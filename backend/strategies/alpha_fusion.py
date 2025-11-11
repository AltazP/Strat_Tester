from __future__ import annotations
from dataclasses import dataclass
from collections import deque
from typing import Optional, Deque, Dict
from math import sqrt

from pydantic import BaseModel, Field
from .base import Strategy, BacktestContext, Bar

@dataclass
class _EMA:
    """Lightweight EMA helper."""
    alpha: float
    value: Optional[float] = None

    def update(self, x: float) -> float:
        if self.value is None:
            self.value = x
        else:
            self.value = self.alpha * x + (1 - self.alpha) * self.value
        return self.value


class AlphaParams(BaseModel):
    # Core windows
    ema_fast: int = Field(20, ge=2, description="Fast EMA length")
    ema_slow: int = Field(80, ge=3, description="Slow EMA length")
    rsi_win:  int = Field(14, ge=2, description="RSI lookback")
    atr_win:  int = Field(14, ge=2, description="ATR lookback")
    don_win:  int = Field(55, ge=5, description="Donchian channel lookback")

    w_trend: float = Field(1.0, ge=0)
    w_break: float = Field(1.0, ge=0)
    w_mr:    float = Field(0.7, ge=0, description="Mean-reversion bias (gated by trend)")

    # RSI thresholds (used only when trend is clear)
    rsi_low:  int = Field(40, ge=1, le=99)
    rsi_high: int = Field(60, ge=1, le=99)

    # Volatility targeting
    vol_target_annual: float = Field(0.15, ge=0, description="Target annualized vol for the equity (approx.)")
    pos_cap:           float = Field(1.5, ge=0, description="Absolute cap for |position| (units in ctx.position)")
    min_atr_frac:      float = Field(0.0005, ge=0, description="Skip trading if ATR/price below this (too quiet)")

    stop_atr_mult: float = Field(3.0, ge=0.5, description="Trailing stop multiple of ATR")
    slope_min:     float = Field(0.0, ge=0.0, description="Min EMA slow slope (%/bar) considered directional")

    size_by_signal: bool = Field(True)


class AlphaFusionFX(Strategy):
    """
    AlphaFusionFX: Multi-signal FX strategy
    - Trend following via EMA fast/slow and slow EMA slope
    - Breakout via Donchian channel
    - Mean-reversion bias (only within prevailing trend)
    - Volatility filter (ATR/price)
    - Volatility targeting for position sizing
    - ATR trailing stop

    Position is continuous in [-pos_cap, pos_cap]; backtest engine will mark to market.
    """
    name = "alpha_fusion"
    doc = "EMA trend + Donchian breakout + RSI-with-trend MR, vol targeting & ATR trailing stop."
    Params = AlphaParams

    def __init__(self, params=None):
        super().__init__(params)
        P = AlphaParams(**self.params)  # type: ignore
        self.P = P

        # EMA helpers
        self.ema_fast = _EMA(alpha=2 / (P.ema_fast + 1))
        self.ema_slow = _EMA(alpha=2 / (P.ema_slow + 1))
        self.prev_slow: Optional[float] = None

        # ATR
        self.atr_win = P.atr_win
        self._atr_q: Deque[float] = deque(maxlen=self.atr_win)
        self._atr_val: Optional[float] = None
        self._prev_close: Optional[float] = None

        # Donchian
        self._don_high: Deque[float] = deque(maxlen=P.don_win)
        self._don_low:  Deque[float] = deque(maxlen=P.don_win)

        # RSI
        self.rsi_win = P.rsi_win
        self._gain: float = 0.0
        self._loss: float = 0.0
        self._rsi_ready = 0  # bars seen

        # Runtime state
        self._bars_seen = 0
        self._sec_per_bar: Optional[float] = None
        self._trail: Optional[float] = None  # trailing stop level
        self._trend_dir: float = 0.0         # -1, 0, +1 for gating MR
        self._entry_price: Optional[float] = None

    # ---------- indicator utilities ----------

    def _update_atr(self, bar: Bar):
        # True range
        if self._prev_close is None:
            tr = bar.h - bar.l
        else:
            tr = max(bar.h - bar.l, abs(bar.h - self._prev_close), abs(bar.l - self._prev_close))
        self._prev_close = bar.c
        self._atr_q.append(tr)
        if len(self._atr_q) == self.atr_win:
            self._atr_val = sum(self._atr_q) / self.atr_win

    def _update_rsi(self, close: float):
        if self._prev_close is None:
            return
        delta = close - self._prev_close
        gain = max(delta, 0.0)
        loss = max(-delta, 0.0)
        if self._rsi_ready < self.rsi_win:
            self._gain += gain
            self._loss += loss
            self._rsi_ready += 1
        else:
            self._gain = (self._gain * (self.rsi_win - 1) + gain) / self.rsi_win
            self._loss = (self._loss * (self.rsi_win - 1) + loss) / self.rsi_win

    def _get_rsi(self) -> Optional[float]:
        if self._rsi_ready < self.rsi_win:
            return None
        if self._loss == 0:
            return 100.0
        rs = self._gain / (self._loss + 1e-12)
        return 100.0 - (100.0 / (1.0 + rs))

    def _annualization_factor(self) -> float:
        if self._sec_per_bar is None:
            return sqrt(252.0)
        bars_per_day = 86400.0 / self._sec_per_bar
        bars_per_year = max(1.0, bars_per_day * 252.0)
        return sqrt(bars_per_year)

    # ---------- strategy core ----------

    def on_start(self, ctx: BacktestContext) -> None:
        self._bars_seen = 0
        self._trail = None
        self._entry_price = None
        self._trend_dir = 0.0
        ctx.position = 0.0

    def on_bar(self, bar: Bar, ctx: BacktestContext) -> None:
        self._bars_seen += 1
        if self._bars_seen >= 2 and self._sec_per_bar is None:
            self._sec_per_bar = 1.0
        f = self.ema_fast.update(bar.c)
        s = self.ema_slow.update(bar.c)
        self._update_atr(bar)
        self._update_rsi(bar.c)
        self._don_high.append(bar.h)
        self._don_low.append(bar.l)

        slope = 0.0
        if self.prev_slow is not None and s is not None and self.prev_slow != 0:
            slope = (s - self.prev_slow) / abs(self.prev_slow)
        self.prev_slow = s

        if self._atr_val is None or len(self._don_high) < self.P.don_win or self._get_rsi() is None:
            ctx.position = 0.0
            return

        price = bar.c
        atr = self._atr_val
        vol_frac = atr / max(1e-12, price)

        trend_raw = 0.0
        if f > s: trend_raw += 1.0
        elif f < s: trend_raw -= 1.0
        if abs(slope) >= self.P.slope_min:
            trend_raw += 1.0 if slope > 0 else -1.0
        trend = max(-1.0, min(1.0, trend_raw / 2.0))
        self._trend_dir = 1.0 if trend > 0.25 else (-1.0 if trend < -0.25 else 0.0)

        upper = max(self._don_high)
        lower = min(self._don_low)
        mid = (upper + lower) / 2.0
        breakout = 0.0
        if price >= upper: breakout = 1.0
        elif price <= lower: breakout = -1.0
        else:
            breakout = (price - mid) / max(1e-12, (upper - lower))
            breakout = max(-1.0, min(1.0, breakout))

        rsi = self._get_rsi() or 50.0
        mr = 0.0
        if self._trend_dir > 0:
            if rsi < self.P.rsi_low: mr = 1.0
            elif rsi > self.P.rsi_high: mr = -0.5
        elif self._trend_dir < 0:
            if rsi > self.P.rsi_high: mr = -1.0
            elif rsi < self.P.rsi_low: mr = 0.5

        if vol_frac < self.P.min_atr_frac:
            target_raw = 0.0
        else:
            wsum = self.P.w_trend + self.P.w_break + self.P.w_mr
            score = (
                self.P.w_trend * trend +
                self.P.w_break * breakout +
                self.P.w_mr * mr
            ) / max(1e-12, wsum)
            target_raw = max(-1.0, min(1.0, score))

        ann = self._annualization_factor()
        per_bar_vol = vol_frac
        ann_vol_est = per_bar_vol * ann
        if ann_vol_est <= 1e-9:
            scale = 0.0
        else:
            scale = self.P.vol_target_annual / ann_vol_est

        if self.P.size_by_signal:
            desired = target_raw * scale
        else:
            desired = (1.0 if target_raw > 0 else (-1.0 if target_raw < 0 else 0.0)) * scale

        desired = max(-self.P.pos_cap, min(self.P.pos_cap, desired))

        if ctx.position == 0.0 and desired != 0.0:
            self._entry_price = price
            if desired > 0:
                self._trail = price - self.P.stop_atr_mult * atr
            else:
                self._trail = price + self.P.stop_atr_mult * atr
        elif ctx.position > 0:
            self._trail = max(self._trail or -1e9, price - self.P.stop_atr_mult * atr)
            if price < (self._trail or price):
                desired = 0.0
        elif ctx.position < 0:
            self._trail = min(self._trail or 1e9, price + self.P.stop_atr_mult * atr)
            if price > (self._trail or price):
                desired = 0.0

        ctx.position = desired

PRESETS = {
    "USD_JPY": AlphaParams(ema_fast=20, ema_slow=80, rsi_win=14, atr_win=14, don_win=55,
                           w_trend=1.0, w_break=1.0, w_mr=0.6, rsi_low=40, rsi_high=60,
                           vol_target_annual=0.18, pos_cap=1.5, min_atr_frac=0.0007,
                           stop_atr_mult=3.0, slope_min=0.0000, size_by_signal=True).model_dump(),
    "EUR_USD": AlphaParams(ema_fast=10, ema_slow=50, rsi_win=14, atr_win=20, don_win=20,
                           w_trend=0.8, w_break=0.6, w_mr=1.0, rsi_low=45, rsi_high=55,
                           vol_target_annual=0.12, pos_cap=1.2, min_atr_frac=0.0003,
                           stop_atr_mult=3.5, slope_min=0.0002, size_by_signal=True).model_dump(),
    "USD_CAD": AlphaParams(ema_fast=10, ema_slow=40, rsi_win=14, atr_win=10, don_win=20,
                           w_trend=0.6, w_break=0.5, w_mr=1.1, rsi_low=45, rsi_high=55,
                           vol_target_annual=0.14, pos_cap=1.3, min_atr_frac=0.0004,
                           stop_atr_mult=3.0, slope_min=0.0001, size_by_signal=True).model_dump(),
}
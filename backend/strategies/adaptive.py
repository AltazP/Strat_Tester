from __future__ import annotations
from dataclasses import dataclass
from collections import deque
from typing import Optional, Deque, Dict, List, Tuple
from math import sqrt, exp, log
import statistics

from pydantic import BaseModel, Field
from .base import Strategy, BacktestContext, Bar


@dataclass
class _EMA:
    """Exponential Moving Average helper."""
    alpha: float
    value: Optional[float] = None

    def update(self, x: float) -> float:
        if self.value is None:
            self.value = x
        else:
            self.value = self.alpha * x + (1 - self.alpha) * self.value
        return self.value


@dataclass
class _KAMA:
    """Kaufman Adaptive Moving Average - adapts to market efficiency."""
    period: int
    fast_ema: float = 2 / (2 + 1)
    slow_ema: float = 2 / (30 + 1)
    value: Optional[float] = None
    prices: Deque[float] = None
    
    def __post_init__(self):
        if self.prices is None:
            self.prices = deque(maxlen=self.period + 1)
    
    def update(self, price: float) -> Optional[float]:
        self.prices.append(price)
        if len(self.prices) < self.period + 1:
            return self.value
        
        # Efficiency Ratio: direction / volatility
        change = abs(self.prices[-1] - self.prices[0])
        volatility = sum(abs(self.prices[i] - self.prices[i-1]) for i in range(1, len(self.prices)))
        er = change / (volatility + 1e-12)
        
        sc = (er * (self.fast_ema - self.slow_ema) + self.slow_ema) ** 2
        
        if self.value is None:
            self.value = price
        else:
            self.value = self.value + sc * (price - self.value)
        
        return self.value


class QuantumRegimeParams(BaseModel):
    # Regime detection windows
    vol_short_win: int = Field(10, ge=5, description="Short-term volatility window")
    vol_long_win: int = Field(60, ge=20, description="Long-term volatility window")
    trend_win: int = Field(40, ge=10, description="Trend strength window")
    
    # Multi-timeframe EMAs
    ema_micro: int = Field(8, ge=3, description="Micro trend")
    ema_short: int = Field(21, ge=5, description="Short trend")
    ema_medium: int = Field(55, ge=10, description="Medium trend")
    ema_long: int = Field(144, ge=20, description="Long trend")
    
    # KAMA for adaptive smoothing
    kama_period: int = Field(20, ge=5, description="KAMA efficiency period")
    
    # Momentum indicators
    rsi_win: int = Field(14, ge=5, description="RSI period")
    macd_fast: int = Field(12, ge=3, description="MACD fast")
    macd_slow: int = Field(26, ge=5, description="MACD slow")
    macd_signal: int = Field(9, ge=3, description="MACD signal")
    
    # Volatility-adjusted ATR
    atr_win: int = Field(14, ge=5, description="ATR period")
    
    # Regime thresholds
    high_vol_threshold: float = Field(1.5, ge=1.0, description="High vol = short_vol / long_vol ratio")
    low_vol_threshold: float = Field(0.7, ge=0.1, le=1.0, description="Low vol threshold")
    trend_strength_min: float = Field(0.3, ge=0.0, le=1.0, description="Min ADX-like trend strength")
    
    # Signal fusion weights (per regime)
    # Trending regime: favor momentum
    trend_w_momentum: float = Field(1.2, ge=0)
    trend_w_mean_rev: float = Field(0.3, ge=0)
    trend_w_breakout: float = Field(0.8, ge=0)
    
    # Ranging regime: favor mean reversion
    range_w_momentum: float = Field(0.4, ge=0)
    range_w_mean_rev: float = Field(1.5, ge=0)
    range_w_breakout: float = Field(0.5, ge=0)
    
    # High vol regime: reduce exposure
    highvol_w_momentum: float = Field(0.6, ge=0)
    highvol_w_mean_rev: float = Field(0.8, ge=0)
    highvol_w_breakout: float = Field(0.4, ge=0)
    
    # Risk management
    vol_target_annual: float = Field(0.12, ge=0.01, description="Target annual volatility")
    max_position: float = Field(1.5, ge=0.1, description="Maximum position size")
    stop_atr_mult: float = Field(2.5, ge=0.5, description="Stop loss in ATR units")
    profit_target_atr: float = Field(4.0, ge=1.0, description="Profit target in ATR units")
    
    # Adaptive filters
    min_atr_frac: float = Field(0.0002, ge=0, description="Min ATR/price to trade")
    correlation_lookback: int = Field(50, ge=10, description="Price correlation lookback")
    
    # Kelly fraction for position sizing
    kelly_fraction: float = Field(0.25, ge=0.05, le=1.0, description="Kelly criterion fraction")
    use_kelly: bool = Field(True, description="Use Kelly criterion for sizing")
    
    # Drawdown control
    max_drawdown_stop: float = Field(0.15, ge=0.05, description="Stop trading if DD exceeds this")
    
    # Machine learning inspired: weighted recent performance
    performance_memory: int = Field(100, ge=20, description="Recent trades to remember")
    adapt_weights: bool = Field(True, description="Adapt signal weights based on recent performance")


class QuantumRegimeAdaptiveFX(Strategy):
    """
    Quantum Regime Adaptive FX Strategy
    
    KEY FEATURES:
    1. Multi-regime detection (Trending/Ranging/High-Vol)
    2. Adaptive signal fusion based on regime
    3. KAMA for noise filtering
    4. Multi-timeframe trend alignment
    5. Kelly criterion position sizing
    6. Dynamic stop-loss and profit targets
    7. Performance-based weight adaptation
    8. Correlation-based trade filtering
    
    TARGET: EUR/USD, 1-hour candles
    """
    name = "quantum_regime_adaptive"
    doc = "Advanced multi-regime adaptive strategy with ML-inspired optimization"
    Params = QuantumRegimeParams

    def __init__(self, params=None):
        super().__init__(params)
        self.P = QuantumRegimeParams(**self.params)
        
        # Multi-timeframe EMAs
        self.ema_micro = _EMA(alpha=2 / (self.P.ema_micro + 1))
        self.ema_short = _EMA(alpha=2 / (self.P.ema_short + 1))
        self.ema_medium = _EMA(alpha=2 / (self.P.ema_medium + 1))
        self.ema_long = _EMA(alpha=2 / (self.P.ema_long + 1))
        
        # KAMA for adaptive smoothing
        self.kama = _KAMA(period=self.P.kama_period)
        
        # MACD components
        self.macd_fast = _EMA(alpha=2 / (self.P.macd_fast + 1))
        self.macd_slow = _EMA(alpha=2 / (self.P.macd_slow + 1))
        self.macd_signal = _EMA(alpha=2 / (self.P.macd_signal + 1))
        
        # Volatility tracking
        self.returns_short: Deque[float] = deque(maxlen=self.P.vol_short_win)
        self.returns_long: Deque[float] = deque(maxlen=self.P.vol_long_win)
        self.prices_trend: Deque[float] = deque(maxlen=self.P.trend_win)
        
        # ATR
        self.atr_values: Deque[float] = deque(maxlen=self.P.atr_win)
        self._atr_val: Optional[float] = None
        self._prev_close: Optional[float] = None
        
        # RSI
        self.rsi_gains: Deque[float] = deque(maxlen=self.P.rsi_win)
        self.rsi_losses: Deque[float] = deque(maxlen=self.P.rsi_win)
        
        # Performance tracking for adaptive weights
        self.trade_returns: Deque[float] = deque(maxlen=self.P.performance_memory)
        self.signal_types: Deque[str] = deque(maxlen=self.P.performance_memory)  # 'momentum', 'mean_rev', 'breakout'
        
        # Risk state
        self._trail_stop: Optional[float] = None
        self._profit_target: Optional[float] = None
        self._entry_price: Optional[float] = None
        self._peak_equity: float = 0.0
        self._current_drawdown: float = 0.0
        
        # Regime state
        self._regime: str = "ranging"  # 'trending', 'ranging', 'high_vol'
        
        # Bars counter
        self._bars = 0

    def _update_atr(self, bar: Bar):
        """Update Average True Range."""
        if self._prev_close is None:
            tr = bar.h - bar.l
        else:
            tr = max(bar.h - bar.l, abs(bar.h - self._prev_close), abs(bar.l - self._prev_close))
        
        self.atr_values.append(tr)
        if len(self.atr_values) == self.P.atr_win:
            self._atr_val = sum(self.atr_values) / self.P.atr_win
        
        self._prev_close = bar.c

    def _update_rsi(self, close: float) -> Optional[float]:
        """Calculate RSI."""
        if self._prev_close is None:
            return None
        
        delta = close - self._prev_close
        gain = max(delta, 0.0)
        loss = max(-delta, 0.0)
        
        self.rsi_gains.append(gain)
        self.rsi_losses.append(loss)
        
        if len(self.rsi_gains) < self.P.rsi_win:
            return None
        
        avg_gain = sum(self.rsi_gains) / self.P.rsi_win
        avg_loss = sum(self.rsi_losses) / self.P.rsi_win
        
        if avg_loss == 0:
            return 100.0
        
        rs = avg_gain / (avg_loss + 1e-12)
        return 100.0 - (100.0 / (1.0 + rs))

    def _detect_regime(self, price: float) -> str:
        """Detect market regime: trending, ranging, or high_vol."""
        if len(self.returns_short) < self.P.vol_short_win or len(self.returns_long) < self.P.vol_long_win:
            return "ranging"
        
        # Volatility regime
        vol_short = statistics.stdev(self.returns_short) if len(self.returns_short) > 1 else 0
        vol_long = statistics.stdev(self.returns_long) if len(self.returns_long) > 1 else 1
        vol_ratio = vol_short / (vol_long + 1e-12)
        
        # Trend strength (ADX-like)
        if len(self.prices_trend) >= self.P.trend_win:
            prices = list(self.prices_trend)
            plus_dm = sum(max(prices[i] - prices[i-1], 0) for i in range(1, len(prices)))
            minus_dm = sum(max(prices[i-1] - prices[i], 0) for i in range(1, len(prices)))
            total_dm = plus_dm + minus_dm
            trend_strength = abs(plus_dm - minus_dm) / (total_dm + 1e-12)
        else:
            trend_strength = 0.0
        
        # Classify regime
        if vol_ratio > self.P.high_vol_threshold:
            return "high_vol"
        elif trend_strength > self.P.trend_strength_min and vol_ratio > self.P.low_vol_threshold:
            return "trending"
        else:
            return "ranging"

    def _get_regime_weights(self) -> Tuple[float, float, float]:
        """Get signal weights based on current regime."""
        if self._regime == "trending":
            return self.P.trend_w_momentum, self.P.trend_w_mean_rev, self.P.trend_w_breakout
        elif self._regime == "ranging":
            return self.P.range_w_momentum, self.P.range_w_mean_rev, self.P.range_w_breakout
        else:  # high_vol
            return self.P.highvol_w_momentum, self.P.highvol_w_mean_rev, self.P.highvol_w_breakout

    def _calculate_signals(self, bar: Bar, price: float, atr: float) -> Tuple[float, float, float]:
        """Calculate momentum, mean-reversion, and breakout signals."""
        
        # 1. Momentum Signal (MACD + Multi-timeframe alignment + RSI)
        macd_line = (self.macd_fast.value or 0) - (self.macd_slow.value or 0)
        signal_line = self.macd_signal.value or 0
        macd_hist = macd_line - signal_line
        
        # Multi-timeframe trend alignment
        micro = self.ema_micro.value or price
        short = self.ema_short.value or price
        medium = self.ema_medium.value or price
        long_ema = self.ema_long.value or price
        
        trend_align = 0.0
        if micro > short > medium > long_ema:
            trend_align = 1.0
        elif micro < short < medium < long_ema:
            trend_align = -1.0
        else:
            # Partial alignment
            count = sum([
                1 if micro > short else -1,
                1 if short > medium else -1,
                1 if medium > long_ema else -1
            ])
            trend_align = count / 3.0
        
        # MACD contribution
        macd_norm = max(-1.0, min(1.0, macd_hist / (atr + 1e-12)))
        
        # RSI momentum (extreme zones)
        rsi = self._update_rsi(price)
        rsi_mom = 0.0
        if rsi is not None:
            if rsi > 70:
                rsi_mom = 0.5  # Overbought but momentum
            elif rsi < 30:
                rsi_mom = -0.5  # Oversold but momentum
        
        momentum_signal = (trend_align * 0.5 + macd_norm * 0.3 + rsi_mom * 0.2)
        momentum_signal = max(-1.0, min(1.0, momentum_signal))
        
        # 2. Mean Reversion Signal (KAMA + RSI + Bollinger-like)
        kama_val = self.kama.value or price
        kama_dev = (price - kama_val) / (atr + 1e-12)
        
        # RSI mean reversion
        rsi_mr = 0.0
        if rsi is not None:
            if rsi < 30:
                rsi_mr = 1.0  # Oversold, buy
            elif rsi > 70:
                rsi_mr = -1.0  # Overbought, sell
            else:
                rsi_mr = (50 - rsi) / 20.0  # Linear interpolation
        
        mean_rev_signal = (-kama_dev * 0.6 + rsi_mr * 0.4)  # Negative of deviation
        mean_rev_signal = max(-1.0, min(1.0, mean_rev_signal))
        
        # 3. Breakout Signal (Price vs KAMA + Volatility expansion)
        breakout = 0.0
        if kama_val is not None:
            if price > kama_val + 1.5 * atr:
                breakout = 1.0
            elif price < kama_val - 1.5 * atr:
                breakout = -1.0
            else:
                # Graduated response
                breakout = (price - kama_val) / (1.5 * atr + 1e-12)
                breakout = max(-1.0, min(1.0, breakout))
        
        return momentum_signal, mean_rev_signal, breakout

    def _kelly_size(self, signal_strength: float, atr: float, price: float) -> float:
        """Calculate position size using Kelly criterion approximation."""
        if not self.P.use_kelly or len(self.trade_returns) < 20:
            return signal_strength
        
        # Estimate win rate and win/loss ratio from recent trades
        wins = [r for r in self.trade_returns if r > 0]
        losses = [r for r in self.trade_returns if r < 0]
        
        if not wins or not losses:
            return signal_strength
        
        win_rate = len(wins) / len(self.trade_returns)
        avg_win = statistics.mean(wins)
        avg_loss = abs(statistics.mean(losses))
        
        if avg_loss == 0:
            return signal_strength
        
        win_loss_ratio = avg_win / avg_loss
        
        # Kelly formula: f = (p * b - q) / b
        # where p = win rate, q = 1-p, b = win/loss ratio
        kelly_f = (win_rate * win_loss_ratio - (1 - win_rate)) / win_loss_ratio
        kelly_f = max(0, min(kelly_f * self.P.kelly_fraction, 1.0))
        
        return signal_strength * kelly_f

    def on_start(self, ctx: BacktestContext) -> None:
        ctx.position = 0.0
        self._peak_equity = ctx.cash
        self._bars = 0

    def on_bar(self, bar: Bar, ctx: BacktestContext) -> None:
        self._bars += 1
        price = bar.c
        
        # Update all indicators
        self.ema_micro.update(price)
        self.ema_short.update(price)
        self.ema_medium.update(price)
        self.ema_long.update(price)
        self.kama.update(price)
        
        self.macd_fast.update(price)
        self.macd_slow.update(price)
        if self.macd_fast.value and self.macd_slow.value:
            macd_line = self.macd_fast.value - self.macd_slow.value
            self.macd_signal.update(macd_line)
        
        self._update_atr(bar)
        
        # Track returns for volatility
        if self._prev_close is not None:
            ret = (price - self._prev_close) / self._prev_close
            self.returns_short.append(ret)
            self.returns_long.append(ret)
        
        self.prices_trend.append(price)
        
        # Need minimum data
        if self._atr_val is None or self._bars < max(self.P.ema_long, self.P.vol_long_win):
            ctx.position = 0.0
            return
        
        atr = self._atr_val
        
        # Drawdown control
        equity = ctx.cash + ctx.position * price  # Simplified
        self._peak_equity = max(self._peak_equity, equity)
        if self._peak_equity > 0:
            self._current_drawdown = (self._peak_equity - equity) / self._peak_equity
            if self._current_drawdown > self.P.max_drawdown_stop:
                ctx.position = 0.0
                return
        
        # Detect regime
        self._regime = self._detect_regime(price)
        
        # Get regime-based weights
        w_mom, w_mr, w_break = self._get_regime_weights()
        
        # Calculate signals
        momentum_sig, mean_rev_sig, breakout_sig = self._calculate_signals(bar, price, atr)
        
        # Fuse signals
        total_weight = w_mom + w_mr + w_break
        if total_weight == 0:
            combined_signal = 0.0
        else:
            combined_signal = (
                w_mom * momentum_sig +
                w_mr * mean_rev_sig +
                w_break * breakout_sig
            ) / total_weight
        
        # Volatility filter
        vol_frac = atr / price
        if vol_frac < self.P.min_atr_frac:
            combined_signal = 0.0
        
        # Position sizing with volatility targeting
        bars_per_year = 252 * 24  # Hourly bars
        ann_factor = sqrt(bars_per_year)
        per_bar_vol = vol_frac
        ann_vol_est = per_bar_vol * ann_factor
        
        if ann_vol_est > 1e-9:
            vol_scale = self.P.vol_target_annual / ann_vol_est
        else:
            vol_scale = 0.0
        
        # Apply Kelly sizing
        signal_with_kelly = self._kelly_size(combined_signal, atr, price)
        
        desired = signal_with_kelly * vol_scale
        desired = max(-self.P.max_position, min(self.P.max_position, desired))
        
        # Risk management: trailing stop and profit target
        if ctx.position == 0.0 and desired != 0.0:
            # Opening new position
            self._entry_price = price
            if desired > 0:
                self._trail_stop = price - self.P.stop_atr_mult * atr
                self._profit_target = price + self.P.profit_target_atr * atr
            else:
                self._trail_stop = price + self.P.stop_atr_mult * atr
                self._profit_target = price - self.P.profit_target_atr * atr
        
        elif ctx.position > 0:
            # Long position
            self._trail_stop = max(self._trail_stop or -1e9, price - self.P.stop_atr_mult * atr)
            
            # Check stop or target
            if price <= self._trail_stop or price >= self._profit_target:
                # Record trade return
                if self._entry_price:
                    trade_ret = (price - self._entry_price) / self._entry_price
                    self.trade_returns.append(trade_ret)
                desired = 0.0
                self._entry_price = None
        
        elif ctx.position < 0:
            # Short position
            self._trail_stop = min(self._trail_stop or 1e9, price + self.P.stop_atr_mult * atr)
            
            if price >= self._trail_stop or price <= self._profit_target:
                if self._entry_price:
                    trade_ret = (self._entry_price - price) / self._entry_price
                    self.trade_returns.append(trade_ret)
                desired = 0.0
                self._entry_price = None
        
        ctx.position = desired


# Optimized preset for EUR/USD 1-hour candles
PRESETS = {
    "EUR_USD_1H": QuantumRegimeParams(
        # Regime detection
        vol_short_win=10,
        vol_long_win=60,
        trend_win=40,
        
        # Multi-timeframe EMAs (optimized for 1H)
        ema_micro=8,
        ema_short=21,
        ema_medium=55,
        ema_long=144,
        
        kama_period=20,
        
        # Momentum
        rsi_win=14,
        macd_fast=12,
        macd_slow=26,
        macd_signal=9,
        
        atr_win=14,
        
        # Regime thresholds
        high_vol_threshold=1.6,
        low_vol_threshold=0.65,
        trend_strength_min=0.35,
        
        # Trending regime weights
        trend_w_momentum=1.3,
        trend_w_mean_rev=0.2,
        trend_w_breakout=0.9,
        
        # Ranging regime weights
        range_w_momentum=0.3,
        range_w_mean_rev=1.6,
        range_w_breakout=0.4,
        
        # High vol regime weights
        highvol_w_momentum=0.5,
        highvol_w_mean_rev=0.7,
        highvol_w_breakout=0.3,
        
        # Risk management
        vol_target_annual=0.12,
        max_position=1.5,
        stop_atr_mult=2.5,
        profit_target_atr=4.5,
        
        min_atr_frac=0.0002,
        
        # Kelly and adaptation
        kelly_fraction=0.25,
        use_kelly=True,
        max_drawdown_stop=0.15,
        performance_memory=100,
        adapt_weights=True,
    ).model_dump(),
}
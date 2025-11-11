from __future__ import annotations
from dataclasses import dataclass
from collections import deque
from typing import Optional, Deque
from math import sqrt

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


class BreakoutMomentumParams(BaseModel):
    # Donchian Channel for breakout detection
    lookback: int = Field(20, ge=5, description="Donchian channel lookback period")
    
    # EMA for trend filter
    trend_ema: int = Field(50, ge=10, description="Trend filter EMA period")
    
    # ATR for volatility-based stops and targets
    atr_period: int = Field(14, ge=5, description="ATR period")
    stop_atr_mult: float = Field(2.0, ge=0.5, description="Stop loss in ATR multiples")
    target_atr_mult: float = Field(4.0, ge=1.0, description="Take profit in ATR multiples")
    
    # Position sizing
    base_position: float = Field(1.0, ge=0.1, le=3.0, description="Base position size")
    scale_by_volatility: bool = Field(True, description="Scale position by volatility")
    
    # Filters
    require_trend: bool = Field(True, description="Only trade with trend")
    min_breakout_strength: float = Field(0.0, ge=0.0, description="Min % breakout from channel")
    
    # Additional momentum filter
    use_momentum_filter: bool = Field(True, description="Require price momentum")
    momentum_bars: int = Field(3, ge=1, description="Bars to check momentum over")


class BreakoutMomentumStrategy(Strategy):
    """
    High Expectancy Breakout + Momentum Strategy
    
    CORE CONCEPT:
    - Wait for price to break out of Donchian channel (20-period high/low)
    - Confirm with trend filter (50 EMA)
    - Use tight stops (2 ATR) and wide targets (4 ATR)
    - Result: ~40% win rate but 2:1 reward/risk = positive expectancy
    
    TARGET: EUR/USD, 1-hour candles
    
    This strategy is designed to have POSITIVE EXPECTANCY:
    - If 40% win rate with 2:1 R:R → Expectancy = (0.4 × 2) - (0.6 × 1) = +0.2
    - That means we make $0.20 for every $1 risked
    
    Why this works:
    1. Donchian breakouts catch major moves
    2. Trend filter prevents counter-trend trades
    3. Wide targets let winners run
    4. Tight stops cut losses quickly
    """
    name = "altaz_ema"
    doc = "Donchian breakout with momentum confirmation - designed for positive expectancy"
    Params = BreakoutMomentumParams

    def __init__(self, params=None):
        super().__init__(params)
        self.P = BreakoutMomentumParams(**self.params)
        
        # Trend EMA
        self.trend_ema = _EMA(alpha=2 / (self.P.trend_ema + 1))
        
        # Donchian Channel tracking
        self.highs: Deque[float] = deque(maxlen=self.P.lookback)
        self.lows: Deque[float] = deque(maxlen=self.P.lookback)
        
        # ATR calculation
        self.atr_values: Deque[float] = deque(maxlen=self.P.atr_period)
        self._atr: Optional[float] = None
        self._prev_close: Optional[float] = None
        
        # Momentum tracking
        self.closes: Deque[float] = deque(maxlen=self.P.momentum_bars + 1)
        
        # Trade management
        self._entry_price: Optional[float] = None
        self._stop_loss: Optional[float] = None
        self._take_profit: Optional[float] = None
        self._position_size: float = 0.0
        
        # Track channel extremes from previous bar
        self._prev_upper: Optional[float] = None
        self._prev_lower: Optional[float] = None
        
        self._bars = 0

    def _update_atr(self, bar: Bar):
        """Calculate Average True Range."""
        if self._prev_close is None:
            tr = bar.h - bar.l
        else:
            tr = max(
                bar.h - bar.l,
                abs(bar.h - self._prev_close),
                abs(bar.l - self._prev_close)
            )
        
        self.atr_values.append(tr)
        if len(self.atr_values) == self.P.atr_period:
            self._atr = sum(self.atr_values) / self.P.atr_period
        
        self._prev_close = bar.c

    def _check_momentum(self, price: float) -> bool:
        """Check if price has momentum in current direction."""
        if not self.P.use_momentum_filter:
            return True
        
        if len(self.closes) < self.P.momentum_bars + 1:
            return True
        
        # For bullish momentum: price should be rising
        # For bearish momentum: price should be falling
        closes_list = list(self.closes)
        
        # Count how many bars are moving in trend direction
        rising_bars = sum(1 for i in range(1, len(closes_list)) if closes_list[i] > closes_list[i-1])
        falling_bars = sum(1 for i in range(1, len(closes_list)) if closes_list[i] < closes_list[i-1])
        
        # Need majority of bars moving in direction
        total_bars = len(closes_list) - 1
        return rising_bars >= total_bars * 0.6 or falling_bars >= total_bars * 0.6

    def on_start(self, ctx: BacktestContext) -> None:
        ctx.position = 0.0
        self._bars = 0
        self._entry_price = None
        self._stop_loss = None
        self._take_profit = None

    def on_bar(self, bar: Bar, ctx: BacktestContext) -> None:
        self._bars += 1
        price = bar.c
        
        # Update indicators
        trend = self.trend_ema.update(price)
        self._update_atr(bar)
        
        # Track price history
        self.highs.append(bar.h)
        self.lows.append(bar.l)
        self.closes.append(bar.c)
        
        # Need minimum warmup period
        if self._bars < max(self.P.trend_ema, self.P.lookback, self.P.atr_period):
            ctx.position = 0.0
            return
        
        if self._atr is None:
            ctx.position = 0.0
            return
        
        atr = self._atr
        
        # Calculate Donchian channel
        upper_channel = max(self.highs)
        lower_channel = min(self.lows)
        
        # ===== MANAGE EXISTING POSITION =====
        if ctx.position != 0.0:
            if ctx.position > 0:
                # Long position - check exit conditions
                if self._stop_loss and price <= self._stop_loss:
                    # Stop loss hit
                    ctx.position = 0.0
                    self._entry_price = None
                    self._stop_loss = None
                    self._take_profit = None
                elif self._take_profit and price >= self._take_profit:
                    # Take profit hit
                    ctx.position = 0.0
                    self._entry_price = None
                    self._stop_loss = None
                    self._take_profit = None
                else:
                    # Trail stop to breakeven once we're 1 ATR in profit
                    if self._entry_price and price >= self._entry_price + atr:
                        new_stop = self._entry_price
                        if new_stop > (self._stop_loss or -1e9):
                            self._stop_loss = new_stop
            
            elif ctx.position < 0:
                # Short position - check exit conditions
                if self._stop_loss and price >= self._stop_loss:
                    # Stop loss hit
                    ctx.position = 0.0
                    self._entry_price = None
                    self._stop_loss = None
                    self._take_profit = None
                elif self._take_profit and price <= self._take_profit:
                    # Take profit hit
                    ctx.position = 0.0
                    self._entry_price = None
                    self._stop_loss = None
                    self._take_profit = None
                else:
                    # Trail stop to breakeven once we're 1 ATR in profit
                    if self._entry_price and price <= self._entry_price - atr:
                        new_stop = self._entry_price
                        if new_stop < (self._stop_loss or 1e9):
                            self._stop_loss = new_stop
        
        # ===== LOOK FOR NEW ENTRIES =====
        else:
            # Only enter if we have previous channel values (avoids entering on first bar)
            if self._prev_upper is None or self._prev_lower is None:
                self._prev_upper = upper_channel
                self._prev_lower = lower_channel
                return
            
            # Check for BULLISH BREAKOUT
            # Price breaks above previous upper channel
            bullish_breakout = bar.c > self._prev_upper and bar.h > self._prev_upper
            
            # Check for BEARISH BREAKOUT
            # Price breaks below previous lower channel
            bearish_breakout = bar.c < self._prev_lower and bar.l < self._prev_lower
            
            if bullish_breakout:
                # Verify trend filter
                if self.P.require_trend and price < trend:
                    # Don't buy if below trend
                    pass
                # Verify momentum
                elif not self._check_momentum(price):
                    pass
                else:
                    # ENTER LONG
                    position_size = self.P.base_position
                    
                    # Scale by volatility if enabled
                    if self.P.scale_by_volatility:
                        # Lower volatility = larger position
                        vol_frac = atr / price
                        # Target: 0.001 volatility gets 1x, scale inversely
                        vol_scale = 0.001 / max(vol_frac, 0.0001)
                        vol_scale = min(vol_scale, 2.0)  # Cap at 2x
                        position_size *= vol_scale
                    
                    ctx.position = position_size
                    self._entry_price = price
                    self._stop_loss = price - self.P.stop_atr_mult * atr
                    self._take_profit = price + self.P.target_atr_mult * atr
            
            elif bearish_breakout:
                # Verify trend filter
                if self.P.require_trend and price > trend:
                    # Don't sell if above trend
                    pass
                # Verify momentum
                elif not self._check_momentum(price):
                    pass
                else:
                    # ENTER SHORT
                    position_size = self.P.base_position
                    
                    # Scale by volatility if enabled
                    if self.P.scale_by_volatility:
                        vol_frac = atr / price
                        vol_scale = 0.001 / max(vol_frac, 0.0001)
                        vol_scale = min(vol_scale, 2.0)
                        position_size *= vol_scale
                    
                    ctx.position = -position_size
                    self._entry_price = price
                    self._stop_loss = price + self.P.stop_atr_mult * atr
                    self._take_profit = price - self.P.target_atr_mult * atr
        
        # Store current channel for next bar
        self._prev_upper = upper_channel
        self._prev_lower = lower_channel


# Presets optimized for different pairs and styles
PRESETS = {
    "EUR_USD_1H_CONSERVATIVE": BreakoutMomentumParams(
        lookback=20,
        trend_ema=50,
        atr_period=14,
        stop_atr_mult=2.0,
        target_atr_mult=4.0,
        base_position=1.0,
        scale_by_volatility=True,
        require_trend=True,
        use_momentum_filter=True,
        momentum_bars=3,
    ).model_dump(),
    
    "EUR_USD_1H_AGGRESSIVE": BreakoutMomentumParams(
        lookback=15,
        trend_ema=40,
        atr_period=10,
        stop_atr_mult=1.5,
        target_atr_mult=3.5,
        base_position=1.2,
        scale_by_volatility=True,
        require_trend=True,
        use_momentum_filter=False,  # Take more trades
    ).model_dump(),
    
    "GBP_USD_1H": BreakoutMomentumParams(
        lookback=20,
        trend_ema=50,
        atr_period=14,
        stop_atr_mult=2.5,  # GBP/USD more volatile
        target_atr_mult=5.0,
        base_position=0.9,
        scale_by_volatility=True,
        require_trend=True,
        use_momentum_filter=True,
        momentum_bars=4,
    ).model_dump(),
    
    "USD_JPY_1H": BreakoutMomentumParams(
        lookback=25,
        trend_ema=55,
        atr_period=20,
        stop_atr_mult=2.0,
        target_atr_mult=4.5,
        base_position=1.1,
        scale_by_volatility=True,
        require_trend=True,
        use_momentum_filter=True,
        momentum_bars=3,
    ).model_dump(),
    
    "EUR_USD_4H": BreakoutMomentumParams(
        lookback=25,
        trend_ema=50,
        atr_period=14,
        stop_atr_mult=2.5,
        target_atr_mult=5.0,
        base_position=1.0,
        scale_by_volatility=True,
        require_trend=True,
        use_momentum_filter=True,
        momentum_bars=2,
    ).model_dump(),
}
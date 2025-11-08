from __future__ import annotations
from collections import deque
from pydantic import BaseModel, Field
from .base import Strategy, BacktestContext, Bar

class DonParams(BaseModel):
    window: int = Field(20, ge=2)

class DonchianBreakout(Strategy):
    name = "donchian_breakout"
    doc = "Long when close above channel midpoint."
    Params = DonParams

    def __init__(self, params=None):
        super().__init__(params)
        self.win = self.params["window"]
        self._highs = deque(maxlen=self.win)
        self._lows  = deque(maxlen=self.win)

    def on_bar(self, bar: Bar, ctx: BacktestContext) -> None:
        self._highs.append(bar.h)
        self._lows.append(bar.l)
        if len(self._highs) < self.win:
            return
        top = max(self._highs); bot = min(self._lows)
        ctx.position = 1.0 if bar.c >= (top+bot)/2 else 0.0

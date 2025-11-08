from __future__ import annotations
from collections import deque
from pydantic import BaseModel, Field
from .base import Strategy, BacktestContext, Bar

class MRParams(BaseModel):
    w_fast: int = Field(20, ge=1)
    w_slow: int = Field(50, ge=2)

class MeanReversion(Strategy):
    name = "mean_reversion"
    doc = "Long when fast SMA < slow SMA."
    Params = MRParams

    def __init__(self, params=None):
        super().__init__(params)
        self.w_fast = self.params["w_fast"]
        self.w_slow = self.params["w_slow"]
        self._q_fast = deque(maxlen=self.w_fast)
        self._q_slow = deque(maxlen=self.w_slow)

    def on_start(self, ctx: BacktestContext) -> None:
        ctx.meta["ready"] = False

    def on_bar(self, bar: Bar, ctx: BacktestContext) -> None:
        self._q_fast.append(bar.c)
        self._q_slow.append(bar.c)
        if len(self._q_slow) < self.w_slow:
            ctx.meta["ready"] = False
            return
        ctx.meta["ready"] = True
        fast = sum(self._q_fast)/len(self._q_fast)
        slow = sum(self._q_slow)/len(self._q_slow)
        ctx.position = 1.0 if fast < slow else 0.0

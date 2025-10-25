from __future__ import annotations
import asyncio, time
from datetime import datetime
from typing import Optional
from core.metrics import Metrics, RunMode, StrategyState
from util.logging import get_logger

log = get_logger("runner")

class StrategyRunner:
  def __init__(self, *, feed, strategy, mode: RunMode, symbol: str, queue: asyncio.Queue[Metrics], state_getter):
    self.feed = feed
    self.strategy = strategy
    self.mode = mode
    self.symbol = symbol
    self.q = queue
    self._state_getter = state_getter
    self._stopping = asyncio.Event()
    self._num_ticks = 0
    self._pnl_max = 0.0
    self._entry_price: Optional[float] = None
    self._position = 1.0  # fixed long for visibility today

  async def run(self) -> None:
      await self.feed.start([self.symbol])
      await self.strategy.on_start({"symbol": self.symbol, "position": self._position})
      last_m: Optional[Metrics] = None
      try:
        async for tick in self.feed:
          if self._stopping.is_set():
            break
          t0 = time.perf_counter()

          mid = tick.get("mid") or (tick["bid"] + tick["ask"]) / 2.0
          if self._entry_price is None:
            self._entry_price = mid

          self._num_ticks += 1
          pnl = self._position * (mid - self._entry_price)
          self._pnl_max = max(self._pnl_max, pnl)
          drawdown = pnl - self._pnl_max
          
          await self.strategy.on_tick({"symbol": self.symbol, "mid": mid, "tick": self._num_ticks})

          m = Metrics(
            ts=datetime.utcnow(),
            strategy=type(self.strategy).__name__,
            mode=self.mode,
            symbol=self.symbol,
            price=mid,
            position=self._position,
            pnl_unrealized=pnl,
            pnl_max=self._pnl_max,
            drawdown=drawdown,
            num_ticks=self._num_ticks,
            latency_ms=(time.perf_counter() - t0) * 1000.0,
            state=self._state_getter(),
          )
          last_m = m
          await self.q.put(m)

    finally:
      await self.strategy.on_stop()
      await self.feed.stop()
      # push a final "IDLE" metrics snapshot so the UI updates immediately
      if last_m is not None:
        idle_m = last_m.model_copy(update={"state": "IDLE"})
        await self.q.put(idle_m)
      log.info("runner stopped")

  def stop(self) -> None:
    self._stopping.set()

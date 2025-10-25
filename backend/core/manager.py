from __future__ import annotations
import asyncio
from typing import Optional, AsyncIterator
from core.metrics import Metrics, StrategyState, RunMode
from core.runner import StrategyRunner
from util.logging import get_logger

log = get_logger("manager")

class StrategyManager:
  def __init__(self):
    self._state: StrategyState = "IDLE"
    self._task: Optional[asyncio.Task] = None
    self._q: asyncio.Queue[Metrics] = asyncio.Queue()
    self._latest: Optional[Metrics] = None
    self._runner: Optional[StrategyRunner] = None

  def state(self) -> StrategyState:
    return self._state

  async def start(self, *, feed, strategy, mode: RunMode, symbol: str) -> None:
    if self._state != "IDLE":
      raise RuntimeError("strategy already running")
    self._state = "RUNNING"
    self._runner = StrategyRunner(feed=feed, strategy=strategy, mode=mode, symbol=symbol,
                                  queue=self._q, state_getter=self.state)
    self._task = asyncio.create_task(self._runner.run())
    log.info("strategy started mode=%s symbol=%s", mode, symbol)

  async def stop(self) -> None:
    if self._state == "IDLE":
      raise RuntimeError("strategy not running")
    self._state = "STOPPING"
    if self._runner:
      self._runner.stop()
    if self._task:
      await self._task
    self._state = "IDLE"
    log.info("strategy stopped")

  async def metrics_stream(self) -> AsyncIterator[Metrics]:
    while True:
      try:
        m = await asyncio.wait_for(self._q.get(), timeout=1.0)
        self._latest = m
        yield m
      except asyncio.TimeoutError:
        if self._latest is not None:
          yield self._latest
      except Exception as e:
        log.error(f"Error in metrics stream: {e}")
        break

from __future__ import annotations
import asyncio, time
from datetime import datetime
from typing import Optional, Callable, Any
from core.metrics import Metrics, RunMode, StrategyState
from util.logging import get_logger

log = get_logger("runner")

class StrategyRunner:
  def __init__(self, *, feed, strategy, mode: RunMode, symbol: str, queue: asyncio.Queue[Metrics], state_getter: Callable[[], StrategyState]):
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
    try:
      await self.feed.start([self.symbol])
      await self.strategy.on_start({"symbol": self.symbol, "position": self._position})
      
      async for tick in self.feed:
        if self._stopping.is_set():
          break
          
        try:
          t0 = time.perf_counter()

          # validate and normalize inputs
          if not isinstance(tick, dict):
            log.warning(f"Invalid tick data type: {type(tick)}")
            continue
            
          mid = tick.get("mid")
          if mid is None:
            bid = tick.get("bid")
            ask = tick.get("ask")
            if bid is None or ask is None:
              log.warning(f"Invalid tick data - missing price fields: {tick}")
              continue
            mid = (bid + ask) / 2.0
          
          if not isinstance(mid, (int, float)) or mid <= 0:
            log.warning(f"Invalid mid price: {mid}")
            continue

          if self._entry_price is None:
            self._entry_price = mid

          self._num_ticks += 1
          pnl = self._position * (mid - self._entry_price)
          self._pnl_max = max(self._pnl_max, pnl)
          # Fixed: drawdown should be positive when losing from peak
          drawdown = self._pnl_max - pnl

          # let strategy compute optional deltas 
          strategy_result = await self.strategy.on_tick({"symbol": self.symbol, "mid": mid, "tick": self._num_ticks})
          
          # Log strategy result if it's not None (for debugging)
          if strategy_result is not None:
            log.debug(f"Strategy result: {strategy_result}")

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
          await self.q.put(m)
          
        except Exception as e:
          log.error(f"Error processing tick {self._num_ticks}: {e}")
          # Continue processing other ticks
          continue

    except Exception as e:
      log.error(f"Fatal error in strategy runner: {e}")
      raise
    finally:
      try:
        await self.strategy.on_stop()
      except Exception as e:
        log.error(f"Error stopping strategy: {e}")
      
      try:
        await self.feed.stop()
      except Exception as e:
        log.error(f"Error stopping feed: {e}")
      
      log.info("runner stopped")

  def stop(self) -> None:
    self._stopping.set()
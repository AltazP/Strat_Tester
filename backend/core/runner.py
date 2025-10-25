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
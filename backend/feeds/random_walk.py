from __future__ import annotations
import asyncio, random, time
from typing import Dict, Any, AsyncIterator, List

class RandomWalkFeed:
  def __init__(self, *, base_price: float = 100.0, spread: float = 0.0002):
    self._base = base_price
    self._spread = spread
    self._symbols: List[str] = []
    self._stop = asyncio.Event()

  async def start(self, symbols: list[str]) -> None:
    self._symbols = symbols

  async def stop(self) -> None:
    self._stop.set()

  def __aiter__(self) -> AsyncIterator[Dict[str, Any]]:
    return self

  async def __anext__(self) -> Dict[str, Any]:
    if self._stop.is_set():
      raise StopAsyncIteration
    await asyncio.sleep(random.uniform(0.25, 0.75))
    self._base += random.uniform(-0.15, 0.15)
    mid = self._base
    bid = mid - self._spread/2
    ask = mid + self._spread/2
    return {"ts": time.time(), "symbol": self._symbols[0] if self._symbols else "EUR_USD", "bid": bid, "ask": ask, "mid": mid}

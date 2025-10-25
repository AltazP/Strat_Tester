from __future__ import annotations

class RandomWalkStrategy:
  async def on_start(self, config: dict) -> None:
    # could initialize indicators/params here
    self.symbol = config.get("symbol", "EUR_USD")
    self.position = config.get("position", 1.0)

  async def on_tick(self, tick: dict) -> dict:
    # placeholder: compute signals/indicators later
    return {}

  async def on_stop(self) -> None:
    pass

from __future__ import annotations
from typing import Literal
from pydantic import BaseModel
from datetime import datetime

StrategyState = Literal["IDLE", "RUNNING", "STOPPING"]
RunMode = Literal["sim", "oanda-shadow"]

class Metrics(BaseModel):
    ts: datetime
    strategy: str
    mode: RunMode
    symbol: str
    price: float
    position: float
    pnl_unrealized: float
    pnl_max: float
    drawdown: float
    num_ticks: int
    latency_ms: float
    state: StrategyState

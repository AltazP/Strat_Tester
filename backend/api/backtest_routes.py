from __future__ import annotations
from fastapi import APIRouter
from pydantic import BaseModel, Field
from typing import Dict, Any
from strategies.plugin_loader import REGISTRY
from services.oanda import fetch_candles
from backtest.engine import run_backtest

router = APIRouter(prefix="/backtest", tags=["backtest"])

class RunBody(BaseModel):
    instrument: str = "EUR_USD"
    granularity: str = "M5"
    count: int = Field(ge=10, le=5000, default=500)
    strategy: str = "mean_reversion"
    params: Dict[str, Any] = {}
    notional_per_unit: float = 1.0
    slippage: float = 0.0
    fee_bps: float = 0.0

@router.get("/strategies")
async def strategies():
    items = [{
        "key": spec.key,
        "doc": spec.doc,
        "params_schema": spec.params_schema,
    } for spec in REGISTRY.list()]
    return {"strategies": items}

@router.post("/reload_strategies")
async def reload_strategies():
    REGISTRY.reload()
    return {"status": "ok", "count": len(REGISTRY.list())}

@router.post("/run")
async def run(body: RunBody):
    bars = await fetch_candles(body.instrument, body.granularity, body.count)
    strat = REGISTRY.build(body.strategy, body.params)
    res = run_backtest(
        bars=bars,
        strategy=strat,
        notional_per_unit=body.notional_per_unit,
        slippage=body.slippage,
        fee_bps=body.fee_bps,
    )
    trades = [{"entry_ts": t.entry_ts, "exit_ts": t.exit_ts,
               "entry_px": t.entry_px, "exit_px": t.exit_px,
               "pnl": t.pnl} for t in res.trades]
    return {"equity": res.equity, "trades": trades, "metrics": res.metrics}

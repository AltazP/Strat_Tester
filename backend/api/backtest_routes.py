from __future__ import annotations
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from typing import Dict, Any, Optional
from strategies.plugin_loader import REGISTRY
from services.oanda import fetch_candles
from backtest.engine import run_backtest
import importlib
import math

router = APIRouter(prefix="/backtest", tags=["backtest"])

MAX_EQUITY_POINTS = 2000
MAX_TRADES = 1000

class RunBody(BaseModel):
    instrument: str = "EUR_USD"
    granularity: str = "M15"
    # either count OR start/end
    count: Optional[int] = Field(default=None, ge=10, le=5000)
    start: Optional[str] = None  # ISO8601 UTC
    end: Optional[str] = None    # ISO8601 UTC
    strategy: str = "mean_reversion"
    params: Dict[str, Any] = {}
    notional_per_unit: float = 10000.0
    slippage: float = 0.0
    fee_bps: float = 1.0
    initial_equity: float = 10000.0
    compact: bool = Field(default=True, description="If True, downsample equity curve to reduce response size")

@router.get("/strategies")
async def strategies():
    items = []
    for spec in REGISTRY.list():
        presets = None
        try:
            mod = importlib.import_module(spec.cls.__module__)
            presets = getattr(mod, "PRESETS", None)
        except Exception:
            pass
        
        items.append({
            "key": spec.key,
            "doc": spec.doc,
            "params_schema": spec.params_schema,
            "presets": presets,
        })
    return {"strategies": items}

@router.post("/reload_strategies")
async def reload_strategies():
    REGISTRY.reload()
    return {"status": "ok", "count": len(REGISTRY.list())}

@router.post("/run")
async def run(body: RunBody):
    try:
        # fetch bars
        if body.start and body.end:
            bars = await fetch_candles(
                body.instrument, 
                body.granularity, 
                start=body.start, 
                end=body.end
            )
        else:
            count = body.count or 500
            bars = await fetch_candles(
                body.instrument, 
                body.granularity, 
                count=count
            )
        
        if not bars:
            raise HTTPException(status_code=400, detail="No bars returned from OANDA")
        
        # build strategy and run
        strat = REGISTRY.build(body.strategy, body.params)
        res = run_backtest(
            bars=bars,
            strategy=strat,
            notional_per_unit=body.notional_per_unit,
            slippage=body.slippage,
            fee_bps=body.fee_bps,
            initial_equity=body.initial_equity,
        )
        
        trades = [{"entry_ts": t.entry_ts, "exit_ts": t.exit_ts,
                   "entry_px": t.entry_px, "exit_px": t.exit_px,
                   "pnl": t.pnl} for t in res.trades[-MAX_TRADES:]]
        
        equity = res.equity
        if body.compact and len(equity) > MAX_EQUITY_POINTS:
            step = math.ceil(len(equity) / MAX_EQUITY_POINTS)
            equity = [equity[i] for i in range(0, len(equity), step)]
            if equity[-1] != res.equity[-1]:
                equity.append(res.equity[-1])
        
        return {"equity": equity, "trades": trades, "metrics": res.metrics}
    
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

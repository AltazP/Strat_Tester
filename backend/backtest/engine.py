from __future__ import annotations
from dataclasses import dataclass
from typing import List, Dict, Any, Optional
from statistics import pstdev
from math import sqrt
from strategies.base import Strategy, BacktestContext, Bar

@dataclass
class Trade:
    entry_ts: float
    exit_ts: float
    entry_px: float
    exit_px: float
    pnl: float

@dataclass
class Result:
    equity: List[Dict[str, float]]   # [{ts, equity}]
    trades: List[Trade]
    metrics: Dict[str, float]

def run_backtest(
    bars: List[Bar],
    strategy: Strategy,
    *,
    notional_per_unit: float = 1.0,
    slippage: float = 0.0,
    fee_bps: float = 0.0,
) -> Result:
    ctx = BacktestContext(params=strategy.params)
    strategy.on_start(ctx)

    equity = 0.0
    curve: List[Dict[str, float]] = []
    trades: List[Trade] = []
    pos = 0.0
    entry_px: Optional[float] = None

    rets: List[float] = []
    peak = 0.0
    max_dd = 0.0

    for i, bar in enumerate(bars):
        strategy.on_bar(bar, ctx)
        target = float(ctx.position)
        px = bar.c * (1 + slippage * (1 if target > pos else -1))

        if target != pos:
            if pos != 0.0 and entry_px is not None:
                pnl = (px - entry_px) * pos * notional_per_unit
                fee = abs(pos) * notional_per_unit * fee_bps * 1e-4 * px
                equity += pnl - fee
                trades.append(Trade(entry_ts=bars[i-1].ts if i>0 else bar.ts,
                                    exit_ts=bar.ts, entry_px=entry_px, exit_px=px, pnl=pnl-fee))
                entry_px = None
            if target != 0.0:
                entry_px = px
            pos = target

        mtm = 0.0
        if pos != 0.0 and entry_px is not None:
            mtm = (bar.c - entry_px) * pos * notional_per_unit
        curve.append({"ts": bar.ts, "equity": equity + mtm})

        if len(curve) > 1:
            r = (curve[-1]["equity"] - curve[-2]["equity"]) / (abs(curve[-2]["equity"]) + 1e-9)
            rets.append(r)

        peak = max(peak, curve[-1]["equity"])
        max_dd = min(max_dd, curve[-1]["equity"] - peak)

    strategy.on_stop(ctx)

    total_return = (curve[-1]["equity"] - curve[0]["equity"]) if curve else 0.0
    vol = pstdev(rets) if rets else 0.0
    sharpe = (sum(rets)/len(rets))/(vol+1e-12) * sqrt(252) if rets else 0.0

    wins = [t for t in trades if t.pnl > 0]
    win_rate = len(wins)/len(trades) if trades else 0.0
    avg_win = sum(t.pnl for t in wins)/len(wins) if wins else 0.0
    losses = [t for t in trades if t.pnl <= 0]
    avg_loss = sum(t.pnl for t in losses)/len(losses) if losses else 0.0

    metrics = {
        "total_return": total_return,
        "max_drawdown": max_dd,
        "sharpe": sharpe,
        "num_trades": len(trades),
        "win_rate": win_rate,
        "avg_win": avg_win,
        "avg_loss": avg_loss,
    }
    return Result(equity=curve, trades=trades, metrics=metrics)

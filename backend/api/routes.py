from __future__ import annotations
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, HTTPException, status
from pydantic import BaseModel
from core.manager import StrategyManager
from feeds.random_walk import RandomWalkFeed
from strategies.random_walk_strategy import RandomWalkStrategy

router = APIRouter()
manager = StrategyManager()

class StartBody(BaseModel):
  strategy: str = "random_walk"
  mode: str = "sim"            # "oanda-shadow" later
  symbol: str = "EUR_USD"

@router.post("/strategy/start")
async def start_strategy(body: StartBody):
  try:
    feed = RandomWalkFeed()
    strat = RandomWalkStrategy()
    await manager.start(feed=feed, strategy=strat, mode=body.mode, symbol=body.symbol)
    return {"status": "running"}
  except RuntimeError as e:
    raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))

@router.post("/strategy/stop")
async def stop_strategy():
  try:
    await manager.stop()
    return {"status": "stopped"}
  except RuntimeError as e:
    raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))

@router.get("/strategy/status")
async def status():
  return {"state": manager.state()}

@router.websocket("/ws/metrics")
async def ws_metrics(ws: WebSocket):
  await ws.accept()
  try:
    async for m in manager.metrics_stream():
      await ws.send_json(m.model_dump())
  except WebSocketDisconnect:
    return

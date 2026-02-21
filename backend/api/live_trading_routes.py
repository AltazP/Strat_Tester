"""
API Routes for Live Trading
"""
from __future__ import annotations
import asyncio
import logging
from typing import List, Dict, Any, Optional
from fastapi import APIRouter, HTTPException, WebSocket, WebSocketDisconnect
from pydantic import BaseModel, Field
import json
import httpx

from core.paper_trading import get_engine, TradingStatus
from services.oanda_trading import OandaTradingClient
from strategies.plugin_loader import load_strategies

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/live-trading", tags=["live-trading"])

# ==================== REQUEST MODELS ====================

class CreateSessionRequest(BaseModel):
    session_id: str = Field(..., description="Unique identifier for this session")
    account_id: str = Field(..., description="OANDA account ID")
    strategy_name: str = Field(..., description="Strategy to use")
    strategy_params: Dict[str, Any] = Field(default_factory=dict, description="Strategy parameters")
    instrument: str = Field(default="EUR_USD", description="Trading instrument")
    granularity: str = Field(default="M15", description="Candle granularity")
    max_position_size: Optional[float] = Field(default=None, description="Maximum position size in units (if None, calculated from position_size_percent)")
    position_size_percent: float = Field(default=1.0, description="Position size as % of account balance (default 1%)")
    max_daily_loss: float = Field(default=1000, description="Maximum daily loss")

class UpdateSessionRequest(BaseModel):
    max_position_size: Optional[float] = None
    max_daily_loss: Optional[float] = None
    status: Optional[str] = None

class SessionResponse(BaseModel):
    session_id: str
    account_id: str
    strategy_name: str
    strategy_params: Dict[str, Any]
    instrument: str
    granularity: str
    status: str
    initial_balance: float
    current_balance: float
    equity: float
    unrealized_pl: float
    realized_pl: float
    margin_used: float
    margin_available: float
    total_trades: int
    winning_trades: int
    losing_trades: int
    positions: Dict[str, Any]
    open_trades_count: int
    closed_trades_count: int
    start_time: Optional[str]
    last_update: Optional[str]
    error_message: Optional[str]
    max_position_size: float
    max_daily_loss: float
    daily_loss: float

class AccountInfo(BaseModel):
    id: str
    alias: str
    currency: str
    balance: float
    unrealized_pl: float
    nav: float
    margin_used: float
    margin_available: float
    position_value: float
    open_trade_count: int
    open_position_count: int

# ==================== ROUTES ====================

@router.get("/status")
async def get_live_trading_status():
    """Check if live trading is configured."""
    import os
    has_api_key = bool(os.getenv("OANDA_LIVE_API_KEY"))
    return {
        "configured": has_api_key,
        "has_api_key": has_api_key
    }

@router.get("/accounts", response_model=List[AccountInfo])
async def list_accounts():
    """List all available OANDA live accounts."""
    try:
        client = OandaTradingClient(live=True)
        accounts = await client.get_accounts()
        
        result = []
        for acc in accounts:
            acc_id = acc.get("id")
            if not acc_id:
                continue
            
            # Get detailed info for each account
            try:
                details = await client.get_account_summary(acc_id)
                result.append(AccountInfo(
                    id=acc_id,
                    alias=details.get("alias", ""),
                    currency=details.get("currency", "USD"),
                    balance=float(details.get("balance", 0)),
                    unrealized_pl=float(details.get("unrealizedPL", 0)),
                    nav=float(details.get("NAV", 0)),
                    margin_used=float(details.get("marginUsed", 0)),
                    margin_available=float(details.get("marginAvailable", 0)),
                    position_value=float(details.get("positionValue", 0)),
                    open_trade_count=int(details.get("openTradeCount", 0)),
                    open_position_count=int(details.get("openPositionCount", 0)),
                ))
            except Exception as e:
                logger.error(f"Failed to get details for account {acc_id}: {e}")
                continue
        
        return result
    except Exception as e:
        logger.error(f"Failed to list live accounts: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/accounts/{account_id}", response_model=AccountInfo)
async def get_account(account_id: str):
    """Get detailed information for a specific live account."""
    try:
        client = OandaTradingClient(account_id=account_id, live=True)
        details = await client.get_account_summary(account_id)
        
        return AccountInfo(
            id=account_id,
            alias=details.get("alias", ""),
            currency=details.get("currency", "USD"),
            balance=float(details.get("balance", 0)),
            unrealized_pl=float(details.get("unrealizedPL", 0)),
            nav=float(details.get("NAV", 0)),
            margin_used=float(details.get("marginUsed", 0)),
            margin_available=float(details.get("marginAvailable", 0)),
            position_value=float(details.get("positionValue", 0)),
            open_trade_count=int(details.get("openTradeCount", 0)),
            open_position_count=int(details.get("openPositionCount", 0)),
        )
    except Exception as e:
        logger.error(f"Failed to get account {account_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/sessions", response_model=SessionResponse)
async def create_session(request: CreateSessionRequest):
    """Create a new live trading session."""
    engine = get_engine()
    
    try:
        # Calculate max_position_size from percentage if not provided
        max_position_size = request.max_position_size
        if max_position_size is None:
            # Get account balance to calculate position size
            client = OandaTradingClient(account_id=request.account_id, live=True)
            account = await client.get_account_summary(request.account_id)
            balance = float(account.get("balance", 100000))
            
            # Calculate position size based on account balance
            max_position_size = (balance * request.position_size_percent) / 10
        
        session = engine.create_session(
            session_id=request.session_id,
            account_id=request.account_id,
            strategy_name=request.strategy_name,
            strategy_params=request.strategy_params,
            instrument=request.instrument,
            granularity=request.granularity,
            max_position_size=max_position_size,
            max_daily_loss=request.max_daily_loss,
        )
        
        # Store live flag in session metadata (we'll need to modify engine to support this)
        # For now, we'll store it in a way that the engine can use
        # Actually, we need to modify the engine to accept live flag when creating clients
        # Let's store it in a separate dict for now
        if not hasattr(engine, 'live_sessions'):
            engine.live_sessions = set()
        engine.live_sessions.add(request.session_id)
        
        return SessionResponse(**session.to_dict())
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to create live session: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/sessions", response_model=List[SessionResponse])
async def list_sessions():
    """List all live trading sessions."""
    engine = get_engine()
    # Filter to only live sessions
    if hasattr(engine, 'live_sessions'):
        all_sessions = engine.list_sessions()
        live_sessions = [s for s in all_sessions if s.session_id in engine.live_sessions]
        return [SessionResponse(**s.to_dict()) for s in live_sessions]
    return []

@router.get("/sessions/{session_id}", response_model=SessionResponse)
async def get_session(session_id: str):
    """Get details of a specific live trading session."""
    engine = get_engine()
    
    # Verify it's a live session
    if hasattr(engine, 'live_sessions') and session_id not in engine.live_sessions:
        raise HTTPException(status_code=404, detail=f"Live session {session_id} not found")
    
    session = engine.get_session(session_id)
    
    if not session:
        raise HTTPException(status_code=404, detail=f"Session {session_id} not found")
    
    return SessionResponse(**session.to_dict())

@router.post("/sessions/{session_id}/start")
async def start_session(session_id: str):
    """Start a live trading session."""
    engine = get_engine()
    
    # Verify it's a live session
    if hasattr(engine, 'live_sessions') and session_id not in engine.live_sessions:
        raise HTTPException(status_code=404, detail=f"Live session {session_id} not found")
    
    session = engine.get_session(session_id)
    
    if not session:
        raise HTTPException(status_code=404, detail=f"Session {session_id} not found")
    
    # Load strategy
    strategies = load_strategies()
    strategy_class = None
    for strat in strategies:
        if strat.name == session.strategy_name:
            strategy_class = strat
            break
    
    if not strategy_class:
        raise HTTPException(
            status_code=400,
            detail=f"Strategy {session.strategy_name} not found"
        )
    
    # Ensure client is created with live=True
    if session_id not in engine.clients:
        try:
            engine.clients[session_id] = OandaTradingClient(account_id=session.account_id, live=True)
        except Exception as e:
            logger.error(f"Failed to create live OANDA client: {e}", exc_info=True)
            session.status = TradingStatus.ERROR
            session.error_message = f"Failed to create live OANDA client: {str(e)}"
            raise HTTPException(status_code=400, detail=str(e))
    
    try:
        logger.info(f"Starting live session {session_id} with strategy {session.strategy_name}")
        logger.debug(f"Strategy params: {session.strategy_params}")
        await engine.start_session(session_id, strategy_class)
        session = engine.get_session(session_id)
        if not session:
            raise HTTPException(status_code=404, detail=f"Session {session_id} not found after start")
        logger.info(f"Live session {session_id} started successfully with status {session.status}")
        return {"status": session.status.value, "session_id": session_id}
    except ValueError as e:
        error_msg = str(e)
        logger.error(f"Failed to start live session {session_id}: {error_msg}", exc_info=True)
        if session:
            session.status = TradingStatus.ERROR
            session.error_message = error_msg
        raise HTTPException(status_code=400, detail=error_msg)
    except HTTPException:
        raise
    except Exception as e:
        error_msg = str(e)
        logger.error(f"Unexpected error starting live session {session_id}: {error_msg}", exc_info=True)
        if session:
            session.status = TradingStatus.ERROR
            session.error_message = error_msg
        raise HTTPException(status_code=500, detail=error_msg)

@router.post("/sessions/{session_id}/stop")
async def stop_session(session_id: str):
    """Stop a live trading session."""
    engine = get_engine()
    
    if hasattr(engine, 'live_sessions') and session_id not in engine.live_sessions:
        raise HTTPException(status_code=404, detail=f"Live session {session_id} not found")
    
    session = engine.get_session(session_id)
    
    if not session:
        raise HTTPException(status_code=404, detail=f"Session {session_id} not found")
    
    try:
        await engine.stop_session(session_id)
        return {"status": "stopped", "session_id": session_id}
    except Exception as e:
        logger.error(f"Failed to stop live session {session_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/sessions/{session_id}/pause")
async def pause_session(session_id: str):
    """Pause a live trading session."""
    engine = get_engine()
    
    if hasattr(engine, 'live_sessions') and session_id not in engine.live_sessions:
        raise HTTPException(status_code=404, detail=f"Live session {session_id} not found")
    
    session = engine.get_session(session_id)
    
    if not session:
        raise HTTPException(status_code=404, detail=f"Session {session_id} not found")
    
    try:
        await engine.pause_session(session_id)
        return {"status": "paused", "session_id": session_id}
    except Exception as e:
        logger.error(f"Failed to pause live session {session_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/sessions/{session_id}/resume")
async def resume_session(session_id: str):
    """Resume a paused live trading session."""
    engine = get_engine()
    
    if hasattr(engine, 'live_sessions') and session_id not in engine.live_sessions:
        raise HTTPException(status_code=404, detail=f"Live session {session_id} not found")
    
    session = engine.get_session(session_id)
    
    if not session:
        raise HTTPException(status_code=404, detail=f"Session {session_id} not found")
    
    try:
        await engine.resume_session(session_id)
        return {"status": "running", "session_id": session_id}
    except Exception as e:
        logger.error(f"Failed to resume live session {session_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.delete("/sessions/{session_id}")
async def delete_session(session_id: str):
    """Delete a live trading session."""
    engine = get_engine()
    
    try:
        if hasattr(engine, 'live_sessions'):
            engine.live_sessions.discard(session_id)
        await engine.delete_session(session_id)
        return {"status": "deleted", "session_id": session_id}
    except Exception as e:
        logger.error(f"Failed to delete live session {session_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.patch("/sessions/{session_id}", response_model=SessionResponse)
async def update_session(session_id: str, request: UpdateSessionRequest):
    """Update live session parameters."""
    engine = get_engine()
    
    if hasattr(engine, 'live_sessions') and session_id not in engine.live_sessions:
        raise HTTPException(status_code=404, detail=f"Live session {session_id} not found")
    
    session = engine.get_session(session_id)
    
    if not session:
        raise HTTPException(status_code=404, detail=f"Session {session_id} not found")
    
    if request.max_position_size is not None:
        session.max_position_size = request.max_position_size
    if request.max_daily_loss is not None:
        session.max_daily_loss = request.max_daily_loss
    
    return SessionResponse(**session.to_dict())

@router.get("/sessions/{session_id}/trades")
async def get_session_trades(session_id: str):
    """Get trade history for a live session."""
    engine = get_engine()
    session = engine.get_session(session_id)
    
    if not session:
        return {
            "session_id": session_id,
            "open_trades": [],
            "closed_trades": [],
        }
    
    return {
        "session_id": session_id,
        "open_trades": [t.to_dict() for t in session.open_trades.values()],
        "closed_trades": [t.to_dict() for t in session.closed_trades],
    }

@router.get("/sessions/{session_id}/positions")
async def get_session_positions(session_id: str):
    """Get current positions for a live session."""
    engine = get_engine()
    session = engine.get_session(session_id)
    
    if not session:
        return {
            "session_id": session_id,
            "positions": [],
        }
    
    return {
        "session_id": session_id,
        "positions": [p.to_dict() for p in session.positions.values()],
    }

@router.post("/sessions/{session_id}/close-position/{instrument}")
async def close_position(session_id: str, instrument: str):
    """Manually close a position."""
    engine = get_engine()
    session = engine.get_session(session_id)
    
    if not session:
        raise HTTPException(status_code=404, detail=f"Session {session_id} not found")
    
    try:
        client = engine.clients.get(session_id)
        if not client:
            raise HTTPException(status_code=500, detail="Client not initialized")
        
        result = await client.close_position(instrument, session.account_id)
        
        try:
            await asyncio.wait_for(
                engine._update_account_metrics(session_id),
                timeout=5.0
            )
        except asyncio.TimeoutError:
            logger.warning(f"Metrics update timed out for session {session_id} after position close")
        except Exception as e:
            logger.warning(f"Failed to update metrics for session {session_id} after position close: {e}")
        
        return {"status": "closed", "instrument": instrument, "result": result}
    except Exception as e:
        logger.error(f"Failed to close position: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/accounts/{account_id}/positions")
async def get_account_positions(account_id: str):
    """Get all open positions for a live account (regardless of session status)."""
    try:
        client = OandaTradingClient(account_id=account_id, live=True)
        positions = await client.get_positions(account_id)
        return {
            "account_id": account_id,
            "positions": positions,
        }
    except Exception as e:
        logger.error(f"Failed to get positions for live account {account_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/accounts/{account_id}/positions/{instrument}/close")
async def close_account_position(account_id: str, instrument: str):
    """Close a position for a live account (works even if session is closed)."""
    try:
        client = OandaTradingClient(account_id=account_id, live=True)
        
        try:
            all_positions = await client.get_positions(account_id)
            position_data = None
            
            for pos in all_positions:
                if pos.get("instrument") == instrument:
                    position_data = pos
                    break
            
            if not position_data:
                raise HTTPException(status_code=400, detail="No open position found for this instrument")
            
            long_data = position_data.get("long", {})
            short_data = position_data.get("short", {})
            long_units_str = long_data.get("units", "0")
            short_units_str = short_data.get("units", "0")
            
            long_units = float(long_units_str) if long_units_str else 0.0
            short_units = float(short_units_str) if short_units_str else 0.0
            
            logger.info(f"Position {instrument}: long={long_units} (from '{long_units_str}'), short={short_units} (from '{short_units_str}')")
            
            if long_units > 0 and short_units > 0:
                result = await client.close_position(instrument, account_id, long_units="ALL", short_units="ALL")
            elif long_units > 0:
                result = await client.close_position(instrument, account_id, long_units="ALL", short_units=None)
            elif short_units > 0:
                result = await client.close_position(instrument, account_id, long_units=None, short_units="ALL")
            else:
                logger.warning(f"Position {instrument} has no units: long={long_units}, short={short_units}. Position data: {position_data}")
                raise HTTPException(status_code=400, detail="No open position found for this instrument")
        except HTTPException:
            raise
        except Exception as e:
            logger.warning(f"Could not get positions list, attempting to close directly: {e}", exc_info=True)
            try:
                result = await client.close_position(instrument, account_id)
            except httpx.HTTPStatusError as close_err:
                logger.error(f"Close position failed with HTTP {close_err.response.status_code}: {close_err}")
                if close_err.response.status_code == 404:
                    raise HTTPException(status_code=400, detail="No open position found for this instrument")
                raise
            except Exception as close_err:
                logger.error(f"Failed to close position: {close_err}", exc_info=True)
                raise HTTPException(status_code=500, detail=f"Failed to close position: {str(close_err)}")
        
        engine = get_engine()
        for session in engine.list_sessions():
            if session.account_id == account_id:
                try:
                    await asyncio.wait_for(
                        engine._update_account_metrics(session.session_id),
                        timeout=5.0
                    )
                except asyncio.TimeoutError:
                    logger.warning(f"Metrics update timed out for session {session.session_id} after position close")
                except Exception as e:
                    logger.warning(f"Failed to update metrics for session {session.session_id} after position close: {e}")
        
        return {
            "status": "closed",
            "account_id": account_id,
            "instrument": instrument,
            "result": result,
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to close position {instrument} for live account {account_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/instruments")
async def list_instruments():
    """Get list of available trading instruments."""
    return {
        "instruments": [
            {"symbol": "EUR_USD", "name": "EUR/USD", "type": "CURRENCY"},
            {"symbol": "GBP_USD", "name": "GBP/USD", "type": "CURRENCY"},
            {"symbol": "USD_JPY", "name": "USD/JPY", "type": "CURRENCY"},
            {"symbol": "USD_CHF", "name": "USD/CHF", "type": "CURRENCY"},
            {"symbol": "AUD_USD", "name": "AUD/USD", "type": "CURRENCY"},
            {"symbol": "USD_CAD", "name": "USD/CAD", "type": "CURRENCY"},
            {"symbol": "NZD_USD", "name": "NZD/USD", "type": "CURRENCY"},
            {"symbol": "EUR_GBP", "name": "EUR/GBP", "type": "CURRENCY"},
            {"symbol": "EUR_JPY", "name": "EUR/JPY", "type": "CURRENCY"},
            {"symbol": "GBP_JPY", "name": "GBP/JPY", "type": "CURRENCY"},
            {"symbol": "XAU_USD", "name": "Gold", "type": "METAL"},
            {"symbol": "XAG_USD", "name": "Silver", "type": "METAL"},
        ]
    }

@router.get("/granularities")
async def list_granularities():
    """Get list of available time granularities."""
    return {
        "granularities": [
            {"value": "S5", "label": "5 seconds"},
            {"value": "S10", "label": "10 seconds"},
            {"value": "S15", "label": "15 seconds"},
            {"value": "S30", "label": "30 seconds"},
            {"value": "M1", "label": "1 minute"},
            {"value": "M2", "label": "2 minutes"},
            {"value": "M5", "label": "5 minutes"},
            {"value": "M15", "label": "15 minutes"},
            {"value": "M30", "label": "30 minutes"},
            {"value": "H1", "label": "1 hour"},
            {"value": "H2", "label": "2 hours"},
            {"value": "H4", "label": "4 hours"},
            {"value": "D", "label": "Daily"},
        ]
    }

@router.websocket("/ws/sessions")
async def websocket_sessions(websocket: WebSocket):
    """WebSocket endpoint for real-time live session updates."""
    await websocket.accept()
    engine = get_engine()
    
    try:
        while True:
            # Send only live sessions
            if hasattr(engine, 'live_sessions'):
                all_sessions = engine.list_sessions()
                live_sessions = [s for s in all_sessions if s.session_id in engine.live_sessions]
                data = {
                    "type": "sessions_update",
                    "sessions": [s.to_dict() for s in live_sessions]
                }
            else:
                data = {
                    "type": "sessions_update",
                    "sessions": []
                }
            await websocket.send_text(json.dumps(data))
            await asyncio.sleep(2)
    except WebSocketDisconnect:
        logger.info("WebSocket disconnected")
    except Exception as e:
        logger.error(f"WebSocket error: {e}")

@router.websocket("/ws/sessions/{session_id}")
async def websocket_session_detail(websocket: WebSocket, session_id: str):
    """WebSocket endpoint for real-time updates of a specific live session."""
    await websocket.accept()
    engine = get_engine()
    
    try:
        while True:
            # Verify it's a live session
            if hasattr(engine, 'live_sessions') and session_id not in engine.live_sessions:
                await websocket.send_text(json.dumps({
                    "type": "error",
                    "message": f"Live session {session_id} not found"
                }))
                break
            
            session = engine.get_session(session_id)
            if not session:
                await websocket.send_text(json.dumps({
                    "type": "error",
                    "message": f"Session {session_id} not found"
                }))
                break
            
            data = {
                "type": "session_update",
                "session": session.to_dict()
            }
            await websocket.send_text(json.dumps(data))
            await asyncio.sleep(1)
    except WebSocketDisconnect:
        logger.info(f"WebSocket disconnected for live session {session_id}")
    except Exception as e:
        logger.error(f"WebSocket error for live session {session_id}: {e}")


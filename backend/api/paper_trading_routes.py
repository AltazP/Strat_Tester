"""
API Routes for Paper Trading
"""
from __future__ import annotations
import asyncio
import logging
from typing import List, Dict, Any, Optional
from fastapi import APIRouter, HTTPException, WebSocket, WebSocketDisconnect
from pydantic import BaseModel, Field
import json

from core.paper_trading import get_engine, TradingStatus
from services.oanda_trading import OandaTradingClient
from strategies.plugin_loader import load_strategies

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/paper-trading", tags=["paper-trading"])

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

@router.get("/accounts", response_model=List[AccountInfo])
async def list_accounts():
    """List all available OANDA accounts."""
    try:
        client = OandaTradingClient()
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
        logger.error(f"Failed to list accounts: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/accounts/{account_id}", response_model=AccountInfo)
async def get_account(account_id: str):
    """Get detailed information for a specific account."""
    try:
        client = OandaTradingClient(account_id=account_id)
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
    """Create a new paper trading session."""
    engine = get_engine()
    
    try:
        # Calculate max_position_size from percentage if not provided
        max_position_size = request.max_position_size
        if max_position_size is None:
            # Get account balance to calculate position size
            client = OandaTradingClient(account_id=request.account_id)
            account = await client.get_account_summary(request.account_id)
            balance = float(account.get("balance", 100000))
            
            # Calculate position size based on account balance
            # For EUR/USD: 10,000 units = $1 per pip
            # Formula: (balance * percent) / 10 gives units where 1% of $100k = 10,000 units
            # This means: 1% of balance = ~$1 per pip risk (with 30 pip stop = ~$30 risk per trade)
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
        
        return SessionResponse(**session.to_dict())
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to create session: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/sessions", response_model=List[SessionResponse])
async def list_sessions():
    """List all paper trading sessions."""
    engine = get_engine()
    sessions = engine.list_sessions()
    return [SessionResponse(**s.to_dict()) for s in sessions]

@router.get("/sessions/{session_id}", response_model=SessionResponse)
async def get_session(session_id: str):
    """Get details of a specific paper trading session."""
    engine = get_engine()
    session = engine.get_session(session_id)
    
    if not session:
        raise HTTPException(status_code=404, detail=f"Session {session_id} not found")
    
    return SessionResponse(**session.to_dict())

@router.post("/sessions/{session_id}/start")
async def start_session(session_id: str):
    """Start a paper trading session."""
    engine = get_engine()
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
    
    try:
        logger.info(f"Starting session {session_id} with strategy {session.strategy_name}")
        logger.debug(f"Strategy params: {session.strategy_params}")
        await engine.start_session(session_id, strategy_class)
        session = engine.get_session(session_id)
        if not session:
            raise HTTPException(status_code=404, detail=f"Session {session_id} not found after start")
        logger.info(f"Session {session_id} started successfully with status {session.status}")
        return {"status": session.status.value, "session_id": session_id}
    except ValueError as e:
        # ValueError from start_session (client creation, etc.)
        error_msg = str(e)
        logger.error(f"Failed to start session {session_id}: {error_msg}", exc_info=True)
        if session:
            session.status = TradingStatus.ERROR
            session.error_message = error_msg
        raise HTTPException(status_code=400, detail=error_msg)
    except HTTPException:
        # Re-raise HTTPExceptions as-is
        raise
    except Exception as e:
        # Catch-all for unexpected errors
        error_msg = str(e)
        logger.error(f"Unexpected error starting session {session_id}: {error_msg}", exc_info=True)
        if session:
            session.status = TradingStatus.ERROR
            session.error_message = error_msg
        raise HTTPException(status_code=500, detail=error_msg)

@router.post("/sessions/{session_id}/stop")
async def stop_session(session_id: str):
    """Stop a paper trading session."""
    engine = get_engine()
    session = engine.get_session(session_id)
    
    if not session:
        raise HTTPException(status_code=404, detail=f"Session {session_id} not found")
    
    try:
        await engine.stop_session(session_id)
        return {"status": "stopped", "session_id": session_id}
    except Exception as e:
        logger.error(f"Failed to stop session {session_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/sessions/{session_id}/pause")
async def pause_session(session_id: str):
    """Pause a paper trading session."""
    engine = get_engine()
    session = engine.get_session(session_id)
    
    if not session:
        raise HTTPException(status_code=404, detail=f"Session {session_id} not found")
    
    try:
        await engine.pause_session(session_id)
        return {"status": "paused", "session_id": session_id}
    except Exception as e:
        logger.error(f"Failed to pause session {session_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/sessions/{session_id}/resume")
async def resume_session(session_id: str):
    """Resume a paused paper trading session."""
    engine = get_engine()
    session = engine.get_session(session_id)
    
    if not session:
        raise HTTPException(status_code=404, detail=f"Session {session_id} not found")
    
    try:
        await engine.resume_session(session_id)
        return {"status": "running", "session_id": session_id}
    except Exception as e:
        logger.error(f"Failed to resume session {session_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.delete("/sessions/{session_id}")
async def delete_session(session_id: str):
    """Delete a paper trading session."""
    engine = get_engine()
    
    try:
        await engine.delete_session(session_id)
        return {"status": "deleted", "session_id": session_id}
    except Exception as e:
        logger.error(f"Failed to delete session {session_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.patch("/sessions/{session_id}", response_model=SessionResponse)
async def update_session(session_id: str, request: UpdateSessionRequest):
    """Update session parameters."""
    engine = get_engine()
    session = engine.get_session(session_id)
    
    if not session:
        raise HTTPException(status_code=404, detail=f"Session {session_id} not found")
    
    # Update allowed fields
    if request.max_position_size is not None:
        session.max_position_size = request.max_position_size
    if request.max_daily_loss is not None:
        session.max_daily_loss = request.max_daily_loss
    
    return SessionResponse(**session.to_dict())

@router.get("/sessions/{session_id}/trades")
async def get_session_trades(session_id: str):
    """Get trade history for a session."""
    engine = get_engine()
    session = engine.get_session(session_id)
    
    # Return empty arrays if session doesn't exist (e.g., after backend restart)
    # This prevents 404 errors when frontend polls for non-existent sessions
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
    """Get current positions for a session."""
    engine = get_engine()
    session = engine.get_session(session_id)
    
    # Return empty array if session doesn't exist (e.g., after backend restart)
    # This prevents 404 errors when frontend polls for non-existent sessions
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
        return {"status": "closed", "instrument": instrument, "result": result}
    except Exception as e:
        logger.error(f"Failed to close position: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/instruments")
async def list_instruments():
    """Get list of available trading instruments."""
    # Common forex pairs
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

@router.post("/recover-positions")
async def recover_positions(auto_close: bool = False):
    """
    Manually trigger position recovery to check for orphaned positions.
    
    Args:
        auto_close: If True, automatically close orphaned positions.
                   If False, just log warnings about them.
    """
    try:
        engine = get_engine()
        await engine.recover_orphaned_positions(auto_close=auto_close)
        return {
            "status": "success",
            "message": f"Recovery check completed. auto_close={auto_close}"
        }
    except Exception as e:
        logger.error(f"Failed to recover positions: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.websocket("/ws/sessions")
async def websocket_sessions(websocket: WebSocket):
    """WebSocket endpoint for real-time session updates."""
    await websocket.accept()
    engine = get_engine()
    
    try:
        while True:
            # Send all session updates every 2 seconds
            sessions = engine.list_sessions()
            data = {
                "type": "sessions_update",
                "sessions": [s.to_dict() for s in sessions]
            }
            await websocket.send_text(json.dumps(data))
            await asyncio.sleep(2)
    except WebSocketDisconnect:
        logger.info("WebSocket disconnected")
    except Exception as e:
        logger.error(f"WebSocket error: {e}")

@router.websocket("/ws/sessions/{session_id}")
async def websocket_session_detail(websocket: WebSocket, session_id: str):
    """WebSocket endpoint for real-time updates of a specific session."""
    await websocket.accept()
    engine = get_engine()
    
    try:
        while True:
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
            await asyncio.sleep(1)  # More frequent updates for detail view
    except WebSocketDisconnect:
        logger.info(f"WebSocket disconnected for session {session_id}")
    except Exception as e:
        logger.error(f"WebSocket error for session {session_id}: {e}")


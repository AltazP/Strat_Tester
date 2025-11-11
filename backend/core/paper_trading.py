"""
Paper Trading Engine - Executes strategies in real-time with live OANDA data
"""
from __future__ import annotations
import asyncio
import logging
from datetime import datetime, timezone
from typing import Dict, Any, Optional, List
from dataclasses import dataclass, field, asdict
from enum import Enum

from strategies.base import Bar, Strategy, BacktestContext
from services.oanda_trading import OandaTradingClient
from services.oanda import fetch_candles

logger = logging.getLogger(__name__)

class TradingStatus(str, Enum):
    STOPPED = "stopped"
    STARTING = "starting"
    RUNNING = "running"
    PAUSED = "paused"
    ERROR = "error"
    STOPPING = "stopping"

@dataclass
class Position:
    """Represents a trading position."""
    instrument: str
    units: float  # positive = long, negative = short
    avg_price: float
    unrealized_pl: float = 0.0
    margin_used: float = 0.0
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

@dataclass
class Trade:
    """Represents a completed trade."""
    id: str
    instrument: str
    open_time: datetime
    close_time: Optional[datetime]
    open_price: float
    close_price: Optional[float]
    units: float
    realized_pl: float = 0.0
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "instrument": self.instrument,
            "open_time": self.open_time.isoformat() if self.open_time else None,
            "close_time": self.close_time.isoformat() if self.close_time else None,
            "open_price": self.open_price,
            "close_price": self.close_price,
            "units": self.units,
            "realized_pl": self.realized_pl,
        }

@dataclass
class PaperTradingSession:
    """Represents a paper trading session."""
    session_id: str
    account_id: str
    strategy_name: str
    strategy_params: Dict[str, Any]
    instrument: str
    granularity: str
    status: TradingStatus = TradingStatus.STOPPED
    
    # Account metrics
    initial_balance: float = 0.0
    current_balance: float = 0.0
    equity: float = 0.0
    unrealized_pl: float = 0.0
    realized_pl: float = 0.0
    margin_used: float = 0.0
    margin_available: float = 0.0
    
    # Trading stats
    total_trades: int = 0
    winning_trades: int = 0
    losing_trades: int = 0
    
    # Positions and trades
    positions: Dict[str, Position] = field(default_factory=dict)
    open_trades: Dict[str, Trade] = field(default_factory=dict)
    closed_trades: List[Trade] = field(default_factory=list)
    
    # Timestamps
    start_time: Optional[datetime] = None
    last_update: Optional[datetime] = None
    error_message: Optional[str] = None
    
    # Risk management
    max_position_size: float = 10000  # max units per position
    max_daily_loss: float = 1000  # max daily loss in account currency
    daily_loss: float = 0.0
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "session_id": self.session_id,
            "account_id": self.account_id,
            "strategy_name": self.strategy_name,
            "strategy_params": self.strategy_params,
            "instrument": self.instrument,
            "granularity": self.granularity,
            "status": self.status.value,
            "initial_balance": self.initial_balance,
            "current_balance": self.current_balance,
            "equity": self.equity,
            "unrealized_pl": self.unrealized_pl,
            "realized_pl": self.realized_pl,
            "margin_used": self.margin_used,
            "margin_available": self.margin_available,
            "total_trades": self.total_trades,
            "winning_trades": self.winning_trades,
            "losing_trades": self.losing_trades,
            "positions": {k: v.to_dict() for k, v in self.positions.items()},
            "open_trades_count": len(self.open_trades),
            "closed_trades_count": len(self.closed_trades),
            "start_time": self.start_time.isoformat() if self.start_time else None,
            "last_update": self.last_update.isoformat() if self.last_update else None,
            "error_message": self.error_message,
            "max_position_size": self.max_position_size,
            "max_daily_loss": self.max_daily_loss,
            "daily_loss": self.daily_loss,
        }

class PaperTradingEngine:
    """
    Manages paper trading sessions. Each session runs a strategy in real-time.
    """
    
    def __init__(self):
        self.sessions: Dict[str, PaperTradingSession] = {}
        self.running_tasks: Dict[str, asyncio.Task] = {}
        self.clients: Dict[str, OandaTradingClient] = {}
        
    def create_session(
        self,
        session_id: str,
        account_id: str,
        strategy_name: str,
        strategy_params: Dict[str, Any],
        instrument: str,
        granularity: str,
        max_position_size: float = 10000,
        max_daily_loss: float = 1000,
    ) -> PaperTradingSession:
        """Create a new paper trading session."""
        if session_id in self.sessions:
            raise ValueError(f"Session {session_id} already exists")
        
        session = PaperTradingSession(
            session_id=session_id,
            account_id=account_id,
            strategy_name=strategy_name,
            strategy_params=strategy_params,
            instrument=instrument,
            granularity=granularity,
            max_position_size=max_position_size,
            max_daily_loss=max_daily_loss,
        )
        
        self.sessions[session_id] = session
        self.clients[session_id] = OandaTradingClient(account_id=account_id)
        
        logger.info(f"Created paper trading session {session_id}")
        return session
    
    async def start_session(self, session_id: str, strategy_class: type[Strategy]):
        """Start a paper trading session."""
        if session_id not in self.sessions:
            raise ValueError(f"Session {session_id} not found")
        
        session = self.sessions[session_id]
        if session.status == TradingStatus.RUNNING:
            logger.warning(f"Session {session_id} is already running")
            return
        
        session.status = TradingStatus.STARTING
        session.start_time = datetime.now(timezone.utc)
        
        # Get initial account balance
        client = self.clients[session_id]
        try:
            account = await client.get_account_summary(session.account_id)
            session.initial_balance = float(account.get("balance", 0))
            session.current_balance = session.initial_balance
            session.equity = session.initial_balance
        except Exception as e:
            logger.error(f"Failed to get account balance: {e}")
            session.status = TradingStatus.ERROR
            session.error_message = str(e)
            return
        
        # Start trading loop in background
        task = asyncio.create_task(self._trading_loop(session_id, strategy_class))
        self.running_tasks[session_id] = task
        
        session.status = TradingStatus.RUNNING
        logger.info(f"Started paper trading session {session_id}")
    
    async def stop_session(self, session_id: str):
        """Stop a paper trading session."""
        if session_id not in self.sessions:
            raise ValueError(f"Session {session_id} not found")
        
        session = self.sessions[session_id]
        session.status = TradingStatus.STOPPING
        
        # Cancel the trading task
        if session_id in self.running_tasks:
            task = self.running_tasks[session_id]
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass
            del self.running_tasks[session_id]
        
        # Close all positions
        client = self.clients[session_id]
        try:
            positions = await client.get_positions(session.account_id)
            for pos in positions:
                instrument = pos.get("instrument")
                if instrument:
                    await client.close_position(instrument, session.account_id)
        except Exception as e:
            logger.error(f"Error closing positions: {e}")
        
        session.status = TradingStatus.STOPPED
        logger.info(f"Stopped paper trading session {session_id}")
    
    async def pause_session(self, session_id: str):
        """Pause a paper trading session (keep positions, stop new trades)."""
        if session_id not in self.sessions:
            raise ValueError(f"Session {session_id} not found")
        
        session = self.sessions[session_id]
        if session.status == TradingStatus.RUNNING:
            session.status = TradingStatus.PAUSED
            logger.info(f"Paused paper trading session {session_id}")
    
    async def resume_session(self, session_id: str):
        """Resume a paused paper trading session."""
        if session_id not in self.sessions:
            raise ValueError(f"Session {session_id} not found")
        
        session = self.sessions[session_id]
        if session.status == TradingStatus.PAUSED:
            session.status = TradingStatus.RUNNING
            logger.info(f"Resumed paper trading session {session_id}")
    
    def get_session(self, session_id: str) -> Optional[PaperTradingSession]:
        """Get a paper trading session."""
        return self.sessions.get(session_id)
    
    def list_sessions(self) -> List[PaperTradingSession]:
        """List all paper trading sessions."""
        return list(self.sessions.values())
    
    async def delete_session(self, session_id: str):
        """Delete a paper trading session."""
        if session_id in self.sessions:
            # Stop if running
            if self.sessions[session_id].status == TradingStatus.RUNNING:
                await self.stop_session(session_id)
            
            del self.sessions[session_id]
            if session_id in self.clients:
                del self.clients[session_id]
            
            logger.info(f"Deleted paper trading session {session_id}")
    
    async def _trading_loop(self, session_id: str, strategy_class: type[Strategy]):
        """Main trading loop for a session."""
        session = self.sessions[session_id]
        client = self.clients[session_id]
        
        # Initialize strategy
        strategy = strategy_class(session.strategy_params)
        ctx = BacktestContext(session.strategy_params)
        strategy.on_start(ctx)
        
        # Get historical data for warmup
        try:
            bars = await fetch_candles(
                instrument=session.instrument,
                granularity=session.granularity,
                count=100  # warmup with last 100 bars
            )
            
            # Run strategy on historical data
            for bar in bars:
                old_pos = ctx.position
                strategy.on_bar(bar, ctx)
                
                # Don't execute historical signals
                ctx.position = old_pos
        except Exception as e:
            logger.error(f"Error during warmup: {e}")
        
        # Granularity to seconds mapping
        granularity_seconds = {
            "S5": 5, "S10": 10, "S15": 15, "S30": 30,
            "M1": 60, "M2": 120, "M5": 300, "M15": 900, "M30": 1800,
            "H1": 3600, "H2": 7200, "H4": 14400,
            "D": 86400,
        }
        interval = granularity_seconds.get(session.granularity, 60)
        
        # Main trading loop
        try:
            while session.status in [TradingStatus.RUNNING, TradingStatus.PAUSED]:
                try:
                    # Update account metrics
                    await self._update_account_metrics(session_id)
                    
                    # If paused, skip trading logic
                    if session.status == TradingStatus.PAUSED:
                        await asyncio.sleep(5)
                        continue
                    
                    # Check risk limits
                    if session.daily_loss >= session.max_daily_loss:
                        logger.warning(f"Session {session_id} hit daily loss limit")
                        session.status = TradingStatus.PAUSED
                        continue
                    
                    # Fetch latest price
                    pricing = await client.get_pricing(
                        [session.instrument],
                        session.account_id
                    )
                    
                    if not pricing.get("prices"):
                        await asyncio.sleep(5)
                        continue
                    
                    price_data = pricing["prices"][0]
                    current_price = float(price_data["closeoutBid"])
                    
                    # Create a bar from current price (simplified - in production, accumulate OHLC)
                    bar = Bar(
                        ts=datetime.now(timezone.utc).timestamp(),
                        o=current_price,
                        h=current_price,
                        l=current_price,
                        c=current_price,
                    )
                    
                    # Run strategy
                    old_position = ctx.position
                    strategy.on_bar(bar, ctx)
                    new_position = ctx.position
                    
                    # Execute trades if position changed
                    if old_position != new_position:
                        await self._execute_position_change(
                            session_id,
                            old_position,
                            new_position,
                            current_price
                        )
                    
                    session.last_update = datetime.now(timezone.utc)
                    
                    # Wait for next bar
                    await asyncio.sleep(interval)
                    
                except asyncio.CancelledError:
                    raise
                except Exception as e:
                    logger.error(f"Error in trading loop for {session_id}: {e}")
                    session.error_message = str(e)
                    await asyncio.sleep(10)
                    
        except asyncio.CancelledError:
            logger.info(f"Trading loop cancelled for {session_id}")
        finally:
            strategy.on_stop(ctx)
    
    async def _execute_position_change(
        self,
        session_id: str,
        old_position: float,
        new_position: float,
        current_price: float
    ):
        """Execute position change via OANDA API."""
        session = self.sessions[session_id]
        client = self.clients[session_id]
        
        position_delta = new_position - old_position
        
        # Clamp to max position size
        if abs(new_position) > session.max_position_size:
            position_delta = session.max_position_size * (1 if new_position > 0 else -1) - old_position
        
        if abs(position_delta) < 1:  # Minimum trade size
            return
        
        try:
            # Execute market order
            result = await client.create_market_order(
                instrument=session.instrument,
                units=position_delta,
                account_id=session.account_id
            )
            
            logger.info(f"Executed order for {session_id}: {position_delta} units at ~{current_price}")
            
            # Update trade count
            session.total_trades += 1
            
        except Exception as e:
            logger.error(f"Failed to execute order for {session_id}: {e}")
            session.error_message = f"Order execution failed: {e}"
    
    async def _update_account_metrics(self, session_id: str):
        """Update session metrics from OANDA account."""
        session = self.sessions[session_id]
        client = self.clients[session_id]
        
        try:
            # Get account summary
            account = await client.get_account_summary(session.account_id)
            
            session.current_balance = float(account.get("balance", 0))
            session.equity = float(account.get("NAV", 0))
            session.unrealized_pl = float(account.get("unrealizedPL", 0))
            session.realized_pl = session.current_balance - session.initial_balance
            session.margin_used = float(account.get("marginUsed", 0))
            session.margin_available = float(account.get("marginAvailable", 0))
            
            # Get positions
            positions = await client.get_positions(session.account_id)
            session.positions = {}
            
            for pos in positions:
                instrument = pos.get("instrument")
                long_units = float(pos.get("long", {}).get("units", 0))
                short_units = float(pos.get("short", {}).get("units", 0))
                units = long_units + short_units
                
                if abs(units) > 0:
                    avg_price = float(pos.get("long" if long_units != 0 else "short", {}).get("averagePrice", 0))
                    unrealized = float(pos.get("unrealizedPL", 0))
                    
                    session.positions[instrument] = Position(
                        instrument=instrument,
                        units=units,
                        avg_price=avg_price,
                        unrealized_pl=unrealized,
                    )
            
            # Get trades for stats
            trades = await client.get_trades(session.account_id)
            session.open_trades = {}
            
            for trade in trades:
                trade_id = trade.get("id")
                if trade_id:
                    session.open_trades[trade_id] = Trade(
                        id=trade_id,
                        instrument=trade.get("instrument"),
                        open_time=datetime.fromisoformat(trade.get("openTime", "").replace("Z", "+00:00")),
                        close_time=None,
                        open_price=float(trade.get("price", 0)),
                        close_price=None,
                        units=float(trade.get("currentUnits", 0)),
                        realized_pl=float(trade.get("realizedPL", 0)),
                    )
            
        except Exception as e:
            logger.error(f"Failed to update metrics for {session_id}: {e}")

# Global engine instance
_engine: Optional[PaperTradingEngine] = None

def get_engine() -> PaperTradingEngine:
    """Get or create the global paper trading engine."""
    global _engine
    if _engine is None:
        _engine = PaperTradingEngine()
    return _engine


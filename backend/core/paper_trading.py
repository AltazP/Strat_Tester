"""
Paper Trading Engine - Executes strategies in real-time with live OANDA data
"""
from __future__ import annotations
import asyncio
import logging
import os
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
        try:
            logger.info(f"Initializing strategy {strategy_class.__name__} with params: {session.strategy_params}")
            strategy = strategy_class(session.strategy_params)
            ctx = BacktestContext(session.strategy_params)
            strategy.on_start(ctx)
            logger.info(f"Strategy initialized successfully for session {session_id}")
        except Exception as e:
            logger.error(f"Failed to initialize strategy: {e}", exc_info=True)
            session.status = TradingStatus.ERROR
            session.error_message = f"Strategy initialization failed: {str(e)}"
            raise
        
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
        bar_interval = granularity_seconds.get(session.granularity, 60)
        
        # Track the last completed bar timestamp
        last_bar_time = 0.0
        
        # Main trading loop
        try:
            while session.status in [TradingStatus.RUNNING, TradingStatus.PAUSED]:
                try:
                    # Update account metrics every 10 seconds
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
                    
                    # Fetch latest completed candle from OANDA
                    try:
                        latest_bars = await fetch_candles(
                            instrument=session.instrument,
                            granularity=session.granularity,
                            count=1
                        )
                        
                        if not latest_bars:
                            await asyncio.sleep(5)
                            continue
                        
                        latest_bar = latest_bars[-1]
                        
                        # Only process if this is a new bar
                        if latest_bar.ts <= last_bar_time:
                            await asyncio.sleep(5)
                            continue
                        
                        last_bar_time = latest_bar.ts
                        
                        # Log when processing a new bar (helps verify strategy is running)
                        logger.debug(f"Processing new bar for {session_id}: {session.instrument} @ {latest_bar.ts}")
                        
                        # Run strategy on the completed bar
                        old_position = ctx.position
                        strategy.on_bar(latest_bar, ctx)
                        new_position = ctx.position
                        
                        # Execute trades if position changed
                        if old_position != new_position:
                            logger.info(f"Position change for {session_id}: {old_position} → {new_position}")
                            # Get current price for execution
                            pricing = await client.get_pricing(
                                [session.instrument],
                                session.account_id
                            )
                            if pricing.get("prices"):
                                current_price = float(pricing["prices"][0]["closeoutBid"])
                            else:
                                current_price = latest_bar.c
                                
                            await self._execute_position_change(
                                session_id,
                                old_position,
                                new_position,
                                current_price
                            )
                        
                        session.last_update = datetime.now(timezone.utc)
                        
                    except Exception as e:
                        logger.error(f"Error fetching/processing candle: {e}")
                        await asyncio.sleep(10)
                        continue
                    
                    # Check for new bars more frequently than the bar interval
                    # This ensures we catch new bars quickly
                    check_interval = min(bar_interval / 4, 10)
                    await asyncio.sleep(check_interval)
                    
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
        
        # Convert strategy's relative position (e.g., 1.0, 2.0) to actual units
        # Strategy's position is a multiplier of max_position_size
        # Example: ctx.position = 1.0 with max_position_size = 10,000 → 10,000 units
        old_units = old_position * session.max_position_size
        new_units = new_position * session.max_position_size
        
        # Clamp to max position size (in case strategy wants more than 1.0x)
        if abs(new_units) > session.max_position_size:
            new_units = session.max_position_size * (1 if new_position > 0 else -1)
        
        position_delta = new_units - old_units
        
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
            
            # Don't increment total_trades here - it's recalculated from closed_trades + open_trades
            # This ensures accuracy even if trades close before we track them
            
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
            
            # Get open trades
            trades = await client.get_trades(session.account_id)
            
            # Track previous open trades before clearing
            previous_open_trades = session.open_trades.copy()
            previous_open_ids = set(previous_open_trades.keys())
            
            current_open_trade_ids = set()
            session.open_trades = {}
            
            for trade in trades:
                trade_id = trade.get("id")
                if trade_id:
                    current_open_trade_ids.add(trade_id)
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
            
            # Track trades that were open before but are now closed
            newly_closed_ids = previous_open_ids - current_open_trade_ids
            
            # Get closed trades from transactions (if session has a start time)
            if session.start_time:
                try:
                    transactions = await client.get_transactions(
                        session.account_id,
                        from_time=session.start_time.isoformat(),
                        page_size=500
                    )
                    
                    # Track which trades we've already seen as closed
                    existing_closed_ids = {t.id for t in session.closed_trades}
                    
                    # Process transactions to find closed trades
                    # Also look for ORDER_FILL transactions that might represent closed trades
                    for tx in transactions:
                        tx_type = tx.get("type")
                        trade_id = tx.get("tradeID")
                        
                        # Process TRADE_CLOSE transactions
                        if tx_type == "TRADE_CLOSE" and trade_id:
                            trade_id_str = str(trade_id)
                            if trade_id_str not in existing_closed_ids and trade_id_str not in current_open_trade_ids:
                                # This is a closed trade we haven't seen before
                                instrument = tx.get("instrument", session.instrument)
                                pl = float(tx.get("pl", 0))
                                close_price = float(tx.get("price", 0))
                                close_time_str = tx.get("time", "")
                                
                                # Try to find the opening transaction for this trade
                                open_price = close_price
                                units = 0.0
                                open_time_str = close_time_str
                                
                                # Look for the opening ORDER_FILL transaction
                                for open_tx in transactions:
                                    if (open_tx.get("tradeID") == trade_id and 
                                        open_tx.get("type") == "ORDER_FILL" and
                                        open_tx.get("id") != tx.get("id")):
                                        open_price = float(open_tx.get("price", open_price))
                                        units = float(open_tx.get("units", units))
                                        open_time_str = open_tx.get("time", open_time_str)
                                        break
                                
                                # If we couldn't find the open, try to get it from previous open_trades
                                if units == 0.0 and trade_id_str in previous_open_ids:
                                    prev_trade = previous_open_trades.get(trade_id_str)
                                    if prev_trade:
                                        open_price = prev_trade.open_price
                                        units = prev_trade.units
                                        open_time_str = prev_trade.open_time.isoformat()
                                
                                try:
                                    open_time = datetime.fromisoformat(open_time_str.replace("Z", "+00:00"))
                                    close_time = datetime.fromisoformat(close_time_str.replace("Z", "+00:00"))
                                    
                                    closed_trade = Trade(
                                        id=trade_id_str,
                                        instrument=instrument,
                                        open_time=open_time,
                                        close_time=close_time,
                                        open_price=open_price,
                                        close_price=close_price,
                                        units=units if units != 0.0 else float(tx.get("units", 0)),
                                        realized_pl=pl,
                                    )
                                    session.closed_trades.append(closed_trade)
                                    
                                    # Update stats
                                    if pl > 0:
                                        session.winning_trades += 1
                                    elif pl < 0:
                                        session.losing_trades += 1
                                except (ValueError, KeyError) as e:
                                    logger.warning(f"Failed to parse trade close transaction: {e}")
                except Exception as e:
                    logger.warning(f"Failed to fetch closed trades: {e}")
            
            # Recalculate winning/losing trades from closed_trades if they don't match
            # This ensures consistency even if trades were closed before tracking started
            actual_winning = sum(1 for t in session.closed_trades if t.realized_pl > 0)
            actual_losing = sum(1 for t in session.closed_trades if t.realized_pl < 0)
            
            # If we have closed trades but stats don't match, recalculate
            if len(session.closed_trades) > 0:
                if session.winning_trades != actual_winning or session.losing_trades != actual_losing:
                    logger.info(f"Recalculating win/loss stats for {session_id}: {actual_winning}W / {actual_losing}L")
                    session.winning_trades = actual_winning
                    session.losing_trades = actual_losing
            
            # Update total trades count - always recalculate from actual trades
            # This ensures consistency even if trades were closed before tracking started
            session.total_trades = len(session.closed_trades) + len(session.open_trades)
            
            # If we have realized P&L but no closed trades tracked, log a warning
            # This handles cases where trades closed before we started tracking
            if session.realized_pl != 0 and len(session.closed_trades) == 0 and len(session.open_trades) == 0:
                # If there's realized P&L but no trades, it means trades closed before tracking
                # We can't recover the individual trades, but we can at least indicate there was trading
                logger.warning(
                    f"Session {session_id} has realized P&L ({session.realized_pl:.2f}) but no tracked trades. "
                    f"Balance: {session.current_balance:.2f}, Initial: {session.initial_balance:.2f}. "
                    f"Trades may have closed before tracking started or transaction fetching failed."
                )
            
            # Log trade summary for debugging
            if len(session.closed_trades) > 0 or len(session.open_trades) > 0:
                logger.debug(
                    f"Session {session_id} trade summary: "
                    f"{len(session.closed_trades)} closed, {len(session.open_trades)} open, "
                    f"{session.winning_trades}W/{session.losing_trades}L, "
                    f"Realized P&L: {session.realized_pl:.2f}"
                )
            
        except Exception as e:
            logger.error(f"Failed to update metrics for {session_id}: {e}")

    async def recover_orphaned_positions(self, auto_close: bool = False):
        """
        Recover positions that exist on OANDA but aren't tracked in any session.
        This happens when the backend restarts while positions are open.
        
        Args:
            auto_close: If True, automatically close orphaned positions. 
                       If False, just log a warning.
        """
        logger.info("Checking for orphaned positions on startup...")
        
        try:
            # Try to get account from environment first
            account_id = os.getenv("OANDA_ACCOUNT_ID")
            
            # If not set, try to discover accounts
            if not account_id:
                logger.info("OANDA_ACCOUNT_ID not set, attempting to discover accounts...")
                try:
                    # Create temporary client to list accounts
                    temp_client = OandaTradingClient(account_id="")
                    accounts = await temp_client.get_accounts()
                    if not accounts:
                        logger.warning("No OANDA accounts found, skipping position recovery")
                        return
                    # Use the first account found
                    account_id = accounts[0].get("id")
                    if not account_id:
                        logger.warning("Could not determine account ID, skipping position recovery")
                        return
                    logger.info(f"Using account {account_id} for position recovery")
                except Exception as e:
                    logger.warning(f"Failed to discover accounts: {e}, skipping position recovery")
                    return
            
            client = OandaTradingClient(account_id=account_id)
            
            # Get all open positions from OANDA
            positions = await client.get_positions(account_id)
            
            if not positions:
                logger.info(f"No open positions found on OANDA account {account_id}")
                return
            
            # Check which positions are tracked in active sessions
            tracked_instruments = set()
            for session in self.sessions.values():
                if session.instrument:
                    tracked_instruments.add(session.instrument)
            
            orphaned_count = 0
            for pos in positions:
                instrument = pos.get("instrument", "UNKNOWN")
                
                # If this instrument is tracked in a session, it's not orphaned
                if instrument in tracked_instruments:
                    continue
                
                orphaned_count += 1
                long_units = float(pos.get("long", {}).get("units", 0))
                short_units = float(pos.get("short", {}).get("units", 0))
                units = long_units + short_units
                unrealized_pl = float(pos.get("unrealizedPL", 0))
                
                logger.warning(
                    f"Orphaned position on account {account_id}: {instrument} - {units} units, "
                    f"Unrealized P&L: {unrealized_pl:.2f}"
                )
                
                if auto_close:
                    try:
                        await client.close_position(instrument, account_id)
                        logger.info(f"Closed orphaned position: {instrument}")
                    except Exception as e:
                        logger.error(f"Failed to close position {instrument}: {e}")
                else:
                    logger.warning(
                        f"Position {instrument} remains open. "
                        f"Set auto_close=True to auto-close on startup, "
                        f"or manually close via POST /paper-trading/recover-positions?auto_close=true"
                    )
            
            if orphaned_count == 0:
                logger.info("All open positions are tracked in active sessions")
            else:
                logger.warning(
                    f"Found {orphaned_count} orphaned position(s). "
                    f"This likely means the backend restarted while positions were open."
                )
                    
        except Exception as e:
            logger.error(f"Error during position recovery: {e}", exc_info=True)

# Global engine instance
_engine: Optional[PaperTradingEngine] = None

def get_engine() -> PaperTradingEngine:
    """Get or create the global paper trading engine."""
    global _engine
    if _engine is None:
        _engine = PaperTradingEngine()
    return _engine


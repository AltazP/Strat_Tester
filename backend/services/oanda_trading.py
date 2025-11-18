"""
OANDA Trading API Client for Paper Trading
Handles account management, order execution, position tracking, and streaming prices.
"""
from __future__ import annotations
import os
import httpx
import asyncio
from typing import Dict, List, Optional, Any
from datetime import datetime
from enum import Enum

class OrderType(str, Enum):
    MARKET = "MARKET"
    LIMIT = "LIMIT"
    STOP = "STOP"
    MARKET_IF_TOUCHED = "MARKET_IF_TOUCHED"

class OrderSide(str, Enum):
    BUY = "buy"
    SELL = "sell"

def _get_oanda_cfg() -> tuple[str, str]:
    """Get OANDA configuration from environment."""
    host = (os.getenv("OANDA_HOST") or "https://api-fxpractice.oanda.com").rstrip("/")
    key = os.getenv("OANDA_PRACTICE_API_KEY")
    if not key:
        raise RuntimeError(
            "OANDA_PRACTICE_API_KEY is not set. "
            "Add it to backend/.env or export it in your shell."
        )
    return host, key

def _get_oanda_live_cfg() -> tuple[str, str]:
    """Get OANDA live trading configuration from environment."""
    host = (os.getenv("OANDA_LIVE_HOST") or "https://api-fxtrade.oanda.com").rstrip("/")
    key = os.getenv("OANDA_LIVE_API_KEY")
    if not key:
        raise RuntimeError(
            "OANDA_LIVE_API_KEY is not set. "
            "Add it to backend/.env or export it in your shell."
        )
    return host, key

class OandaTradingClient:
    """Full-featured OANDA trading client for paper trading."""
    
    def __init__(self, account_id: Optional[str] = None, live: bool = False):
        if live:
            self.host, self.api_key = _get_oanda_live_cfg()
            self.account_id = account_id or os.getenv("OANDA_LIVE_ACCOUNT_ID")
        else:
            self.host, self.api_key = _get_oanda_cfg()
            self.account_id = account_id or os.getenv("OANDA_ACCOUNT_ID")
        self.headers = {"Authorization": f"Bearer {self.api_key}"}
        
    async def _request(self, method: str, endpoint: str, **kwargs) -> Dict:
        """Make authenticated request to OANDA API."""
        url = f"{self.host}{endpoint}"
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.request(method, url, headers=self.headers, **kwargs)
            response.raise_for_status()
            return response.json()
    
    # ==================== ACCOUNT OPERATIONS ====================
    
    async def get_accounts(self) -> List[Dict[str, Any]]:
        """List all available accounts."""
        data = await self._request("GET", "/v3/accounts")
        return data.get("accounts", [])
    
    async def get_account_details(self, account_id: Optional[str] = None) -> Dict[str, Any]:
        """Get detailed account information including balance, P&L, positions."""
        acc_id = account_id or self.account_id
        if not acc_id:
            raise ValueError("No account_id provided")
        data = await self._request("GET", f"/v3/accounts/{acc_id}")
        return data.get("account", {})
    
    async def get_account_summary(self, account_id: Optional[str] = None) -> Dict[str, Any]:
        """Get account summary (lighter than full details)."""
        acc_id = account_id or self.account_id
        if not acc_id:
            raise ValueError("No account_id provided")
        data = await self._request("GET", f"/v3/accounts/{acc_id}/summary")
        return data.get("account", {})
    
    # ==================== ORDER OPERATIONS ====================
    
    async def create_market_order(
        self,
        instrument: str,
        units: float,
        account_id: Optional[str] = None,
        take_profit: Optional[float] = None,
        stop_loss: Optional[float] = None,
        trailing_stop: Optional[float] = None,
    ) -> Dict[str, Any]:
        """
        Create a market order.
        
        Args:
            instrument: e.g. "EUR_USD"
            units: positive for long, negative for short
            take_profit: take profit price
            stop_loss: stop loss price
            trailing_stop: trailing stop distance in price
        """
        acc_id = account_id or self.account_id
        if not acc_id:
            raise ValueError("No account_id provided")
        
        order_spec: Dict[str, Any] = {
            "type": "MARKET",
            "instrument": instrument,
            "units": str(int(units)),
            "timeInForce": "FOK",  # Fill or Kill
            "positionFill": "DEFAULT"
        }
        
        # Add stop loss and take profit if specified
        if take_profit:
            order_spec["takeProfitOnFill"] = {"price": str(take_profit)}
        if stop_loss:
            order_spec["stopLossOnFill"] = {"price": str(stop_loss)}
        if trailing_stop:
            order_spec["trailingStopLossOnFill"] = {"distance": str(trailing_stop)}
        
        data = await self._request(
            "POST",
            f"/v3/accounts/{acc_id}/orders",
            json={"order": order_spec}
        )
        return data
    
    async def create_limit_order(
        self,
        instrument: str,
        units: float,
        price: float,
        account_id: Optional[str] = None,
        take_profit: Optional[float] = None,
        stop_loss: Optional[float] = None,
    ) -> Dict[str, Any]:
        """Create a limit order."""
        acc_id = account_id or self.account_id
        if not acc_id:
            raise ValueError("No account_id provided")
        
        order_spec: Dict[str, Any] = {
            "type": "LIMIT",
            "instrument": instrument,
            "units": str(int(units)),
            "price": str(price),
            "timeInForce": "GTC",  # Good Till Cancelled
            "positionFill": "DEFAULT"
        }
        
        if take_profit:
            order_spec["takeProfitOnFill"] = {"price": str(take_profit)}
        if stop_loss:
            order_spec["stopLossOnFill"] = {"price": str(stop_loss)}
        
        data = await self._request(
            "POST",
            f"/v3/accounts/{acc_id}/orders",
            json={"order": order_spec}
        )
        return data
    
    async def close_position(
        self,
        instrument: str,
        account_id: Optional[str] = None,
        long_units: Optional[str] = None,
        short_units: Optional[str] = None
    ) -> Dict[str, Any]:
        """Close a position (or part of it).
        
        Args:
            instrument: The instrument to close
            account_id: Account ID (optional if set in client)
            long_units: Units to close for long side ("ALL" or number as string, None to omit)
            short_units: Units to close for short side ("ALL" or number as string, None to omit)
        """
        acc_id = account_id or self.account_id
        if not acc_id:
            raise ValueError("No account_id provided")
        
        # Build request body - only include fields that are specified
        # OANDA requires at least one of longUnits or shortUnits
        body: Dict[str, str] = {}
        if long_units is not None:
            body["longUnits"] = long_units
        if short_units is not None:
            body["shortUnits"] = short_units
        
        # If neither is specified, default to closing all
        if not body:
            body = {"longUnits": "ALL", "shortUnits": "ALL"}
        
        data = await self._request(
            "PUT",
            f"/v3/accounts/{acc_id}/positions/{instrument}/close",
            json=body
        )
        return data
    
    async def cancel_order(self, order_id: str, account_id: Optional[str] = None) -> Dict[str, Any]:
        """Cancel a pending order."""
        acc_id = account_id or self.account_id
        if not acc_id:
            raise ValueError("No account_id provided")
        
        data = await self._request(
            "PUT",
            f"/v3/accounts/{acc_id}/orders/{order_id}/cancel"
        )
        return data
    
    async def get_orders(self, account_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """Get all pending orders."""
        acc_id = account_id or self.account_id
        if not acc_id:
            raise ValueError("No account_id provided")
        
        data = await self._request("GET", f"/v3/accounts/{acc_id}/pendingOrders")
        return data.get("orders", [])
    
    # ==================== POSITION OPERATIONS ====================
    
    async def get_positions(self, account_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """Get all open positions."""
        acc_id = account_id or self.account_id
        if not acc_id:
            raise ValueError("No account_id provided")
        
        data = await self._request("GET", f"/v3/accounts/{acc_id}/openPositions")
        return data.get("positions", [])
    
    async def get_position(self, instrument: str, account_id: Optional[str] = None) -> Dict[str, Any]:
        """Get position for specific instrument."""
        acc_id = account_id or self.account_id
        if not acc_id:
            raise ValueError("No account_id provided")
        
        data = await self._request("GET", f"/v3/accounts/{acc_id}/positions/{instrument}")
        return data.get("position", {})
    
    # ==================== TRADE OPERATIONS ====================
    
    async def get_trades(self, account_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """Get all open trades."""
        acc_id = account_id or self.account_id
        if not acc_id:
            raise ValueError("No account_id provided")
        
        data = await self._request("GET", f"/v3/accounts/{acc_id}/openTrades")
        return data.get("trades", [])
    
    async def close_trade(self, trade_id: str, account_id: Optional[str] = None, units: str = "ALL") -> Dict[str, Any]:
        """Close a specific trade."""
        acc_id = account_id or self.account_id
        if not acc_id:
            raise ValueError("No account_id provided")
        
        data = await self._request(
            "PUT",
            f"/v3/accounts/{acc_id}/trades/{trade_id}/close",
            json={"units": units}
        )
        return data
    
    # ==================== PRICING OPERATIONS ====================
    
    async def get_pricing(
        self,
        instruments: List[str],
        account_id: Optional[str] = None,
        since: Optional[str] = None
    ) -> Dict[str, Any]:
        """Get current pricing for instruments."""
        acc_id = account_id or self.account_id
        if not acc_id:
            raise ValueError("No account_id provided")
        
        params = {"instruments": ",".join(instruments)}
        if since:
            params["since"] = since
        
        data = await self._request(
            "GET",
            f"/v3/accounts/{acc_id}/pricing",
            params=params
        )
        return data
    
    async def stream_pricing(
        self,
        instruments: List[str],
        account_id: Optional[str] = None,
        callback = None
    ):
        """
        Stream real-time pricing. 
        
        Args:
            instruments: list of instruments to stream
            callback: async function to call with each price update
        """
        acc_id = account_id or self.account_id
        if not acc_id:
            raise ValueError("No account_id provided")
        
        stream_host = self.host.replace("api-fxpractice", "stream-fxpractice")
        url = f"{stream_host}/v3/accounts/{acc_id}/pricing/stream"
        params = {"instruments": ",".join(instruments)}
        
        async with httpx.AsyncClient(timeout=None) as client:
            async with client.stream("GET", url, headers=self.headers, params=params) as response:
                response.raise_for_status()
                async for line in response.aiter_lines():
                    if line.strip():
                        try:
                            import json
                            data = json.loads(line)
                            if callback:
                                await callback(data)
                        except json.JSONDecodeError:
                            continue
    
    # ==================== TRANSACTION OPERATIONS ====================
    
    async def get_transactions(
        self,
        account_id: Optional[str] = None,
        from_time: Optional[str] = None,
        to_time: Optional[str] = None,
        page_size: int = 100
    ) -> List[Dict[str, Any]]:
        """Get transaction history."""
        acc_id = account_id or self.account_id
        if not acc_id:
            raise ValueError("No account_id provided")
        
        params: Dict[str, Any] = {"pageSize": page_size}
        if from_time:
            params["from"] = from_time
        if to_time:
            params["to"] = to_time
        
        data = await self._request(
            "GET",
            f"/v3/accounts/{acc_id}/transactions",
            params=params
        )
        return data.get("transactions", [])
    
    async def get_transaction_range(
        self,
        from_id: str,
        to_id: str,
        account_id: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Get transactions in a specific ID range."""
        acc_id = account_id or self.account_id
        if not acc_id:
            raise ValueError("No account_id provided")
        
        data = await self._request(
            "GET",
            f"/v3/accounts/{acc_id}/transactions/idrange",
            params={"from": from_id, "to": to_id}
        )
        return data.get("transactions", [])


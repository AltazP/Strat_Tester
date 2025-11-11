from __future__ import annotations
import os
import httpx
from typing import List, Optional
from strategies.base import Bar

def _get_oanda_cfg() -> tuple[str, str]:
    """
    Read env at call time so changes to .env / process env are respected.
    """
    host = (os.getenv("OANDA_HOST") or "https://api-fxpractice.oanda.com").rstrip("/")
    key = os.getenv("OANDA_PRACTICE_API_KEY")
    if not key:
        raise RuntimeError(
            "OANDA_PRACTICE_API_KEY is not set. "
            "Add it to backend/.env or export it in your shell."
        )
    return host, key

async def fetch_candles(
    instrument: str, 
    granularity: str, 
    count: Optional[int] = None,
    start: Optional[str] = None,
    end: Optional[str] = None
) -> List[Bar]:
    """
    Fetch candles from OANDA. Either provide `count` for lookback, 
    or `start`/`end` for a date range.
    """
    host, key = _get_oanda_cfg()
    url = f"{host}/v3/instruments/{instrument}/candles"
    headers = {"Authorization": f"Bearer {key}"}
    params = {"granularity": granularity, "price": "M"}
    
    if start and end:
        params["from"] = start
        params["to"] = end
    else:
        params["count"] = str(count or 500)

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            r = await client.get(url, headers=headers, params=params)
    except httpx.HTTPError as e:
        raise RuntimeError(f"Failed to reach OANDA: {e}") from e

    if r.status_code == 401:
        raise RuntimeError("OANDA auth failed (401). Check OANDA_PRACTICE_API_KEY.")
    if r.status_code == 404:
        raise RuntimeError(f"Instrument not found or endpoint not available: {instrument}")

    r.raise_for_status()
    data = r.json()

    bars: List[Bar] = []
    for c in data.get("candles", []):
        if not c.get("complete"):
            continue
        t = c["time"]
        ts = _iso_to_epoch(t)
        mid = c["mid"]
        bars.append(
            Bar(
                ts=ts,
                o=float(mid["o"]),
                h=float(mid["h"]),
                l=float(mid["l"]),
                c=float(mid["c"]),
            )
        )
    return bars

def _iso_to_epoch(s: str) -> float:
    from datetime import datetime, timezone
    # "2024-01-01T00:00:00.000000000Z" -> truncate fractional part
    s = s.replace("Z", "").split(".")[0]
    dt = datetime.fromisoformat(s).replace(tzinfo=timezone.utc)
    return dt.timestamp()

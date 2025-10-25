from __future__ import annotations
import os
from dataclasses import dataclass
from dotenv import load_dotenv

load_dotenv()

@dataclass(frozen=True)
class Settings:
    BACKEND_HOST: str = os.getenv("BACKEND_HOST", "127.0.0.1")
    BACKEND_PORT: int = int(os.getenv("BACKEND_PORT", "8000"))
    ENABLE_TRADING: bool = os.getenv("ENABLE_TRADING", "false").lower() == "true"

    # OANDA VARS
    OANDA_PRACTICE_API_KEY: str | None = os.getenv("OANDA_PRACTICE_API_KEY")
    OANDA_ACCOUNT_ID: str | None = os.getenv("OANDA_ACCOUNT_ID")
    OANDA_HOST: str = os.getenv("OANDA_HOST", "api-fxpractice.oanda.com")
    OANDA_STREAM_HOST: str = os.getenv("OANDA_STREAM_HOST", "stream-fxpractice.oanda.com")

settings = Settings()
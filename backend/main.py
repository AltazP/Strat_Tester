from __future__ import annotations
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv
from api.routes import router as api_router
from util.logging import setup_logging
import logging

# Load .env BEFORE anything uses os.getenv(...)
load_dotenv()

setup_logging()
logger = logging.getLogger(__name__)

app = FastAPI(title="Strategy Lab API")

# Dev CORS: allow all (no cookies with "*")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,   # MUST be False when using "*"
    allow_methods=["*"],
    allow_headers=["*"],
)

# optional health check for quick header tests
@app.get("/ping")
def ping():
    return {"ok": True}

# mount your API
app.include_router(api_router)

@app.on_event("startup")
async def startup_event():
    """Run recovery logic on startup to handle orphaned positions."""
    try:
        import os
        from core.paper_trading import get_engine
        
        # Only attempt recovery if OANDA credentials are properly configured
        if not os.getenv("OANDA_PRACTICE_API_KEY"):
            logger.warning("OANDA_PRACTICE_API_KEY not set - skipping position recovery")
            return
            
        engine = get_engine()
        
        # Check for orphaned positions (positions on OANDA but not tracked in sessions)
        # Set auto_close=False to just log warnings, or True to auto-close on startup
        # You can change this based on your preference
        await engine.recover_orphaned_positions(auto_close=False)
        logger.info("Startup recovery check completed")
    except Exception as e:
        logger.error(f"Error during startup recovery: {e}", exc_info=True)

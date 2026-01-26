from __future__ import annotations
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv
from api.routes import router as api_router
from util.logging import setup_logging
import logging
import sys
import traceback
from datetime import datetime, timezone

# Load .env BEFORE anything uses os.getenv(...)
load_dotenv()

setup_logging()
logger = logging.getLogger(__name__)

# Global exception handler to prevent crashes
def handle_exception(exc_type, exc_value, exc_traceback):
    """Handle unhandled exceptions globally to prevent crashes."""
    if issubclass(exc_type, KeyboardInterrupt):
        sys.__excepthook__(exc_type, exc_value, exc_traceback)
        return
    
    logger.critical(
        "Unhandled exception",
        exc_info=(exc_type, exc_value, exc_traceback)
    )

sys.excepthook = handle_exception

app = FastAPI(title="Strategy Lab API")

# Dev CORS: allow all (no cookies with "*")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,   # MUST be False when using "*"
    allow_methods=["*"],
    allow_headers=["*"],
)

# Exception handler middleware to catch all unhandled exceptions
@app.exception_handler(Exception)
async def global_exception_handler(request, exc):
    """Catch all unhandled exceptions to prevent server crashes."""
    logger.error(f"Unhandled exception in request {request.method} {request.url}: {exc}", exc_info=True)
    from fastapi.responses import JSONResponse
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error. Check logs for details."}
    )

# Health check endpoint for monitoring/load balancers
@app.get("/ping")
def ping():
    return {"ok": True}

@app.get("/health")
async def health_check():
    """Comprehensive health check endpoint."""
    try:
        from core.paper_trading import get_engine
        
        # Check if engine is responsive
        engine = get_engine()
        session_count = len(engine.sessions)
        running_sessions = sum(1 for s in engine.sessions.values() if s.status.value == "running")
        
        # Try to get memory info if psutil is available
        memory_mb = None
        memory_ok = True
        try:
            import psutil
            process = psutil.Process()
            memory_info = process.memory_info()
            memory_mb = memory_info.rss / 1024 / 1024
            memory_ok = memory_mb < 512
        except ImportError:
            # psutil not installed, skip memory check
            pass
        except Exception:
            # Memory check failed, but don't fail health check
            pass
        
        return {
            "status": "healthy" if memory_ok else "degraded",
            "memory_mb": round(memory_mb, 2) if memory_mb is not None else None,
            "memory_ok": memory_ok,
            "sessions": {
                "total": session_count,
                "running": running_sessions
            },
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
    except Exception as e:
        logger.error(f"Health check failed: {e}", exc_info=True)
        return {
            "status": "unhealthy",
            "error": str(e),
            "timestamp": datetime.now(timezone.utc).isoformat()
        }, 503

# mount your API
app.include_router(api_router)

@app.on_event("startup")
async def startup_event():
    """Run recovery logic on startup to handle orphaned positions."""
    try:
        import os
        import asyncio
        from core.paper_trading import get_engine
        
        # Only attempt recovery if OANDA credentials are properly configured
        if not os.getenv("OANDA_PRACTICE_API_KEY"):
            logger.warning("OANDA_PRACTICE_API_KEY not set - skipping position recovery")
            return
            
        engine = get_engine()
        
        # Check for orphaned positions with timeout to prevent startup hangs
        # Set auto_close=False to just log warnings, or True to auto-close on startup
        try:
            await asyncio.wait_for(
                engine.recover_orphaned_positions(auto_close=False),
                timeout=10.0  # 10 second timeout
            )
        except asyncio.TimeoutError:
            logger.warning("Position recovery timed out - continuing startup anyway")
    except Exception as e:
        logger.error(f"Error during startup recovery: {e}", exc_info=True)
        # Don't re-raise - allow startup to continue even if recovery fails

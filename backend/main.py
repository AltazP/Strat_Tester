from __future__ import annotations
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv  # <-- add
from api.routes import router as api_router
from util.logging import setup_logging

# Load .env BEFORE anything uses os.getenv(...)
load_dotenv()

setup_logging()

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

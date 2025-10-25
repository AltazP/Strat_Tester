from __future__ import annotations
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from api.routes import router as api_router
from util.logging import setup_logging

setup_logging()

app = FastAPI(title="Strategy Lab API")

# Explicit origins for local dev UI
ALLOWED_ORIGINS = ["http://localhost:3000", "http://127.0.0.1:3000"]

app.add_middleware(
  CORSMiddleware,
  allow_origins=ALLOWED_ORIGINS,
  allow_methods=["*"],
  allow_headers=["*"],
  allow_credentials=True,
)

app.include_router(api_router)

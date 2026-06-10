"""FastAPI application entry point."""
from __future__ import annotations

import os
import sys
from pathlib import Path

# Ensure engine package is importable
_engine_path = str(Path(__file__).resolve().parents[2] / "packages" / "nse_engine")
if _engine_path not in sys.path:
    sys.path.insert(0, _engine_path)

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager

from db import create_tables
from routers import upload, configure, run, results, export


@asynccontextmanager
async def lifespan(app: FastAPI):
    create_tables()
    yield


app = FastAPI(title="NSE Multiverse Tool", version="0.1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(upload.router, prefix="/api")
app.include_router(configure.router, prefix="/api")
app.include_router(run.router, prefix="/api")
app.include_router(results.router, prefix="/api")
app.include_router(export.router, prefix="/api")


@app.get("/api/health")
def health() -> dict:
    return {"status": "ok"}

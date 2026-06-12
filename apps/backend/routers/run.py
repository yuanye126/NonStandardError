"""POST /api/run — enqueue multiverse job; GET /api/run/{run_id}/status."""
from __future__ import annotations

import json
import os
import sys
import uuid
from pathlib import Path

import redis
import rq
from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.orm import Session

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "packages" / "nse_engine"))

from db import get_db, Dataset, Run
from jobs import run_multiverse_job

router = APIRouter()

REDIS_URL = os.environ.get("REDIS_URL", "")   # empty = no Redis, use threading
OUTPUT_DIR = os.environ.get("OUTPUT_DIR", "/tmp/nse_outputs")

_redis_conn: redis.Redis | None = None
_queue: rq.Queue | None = None


def _get_queue() -> rq.Queue:
    global _redis_conn, _queue
    if _queue is None:
        _redis_conn = redis.from_url(REDIS_URL)
        _queue = rq.Queue("nse", connection=_redis_conn, default_timeout=600)
    return _queue


def _use_redis() -> bool:
    """True only when REDIS_URL is set AND Redis is actually reachable."""
    if not REDIS_URL:
        return False
    try:
        r = redis.from_url(REDIS_URL)
        r.ping()
        return True
    except Exception:
        return False


_REDIS_AVAILABLE: bool = _use_redis()


@router.post("/run")
async def start_run(body: dict, db: Session = Depends(get_db)):
    dataset_id = body.get("dataset_id")
    if not dataset_id:
        raise HTTPException(status_code=422, detail="dataset_id required")

    record = db.query(Dataset).filter(Dataset.id == dataset_id).first()
    if not record:
        raise HTTPException(status_code=404, detail="Dataset not found")

    config_dict = body.get("config", body)
    # Inject the server-side data path
    if "dataset" not in config_dict:
        config_dict["dataset"] = {}
    config_dict["dataset"]["path"] = record.storage_path
    config_dict["dataset"]["format"] = record.format

    run_id = str(uuid.uuid4())
    run_rec = Run(id=run_id, dataset_id=dataset_id, config_json=json.dumps(config_dict))
    db.add(run_rec)
    db.commit()

    if _REDIS_AVAILABLE:
        _get_queue().enqueue(
            run_multiverse_job,
            run_id,
            config_dict,
            OUTPUT_DIR,
            job_id=run_id,
        )
    else:
        import threading
        threading.Thread(
            target=run_multiverse_job,
            args=(run_id, config_dict, OUTPUT_DIR),
            daemon=True,
        ).start()

    return {"run_id": run_id}


@router.get("/run/{run_id}/status")
async def run_status(run_id: str, db: Session = Depends(get_db)):
    run_rec = db.query(Run).filter(Run.id == run_id).first()
    if not run_rec:
        raise HTTPException(status_code=404, detail="Run not found")

    return {
        "run_id": run_id,
        "state": run_rec.state,
        "progress": run_rec.progress,
        "n_done": run_rec.n_done,
        "n_total": run_rec.n_total,
        "failure_message": run_rec.failure_message,
    }

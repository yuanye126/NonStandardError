"""GET /api/results/{run_id} — return aggregated results JSON."""
from __future__ import annotations

import json
import sys
from pathlib import Path

from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.orm import Session

from db import get_db, Run

router = APIRouter()


@router.get("/results/{run_id}")
async def get_results(run_id: str, db: Session = Depends(get_db)):
    run_rec = db.query(Run).filter(Run.id == run_id).first()
    if not run_rec:
        raise HTTPException(status_code=404, detail="Run not found")
    if run_rec.state != "done":
        raise HTTPException(
            status_code=202,
            detail=f"Run is {run_rec.state}. Poll /api/run/{run_id}/status.",
        )
    if not run_rec.results_json:
        raise HTTPException(status_code=500, detail="Results not available")
    return json.loads(run_rec.results_json)

"""GET /api/export/{run_id} — stream the replication zip."""
from __future__ import annotations

import json
import sys
from pathlib import Path

from fastapi import APIRouter, HTTPException, Depends
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from db import get_db, Run, Dataset
from export_builder import build_export_zip

router = APIRouter()


@router.get("/export/{run_id}")
async def export_run(run_id: str, db: Session = Depends(get_db)):
    run_rec = db.query(Run).filter(Run.id == run_id).first()
    if not run_rec:
        raise HTTPException(status_code=404, detail="Run not found")
    if run_rec.state != "done":
        raise HTTPException(status_code=400, detail="Run has not completed")

    dataset = db.query(Dataset).filter(Dataset.id == run_rec.dataset_id).first()
    if not dataset:
        raise HTTPException(status_code=404, detail="Dataset not found")

    config_dict = json.loads(run_rec.config_json)

    # Combos CSV path (if it was saved alongside the parquet)
    parquet_path = run_rec.parquet_path or ""
    combos_path = parquet_path.replace("results.parquet", "combos.csv")
    combos_path = combos_path if Path(combos_path).exists() else None

    zip_bytes = build_export_zip(
        config_dict=config_dict,
        data_path=dataset.storage_path,
        parquet_path=parquet_path,
        combos_csv_path=combos_path,
    )

    return StreamingResponse(
        iter([zip_bytes]),
        media_type="application/zip",
        headers={
            "Content-Disposition": f'attachment; filename="nse_replication_{run_id[:8]}.zip"'
        },
    )

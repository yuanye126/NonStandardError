"""POST /api/upload — accept CSV/XLSX up to 20 MB, return column inventory."""
from __future__ import annotations

import io
import json
import os
import sys
import uuid
from pathlib import Path

import pandas as pd
from fastapi import APIRouter, HTTPException, UploadFile, File, Depends
from sqlalchemy.orm import Session

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "packages" / "nse_engine"))

from db import get_db, Dataset

router = APIRouter()

UPLOAD_DIR = os.environ.get("UPLOAD_DIR", "/tmp/nse_uploads")
MAX_SIZE_BYTES = 20 * 1024 * 1024  # 20 MB


def _col_stats(df: pd.DataFrame) -> list[dict]:
    stats = []
    for col in df.columns:
        s = df[col]
        stats.append({
            "name": col,
            "dtype": str(s.dtype),
            "n_missing": int(s.isna().sum()),
            "n_zero": int((s == 0).sum()) if pd.api.types.is_numeric_dtype(s) else 0,
            "n_unique": int(s.nunique()),
            "zero_share": float((s == 0).mean()) if pd.api.types.is_numeric_dtype(s) else 0.0,
            "missing_share": float(s.isna().mean()),
        })
    return stats


@router.post("/upload")
async def upload_dataset(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    content = await file.read()

    if len(content) > MAX_SIZE_BYTES:
        raise HTTPException(
            status_code=413,
            detail=f"File exceeds 20 MB limit ({len(content) / 1_048_576:.1f} MB uploaded). "
                   "Please upload a smaller dataset.",
        )

    filename = file.filename or "upload"
    suffix = Path(filename).suffix.lower()
    if suffix not in (".csv", ".xlsx", ".xls"):
        raise HTTPException(
            status_code=422,
            detail="Only CSV and XLSX files are supported.",
        )
    fmt = "xlsx" if suffix in (".xlsx", ".xls") else "csv"

    try:
        if fmt == "csv":
            df = pd.read_csv(io.BytesIO(content))
        else:
            df = pd.read_excel(io.BytesIO(content))
    except Exception as exc:
        raise HTTPException(status_code=422, detail=f"Could not parse file: {exc}")

    dataset_id = str(uuid.uuid4())
    storage_dir = Path(UPLOAD_DIR)
    storage_dir.mkdir(parents=True, exist_ok=True)
    storage_path = str(storage_dir / f"{dataset_id}.{fmt}")
    with open(storage_path, "wb") as f:
        f.write(content)

    col_info = _col_stats(df)

    record = Dataset(
        id=dataset_id,
        original_filename=filename,
        storage_path=storage_path,
        format=fmt,
        n_rows=len(df),
        columns_json=json.dumps(col_info),
    )
    db.add(record)
    db.commit()

    return {
        "dataset_id": dataset_id,
        "columns": col_info,
        "n_rows": len(df),
    }

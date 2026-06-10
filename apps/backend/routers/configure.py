"""POST /api/configure/validate — validate config, return n_specs + runtime estimate."""
from __future__ import annotations

import json
import random
import sys
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "packages" / "nse_engine"))

import pandas as pd

from nse_engine.config import Config, ConfigValidationError, compute_n_specs
from nse_engine.combos import generate_combinations
from db import get_db, Dataset

router = APIRouter()

# Timing constants (seconds per spec per row, calibrated empirically)
_TIMING = {
    "OLS": 2e-6,
    "RLM": 4e-6,
    "2SLS": 1e-5,
    "Hurdle": 1.5e-5,
}
WEB_SAMPLE_SIZE = 20000
WEB_MAX_RUNTIME_S = 90


@router.post("/configure/validate")
async def validate_config(
    body: dict,
    db: Session = Depends(get_db),
):
    dataset_id = body.get("dataset_id")
    if not dataset_id:
        raise HTTPException(status_code=422, detail="dataset_id required")

    record = db.query(Dataset).filter(Dataset.id == dataset_id).first()
    if not record:
        raise HTTPException(status_code=404, detail="Dataset not found")

    columns = [c["name"] for c in json.loads(record.columns_json)]

    errors: list[str] = []
    warnings: list[str] = []
    try:
        config = Config.from_dict(body.get("config", body))
        config.validate(columns=columns)
    except ConfigValidationError as exc:
        errors = exc.errors
    except Exception as exc:
        errors = [str(exc)]

    if errors:
        return {"valid": False, "errors": errors, "warnings": [],
                "n_specs": None, "est_runtime_s": None, "will_sample": None}

    # Auto-clamp min_variables to the number of available IVs
    n_ivs = len(config.roles.independent)
    if config.variable_selection.min_variables > n_ivs:
        config.variable_selection.min_variables = max(2, n_ivs)
        warnings.append(
            f"min_variables clamped to {config.variable_selection.min_variables} "
            f"(only {n_ivs} independent variables selected)."
        )

    # Load data to count combos
    n_combos, combo_warning = _estimate_combos(record, config)
    if combo_warning:
        warnings.append(combo_warning)

    n_specs = compute_n_specs(config, n_combos)

    n_rows = record.n_rows
    est_s = sum(
        _TIMING.get(m, 3e-6) * n_rows * min(n_specs, WEB_SAMPLE_SIZE)
        for m in config.design_space.models
    )

    will_sample = n_specs > WEB_SAMPLE_SIZE or est_s > WEB_MAX_RUNTIME_S

    return {
        "valid": True,
        "errors": [],
        "warnings": warnings,
        "n_specs": n_specs,
        "n_combos": n_combos,
        "est_runtime_s": round(est_s, 1),
        "will_sample": will_sample,
        "sample_size": WEB_SAMPLE_SIZE if will_sample else n_specs,
    }


def _estimate_combos(record: Dataset, config: Config) -> tuple[int, str | None]:
    """Return (n_combos, optional_warning)."""
    try:
        fmt = record.format
        if fmt == "csv":
            df = pd.read_csv(record.storage_path, nrows=500)
        else:
            df = pd.read_excel(record.storage_path, nrows=500)

        combos = generate_combinations(df, config.roles.independent, config.variable_selection,
                                       rng=random.Random(config.run.seed))
        n = len(combos)
        warning = None
        if n == 0:
            warning = (
                "No variable combinations satisfy the correlation filter "
                f"(max_correlation={config.variable_selection.max_correlation}). "
                "Try raising max_correlation or selecting more independent variables."
            )
        elif n < 10:
            warning = (
                f"Only {n} variable combination(s) passed the correlation filter. "
                "Consider raising max_correlation for a richer multiverse."
            )
        return n, warning
    except Exception as exc:
        fallback = max(1, config.variable_selection.target_combinations // 10)
        return fallback, f"Combo estimation failed ({exc}); using rough estimate."

"""RQ task wrappers for async multiverse runs."""
from __future__ import annotations

import json
import os
import sys
from datetime import datetime
from pathlib import Path

# Ensure the engine package is importable from the worker
_engine_path = str(Path(__file__).resolve().parents[2] / "packages" / "nse_engine")
if _engine_path not in sys.path:
    sys.path.insert(0, _engine_path)

from nse_engine import Config, run_multiverse, aggregate


def run_multiverse_job(run_id: str, config_dict: dict, output_dir: str) -> None:
    """RQ job: run the multiverse and update the DB record."""
    # Import DB here (worker process)
    from db import SessionLocal, Run

    db = SessionLocal()

    def _set(run: Run, **kwargs) -> None:
        for k, v in kwargs.items():
            setattr(run, k, v)
        db.commit()

    run_rec = db.query(Run).filter(Run.id == run_id).first()
    if not run_rec:
        return

    _set(run_rec, state="running")

    try:
        config = Config.from_dict(config_dict)
        parquet_path = str(Path(output_dir) / run_id / "results.parquet")
        Path(parquet_path).parent.mkdir(parents=True, exist_ok=True)

        # Progress callback — updates DB periodically
        def progress(done: int, total: int) -> None:
            pct = done / total if total > 0 else 0
            _set(run_rec, progress=pct, n_done=done, n_total=total)

        result = run_multiverse(config, progress_callback=progress, output_path=parquet_path)

        agg = aggregate(
            parquet_path=parquet_path,
            config_dict=config_dict,
            n_specs_run=result["n_specs_run"],
            n_specs_total=result["n_specs_total"],
            sampled=result["sampled"],
            failure_stats=result["failure_stats"],
        )

        _set(
            run_rec,
            state="done",
            parquet_path=parquet_path,
            results_json=json.dumps(agg, default=str),
            n_done=result["n_specs_run"],
            n_total=result["n_specs_total"],
            progress=1.0,
            finished_at=datetime.utcnow(),
        )

    except Exception as exc:
        _set(
            run_rec,
            state="failed",
            failure_message=str(exc),
            finished_at=datetime.utcnow(),
        )
        raise

    finally:
        db.close()

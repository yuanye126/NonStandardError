"""
run_multiverse(config) — orchestrates the full pipeline:
  load data → build/load combos → expand specs → sample if needed → run in parallel → write Parquet
"""
from __future__ import annotations

import itertools
import os
import random
import time
from collections import Counter
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path
from typing import Any, Callable, Optional

import numpy as np
import pandas as pd

from .combos import generate_combinations, save_combinations, load_combinations
from .config import Config, compute_n_specs
from .processor import RegressionProcessor
from .sampling import sample_specs


# ---------------------------------------------------------------------------
# Spec expansion
# ---------------------------------------------------------------------------

def _expand_specs(config: Config, combos: list[list[str]]) -> list[dict]:
    """Cartesian product of all design-space factors × variable combos."""
    ds = config.design_space
    specs = []
    for combo in combos:
        for dep_na in ds.dep_na_treatment:
            for dep_out in ds.dep_outlier:
                for dep_tr in ds.dep_transform:
                    for ind_na in ds.ind_na_treatment:
                        for ind_out in ds.ind_outlier:
                            for ind_tr in ds.ind_transform:
                                for fe in ds.fixed_effects:
                                    specs.append({
                                        "ind_vars": combo,
                                        "dep_na_treatment": dep_na,
                                        "dep_outlier": dep_out,
                                        "dep_transform": dep_tr,
                                        "ind_na_treatment": ind_na,
                                        "ind_outlier": ind_out,
                                        "ind_transform": ind_tr,
                                        "fixed_effects": fe,
                                        "models": ds.models,
                                    })
    return specs


# ---------------------------------------------------------------------------
# Worker (top-level so it can be pickled by ProcessPoolExecutor)
# ---------------------------------------------------------------------------

def _run_one_spec(args: tuple) -> tuple[list[dict], str | None]:
    """Worker function: (data_bytes, config_dict, spec) → (results, failure_reason)"""
    import io
    import json
    data_bytes, config_dict, spec = args
    df = pd.read_parquet(io.BytesIO(data_bytes))
    cfg = Config.from_dict(config_dict)
    proc = RegressionProcessor(df, cfg)
    try:
        results = proc.run_spec(spec)
        return results, None
    except ValueError as exc:
        return [], str(exc).split(":")[0].strip()
    except Exception as exc:
        return [], f"unexpected_error"


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

def run_multiverse(
    config: Config,
    progress_callback: Optional[Callable[[int, int], None]] = None,
    output_path: Optional[str] = None,
) -> dict:
    """
    Run the multiverse.

    Returns:
        {
            "parquet_path": str,
            "n_specs_run": int,
            "n_specs_total": int,
            "sampled": bool,
            "failure_stats": dict,
            "elapsed_s": float,
        }
    """
    t0 = time.time()

    # 1. Load data
    data_path = config.dataset.path
    fmt = config.dataset.format
    if fmt == "csv":
        data = pd.read_csv(data_path)
    elif fmt == "xlsx":
        data = pd.read_excel(data_path)
    else:
        raise ValueError(f"Unknown format: {fmt}")

    # 2. Build / load variable combinations
    vs = config.variable_selection
    candidates = config.roles.independent
    if vs.precomputed_combos_path and Path(vs.precomputed_combos_path).exists():
        combos = load_combinations(vs.precomputed_combos_path)
    else:
        rng = random.Random(config.run.seed)
        combos = generate_combinations(data, candidates, vs, rng=rng)

    if not combos:
        raise ValueError("No valid variable combinations generated")

    # Save combos alongside the parquet so the export can reference them
    if output_path:
        combos_path = str(Path(output_path).with_name("combos.csv"))
        save_combinations(combos, combos_path)

    # 3. Expand full spec list
    all_specs = _expand_specs(config, combos)
    n_total = compute_n_specs(config, len(combos))

    # 4. Sample if needed
    sampled = False
    run_mode = config.run.mode
    sample_size = config.run.sample_size
    if run_mode == "sample" and len(all_specs) > sample_size:
        all_specs = sample_specs(all_specs, sample_size, config.run.seed)
        sampled = True
    n_run = len(all_specs)

    # 5. Serialize data once (avoid repeated pickling)
    import io
    buf = io.BytesIO()
    data.to_parquet(buf, index=False)
    data_bytes = buf.getvalue()
    config_dict = config.to_dict()

    # 6. Run in parallel
    max_workers = config.run.max_workers or max(1, (os.cpu_count() or 2) - 1)
    failure_stats: Counter = Counter()
    rows: list[dict] = []

    with ProcessPoolExecutor(max_workers=max_workers) as exe:
        futures = {exe.submit(_run_one_spec, (data_bytes, config_dict, spec)): i
                   for i, spec in enumerate(all_specs)}
        done = 0
        for fut in as_completed(futures):
            results, failure = fut.result()
            done += 1
            if failure:
                failure_stats[failure] += 1
            else:
                rows.extend(results)
            if progress_callback and done % max(1, n_run // 100) == 0:
                progress_callback(done, n_run)

    # 7. Write Parquet
    if output_path is None:
        output_path = "results.parquet"
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)

    if rows:
        results_df = _rows_to_df(rows)
        results_df.to_parquet(output_path, index=False)
    else:
        pd.DataFrame().to_parquet(output_path, index=False)

    elapsed = time.time() - t0

    return {
        "parquet_path": output_path,
        "n_specs_run": n_run,
        "n_specs_total": n_total,
        "sampled": sampled,
        "failure_stats": dict(failure_stats),
        "elapsed_s": elapsed,
    }


# ---------------------------------------------------------------------------
# Row normalization
# ---------------------------------------------------------------------------

def _rows_to_df(rows: list[dict]) -> pd.DataFrame:
    """Flatten nested dicts (params, bse, pvalues, ci_low, ci_high) into columns."""
    flat_rows = []
    for r in rows:
        flat: dict[str, Any] = {}
        # Copy scalar fields
        for k, v in r.items():
            if k in ("params", "bse", "pvalues", "ci_low", "ci_high", "marginal_effects",
                     "probit_params", "probit_pvalues", "ind_vars", "fixed_effects",
                     "dep_outlier", "ind_na_treatment", "ind_outlier"):
                continue
            if isinstance(v, (dict, list)):
                import json
                flat[k] = json.dumps(v)
            else:
                flat[k] = v

        # Expand per-coefficient fields
        params = r.get("params", {})
        bse = r.get("bse", {})
        pvalues = r.get("pvalues", {})
        ci_low = r.get("ci_low", {})
        ci_high = r.get("ci_high", {})
        for name, coef in params.items():
            if name == "const":
                continue
            flat[f"coef_{name}"] = coef
            flat[f"se_{name}"] = bse.get(name)
            flat[f"pval_{name}"] = pvalues.get(name)
            flat[f"ci_low_{name}"] = ci_low.get(name)
            flat[f"ci_high_{name}"] = ci_high.get(name)

        # Store ind_vars as JSON string
        flat["ind_vars"] = ",".join(r.get("ind_vars", []))

        # Store FE spec as JSON
        import json
        flat["fixed_effects"] = json.dumps(r.get("fixed_effects", {}))
        flat["dep_outlier"] = json.dumps(r.get("dep_outlier", {}))
        flat["ind_na_treatment"] = json.dumps(r.get("ind_na_treatment", {}))
        flat["ind_outlier"] = json.dumps(r.get("ind_outlier", {}))

        flat_rows.append(flat)

    return pd.DataFrame(flat_rows)

"""
aggregate.py — Compute NSE statistics from spec-row Parquet.

Definitions follow the paper exactly:
  NSE of quantity = IQR across specifications (Q3 − Q1)
  SE = mean of per-spec reported standard errors
  Ratio = NSE / SE
"""
from __future__ import annotations

import json
from typing import Any, Optional

import numpy as np
import pandas as pd


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _iqr(s: pd.Series) -> float:
    q1, q3 = s.quantile([0.25, 0.75])
    return float(q3 - q1)


def _safe_div(a: float, b: float) -> Optional[float]:
    if b == 0 or np.isnan(b) or np.isnan(a):
        return None
    return float(a / b)


# ---------------------------------------------------------------------------
# Variance decomposition
# ---------------------------------------------------------------------------

_FACTOR_COLS = [
    "dep_na_treatment",
    "dep_transform",
    "ind_transform",
    "model_type",
    # JSON-encoded columns decoded below
    "dep_outlier_str",
    "ind_outlier_str",
    "ind_na_treatment_str",
    "fixed_effects_str",
]


def _variance_decomp(df: pd.DataFrame, coef_col: str) -> dict[str, float]:
    """
    Regress coef_col on one-hot dummies for each factor.
    Return R² contribution of each factor (sequential, Type I SS).
    """
    import statsmodels.api as sm

    sub = df[[coef_col] + [c for c in _FACTOR_COLS if c in df.columns]].dropna(
        subset=[coef_col]
    )
    if len(sub) < 10:
        return {}

    y = sub[coef_col].values
    total_ss = float(np.var(y) * len(y))
    if total_ss < 1e-12:
        return {}

    shares: dict[str, float] = {}
    explained_so_far = 0.0
    X_cumul = pd.DataFrame({"const": np.ones(len(sub))})

    for fac in _FACTOR_COLS:
        if fac not in sub.columns:
            continue
        dummies = pd.get_dummies(sub[fac].astype(str), prefix=fac, drop_first=True)
        X_new = pd.concat([X_cumul, dummies], axis=1)
        if X_new.shape[1] <= X_cumul.shape[1]:
            continue
        try:
            res_new = sm.OLS(y, X_new.values.astype(float)).fit()
            r2_new = max(0.0, float(res_new.rsquared))
            shares[fac.replace("_str", "")] = max(0.0, r2_new - explained_so_far)
            explained_so_far = r2_new
            X_cumul = X_new
        except Exception:
            pass

    # Normalize to sum to 1
    total = sum(shares.values())
    if total > 0:
        shares = {k: v / total for k, v in shares.items()}
    return shares


# ---------------------------------------------------------------------------
# Per-factor IQR (paper Table 6 style)
# ---------------------------------------------------------------------------

def _by_factor_iqr(df: pd.DataFrame, coef_col: str) -> dict[str, float]:
    """Return IQR of coef grouped by each factor level (mean of group IQRs)."""
    result: dict[str, float] = {}
    for fac in _FACTOR_COLS:
        if fac not in df.columns:
            continue
        col = fac.replace("_str", "")
        try:
            grp = df.groupby(fac)[coef_col].apply(_iqr)
            result[col] = float(grp.mean())
        except Exception:
            pass
    return result


# ---------------------------------------------------------------------------
# Spec curve data
# ---------------------------------------------------------------------------

def _spec_curve_points(
    df: pd.DataFrame,
    coef_col: str,
    se_col: str,
    focal_name: str,
    max_points: int = 5000,
) -> list[dict]:
    sub = df[[coef_col, se_col] + [c for c in _FACTOR_COLS if c in df.columns]].dropna(
        subset=[coef_col]
    )
    sub = sub.sort_values(coef_col).reset_index(drop=True)

    if len(sub) > max_points:
        sub = sub.iloc[:: len(sub) // max_points + 1]

    points = []
    for rank, (_, row) in enumerate(sub.iterrows()):
        est = float(row[coef_col])
        se = float(row.get(se_col, np.nan))
        ci_low = est - 1.96 * se if not np.isnan(se) else None
        ci_high = est + 1.96 * se if not np.isnan(se) else None
        factors = {}
        for fac in _FACTOR_COLS:
            if fac in row.index:
                factors[fac.replace("_str", "")] = str(row[fac])
        points.append({
            "rank": rank + 1,
            "estimate": est,
            "ci_low": ci_low,
            "ci_high": ci_high,
            "factors": factors,
        })
    return points


# ---------------------------------------------------------------------------
# Hurdle comparison (Table 11)
# ---------------------------------------------------------------------------

def _hurdle_comparison(df: pd.DataFrame, focal_coefficients: list[str]) -> dict:
    has_hurdle = "Hurdle" in df["model_type"].values if "model_type" in df.columns else False
    if not has_hurdle:
        return {"available": False}

    rows_out = []
    for name in focal_coefficients:
        coef_col = f"coef_{name}"
        se_col = f"se_{name}"
        if coef_col not in df.columns:
            continue

        for model in ["OLS", "RLM", "2SLS_IMR", "2SLS_GR", "2SLS_IMRGR"]:
            sub = df[df["model_type"] == model]
            if coef_col not in sub.columns or sub[coef_col].dropna().empty:
                continue
            iqr_v = _iqr(sub[coef_col].dropna())
            median_v = float(sub[coef_col].dropna().median())
            ratio = _safe_div(iqr_v, abs(median_v)) if median_v != 0 else None

            hurdle_sub = df[df["model_type"] == "Hurdle"]
            if coef_col in hurdle_sub.columns and not hurdle_sub[coef_col].dropna().empty:
                h_iqr = _iqr(hurdle_sub[coef_col].dropna())
                h_med = float(hurdle_sub[coef_col].dropna().median())
                h_ratio = _safe_div(h_iqr, abs(h_med)) if h_med != 0 else None
                delta = _safe_div(h_ratio - ratio, ratio) if ratio and h_ratio else None
            else:
                h_ratio = None
                delta = None

            rows_out.append({
                "name": name,
                "model": model,
                "iqr_med": ratio,
                "iqr_med_hurdle": h_ratio,
                "delta": delta,
            })

    # MPE summaries
    mpe: dict = {"unconditional": {}, "conditional": {}}
    for model in ["OLS", "RLM"]:
        sub = df[df["model_type"] == model]
        if "mean_fitted" in sub.columns and not sub["mean_fitted"].dropna().empty:
            mpe["unconditional"][model.lower()] = float(sub["mean_fitted"].median())

    return {
        "available": True,
        "rows": rows_out,
        "mpe": mpe,
    }


# ---------------------------------------------------------------------------
# Main entry
# ---------------------------------------------------------------------------

def aggregate(
    parquet_path: str,
    config_dict: dict,
    n_specs_run: int,
    n_specs_total: int,
    sampled: bool,
    failure_stats: dict,
) -> dict:
    """Produce the full results JSON from the Parquet spec rows."""
    df = pd.read_parquet(parquet_path)

    if df.empty:
        return {
            "meta": {
                "n_specs_run": n_specs_run,
                "n_specs_total": n_specs_total,
                "sampled": sampled,
                "models": config_dict.get("design_space", {}).get("models", []),
                "failure_stats": failure_stats,
            },
            "predictions": None,
            "coefficients": [],
            "spec_curve": None,
            "hurdle": {"available": False},
        }

    # Decode JSON-encoded columns into string labels for groupby
    for json_col, label in [
        ("dep_outlier", "dep_outlier_str"),
        ("ind_outlier", "ind_outlier_str"),
        ("ind_na_treatment", "ind_na_treatment_str"),
        ("fixed_effects", "fixed_effects_str"),
    ]:
        if json_col in df.columns:
            df[label] = df[json_col].astype(str)

    focal_coefficients: list[str] = config_dict.get("focal_coefficients", [])
    if not focal_coefficients:
        # Auto-detect from coef_ columns
        focal_coefficients = [
            c[5:] for c in df.columns
            if c.startswith("coef_") and not c.startswith("coef_const")
        ][:5]

    # Predictions NSE/SE/ratio
    predictions = None
    if "mean_fitted" in df.columns:
        pred_series = df["mean_fitted"].dropna()
        nse = _iqr(pred_series)
        mean_se = float(df["mean_se"].dropna().mean()) if "mean_se" in df.columns else None
        ratio = _safe_div(nse, mean_se) if mean_se else None
        predictions = {"nse": nse, "se": mean_se, "ratio": ratio}

    # Per-coefficient stats
    coefficients = []
    first_focal = None
    for name in focal_coefficients:
        coef_col = f"coef_{name}"
        se_col = f"se_{name}"
        if coef_col not in df.columns:
            continue

        coef_series = df[coef_col].dropna()
        if coef_series.empty:
            continue

        if first_focal is None:
            first_focal = name

        nse = _iqr(coef_series)
        mean_se = float(df[se_col].dropna().mean()) if se_col in df.columns else None
        ratio = _safe_div(nse, mean_se) if mean_se else None

        pct_pos = float((coef_series > 0).mean())
        pct_neg = float((coef_series < 0).mean())
        pval_col = f"pval_{name}"
        pct_sig = float((df[pval_col] < 0.05).mean()) if pval_col in df.columns else None

        var_shares = _variance_decomp(df, coef_col)
        by_factor = _by_factor_iqr(df, coef_col)

        coefficients.append({
            "name": name,
            "nse": nse,
            "se": mean_se,
            "ratio": ratio,
            "pct_positive": pct_pos,
            "pct_negative": pct_neg,
            "pct_sig": pct_sig,
            "by_factor": by_factor,
            "variance_share": var_shares,
        })

    # Spec curve for the first focal coefficient
    spec_curve = None
    if first_focal:
        coef_col = f"coef_{first_focal}"
        se_col = f"se_{first_focal}"
        if coef_col in df.columns:
            spec_curve = {
                "coefficient": first_focal,
                "points": _spec_curve_points(df, coef_col, se_col, first_focal),
            }

    # Hurdle comparison
    hurdle = _hurdle_comparison(df, focal_coefficients)

    return {
        "meta": {
            "n_specs_run": n_specs_run,
            "n_specs_total": n_specs_total,
            "sampled": sampled,
            "models": config_dict.get("design_space", {}).get("models", []),
            "failure_stats": failure_stats,
        },
        "predictions": predictions,
        "coefficients": coefficients,
        "spec_curve": spec_curve,
        "hurdle": hurdle,
    }

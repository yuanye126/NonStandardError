"""
Series-level data transformations: winsorize, truncate, z-score, mean-center.
These are stateless functions; no dataset-specific logic lives here.
"""
from __future__ import annotations

import numpy as np
import pandas as pd


def winsorize_series(s: pd.Series, threshold: float, symmetric: str = "both") -> pd.Series:
    """Winsorize a series at the given quantile threshold.

    symmetric: 'both' | 'lower' | 'upper'
    """
    s = s.copy()
    if symmetric in ("both", "lower"):
        lower = s.quantile(threshold)
        s = s.clip(lower=lower)
    if symmetric in ("both", "upper"):
        upper = s.quantile(1 - threshold)
        s = s.clip(upper=upper)
    return s


def truncate_series(s: pd.Series, threshold: float, symmetric: str = "both") -> pd.Series:
    """Truncate (drop) rows outside the given quantile threshold."""
    mask = pd.Series(True, index=s.index)
    if symmetric in ("both", "lower"):
        lower = s.quantile(threshold)
        mask &= s >= lower
    if symmetric in ("both", "upper"):
        upper = s.quantile(1 - threshold)
        mask &= s <= upper
    return s[mask]


def transform_series(s: pd.Series, method: str) -> pd.Series:
    """Apply a named transformation to a series.

    method: 'none' | 'zscore' | 'mean_center' | 'log' | 'log1p'
    """
    if method == "none":
        return s
    if method == "zscore":
        std = s.std(ddof=1)
        if std == 0:
            return s - s.mean()
        return (s - s.mean()) / std
    if method == "mean_center":
        return s - s.mean()
    if method == "log":
        return np.log(s.clip(lower=1e-9))
    if method == "log1p":
        return np.log1p(s.clip(lower=0))
    raise ValueError(f"Unknown transform method: {method!r}")


def apply_outlier_treatment(s: pd.Series, spec: dict) -> pd.Series:
    """Apply the outlier treatment spec dict to a series.

    spec shape: {"apply": bool, "method": str, "threshold": float, "symmetric": str}
    Returns the (possibly shorter) treated series.
    """
    if not spec.get("apply", False):
        return s
    method = spec["method"]
    threshold = spec["threshold"]
    symmetric = spec.get("symmetric", "both")
    if method == "winsorize":
        return winsorize_series(s, threshold, symmetric)
    if method == "truncate":
        return truncate_series(s, threshold, symmetric)
    raise ValueError(f"Unknown outlier method: {method!r}")

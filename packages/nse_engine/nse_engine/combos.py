"""
Variable combination generation with correlation filter.
All parameters come from VariableSelectionConfig — no hardcoded lists.
"""
from __future__ import annotations

import itertools
import random
from pathlib import Path
from typing import Optional

import numpy as np
import pandas as pd

from .config import VariableSelectionConfig


def _pairwise_correlation_ok(
    data: pd.DataFrame,
    vars: list[str],
    max_corr: float,
) -> bool:
    """Return True if no pair in vars has |rho| >= max_corr."""
    if len(vars) < 2:
        return True
    sub = data[vars].dropna()
    if len(sub) < 5:
        return True
    corr = sub.corr(method="pearson").abs()
    # upper triangle excluding diagonal
    for i in range(len(vars)):
        for j in range(i + 1, len(vars)):
            if corr.iloc[i, j] >= max_corr:
                return False
    return True


def _max_pairwise_corr(data: pd.DataFrame, vars: list[str]) -> float:
    """Return the maximum absolute pairwise correlation among vars."""
    if len(vars) < 2:
        return 0.0
    sub = data[vars].dropna()
    if len(sub) < 5:
        return 0.0
    corr = sub.corr(method="pearson").abs()
    max_c = 0.0
    for i in range(len(vars)):
        for j in range(i + 1, len(vars)):
            max_c = max(max_c, corr.iloc[i, j])
    return max_c


def generate_combinations(
    data: pd.DataFrame,
    candidates: list[str],
    vs_config: VariableSelectionConfig,
    rng: Optional[random.Random] = None,
) -> list[list[str]]:
    """Generate variable combinations satisfying min_variables, max_correlation,
    and required_vars constraints, up to target_combinations.

    If precomputed_combos_path is set, reads from that CSV instead.

    When the strict correlation filter yields no combos (e.g. all variables are
    highly collinear), the function falls back to returning the combos with the
    lowest maximum pairwise correlation, so the UI always shows a non-zero count.
    """
    if vs_config.precomputed_combos_path:
        path = Path(vs_config.precomputed_combos_path)
        df = pd.read_csv(path, header=None)
        return [row.dropna().tolist() for _, row in df.iterrows()]

    required = vs_config.required_vars
    all_candidates = [v for v in candidates if v in data.columns]
    optional = [v for v in all_candidates if v not in required]

    # Clamp min_variables to what's actually available
    n_available = len(required) + len(optional)
    min_v = min(max(vs_config.min_variables, len(required)), n_available)
    if min_v < 1:
        return []

    target = vs_config.target_combinations
    max_corr = vs_config.max_correlation

    if rng is None:
        rng = random.Random(42)

    max_v = min(n_available, min_v + 6)

    combos: list[list[str]] = []
    seen: set[frozenset] = set()

    optional_needed = min_v - len(required)
    total_optional = len(optional)

    if total_optional < optional_needed:
        # Not enough optional variables — use everything we have
        combo = sorted(required + optional)
        if _pairwise_correlation_ok(data, combo, max_corr):
            combos.append(combo)
        return combos

    # Count feasible combos across all sizes
    total_possible = sum(
        len(list(itertools.combinations(optional, k)))
        for k in range(optional_needed, max_v - len(required) + 1)
        if k <= total_optional
    )

    if total_possible <= target * 3:
        for k in range(optional_needed, max_v - len(required) + 1):
            if k > total_optional:
                break
            for chosen in itertools.combinations(optional, k):
                combo = sorted(required + list(chosen))
                key = frozenset(combo)
                if key in seen:
                    continue
                if _pairwise_correlation_ok(data, combo, max_corr):
                    seen.add(key)
                    combos.append(combo)
                    if len(combos) >= target:
                        return combos
    else:
        attempts = 0
        max_attempts = target * 20
        while len(combos) < target and attempts < max_attempts:
            attempts += 1
            k = rng.randint(optional_needed, max_v - len(required))
            k = min(k, total_optional)
            chosen = rng.sample(optional, k)
            combo = sorted(required + chosen)
            key = frozenset(combo)
            if key in seen:
                continue
            if _pairwise_correlation_ok(data, combo, max_corr):
                seen.add(key)
                combos.append(combo)

    # Fallback: if strict filter yielded nothing, return the least-correlated
    # combos found — better than returning 0 and blocking the user entirely.
    if not combos:
        fallback_candidates: list[tuple[float, list[str]]] = []
        n_fallback_tries = min(200, total_possible if total_possible <= 10000 else 200)
        if total_possible <= n_fallback_tries * 2:
            # Enumerate small spaces
            for k in range(optional_needed, min(optional_needed + 2, total_optional + 1)):
                for chosen in itertools.combinations(optional, k):
                    combo = sorted(required + list(chosen))
                    mc = _max_pairwise_corr(data, combo)
                    fallback_candidates.append((mc, combo))
                    if len(fallback_candidates) >= n_fallback_tries:
                        break
                if len(fallback_candidates) >= n_fallback_tries:
                    break
        else:
            rng2 = random.Random(vs_config.__hash__() if hasattr(vs_config, '__hash__') else 0)
            for _ in range(n_fallback_tries):
                k = rng2.randint(optional_needed, min(optional_needed + 2, total_optional))
                chosen = rng2.sample(optional, k)
                combo = sorted(required + chosen)
                mc = _max_pairwise_corr(data, combo)
                fallback_candidates.append((mc, combo))

        if fallback_candidates:
            fallback_candidates.sort(key=lambda x: x[0])
            seen2: set[frozenset] = set()
            for _, combo in fallback_candidates[:target]:
                key = frozenset(combo)
                if key not in seen2:
                    seen2.add(key)
                    combos.append(combo)

    return combos


def save_combinations(combos: list[list[str]], path: str) -> None:
    """Save combinations to CSV (one row per combo, variable-length columns)."""
    max_len = max(len(c) for c in combos) if combos else 0
    rows = [c + [""] * (max_len - len(c)) for c in combos]
    pd.DataFrame(rows).to_csv(path, header=False, index=False)


def load_combinations(path: str) -> list[list[str]]:
    """Load combinations from CSV saved by save_combinations."""
    df = pd.read_csv(path, header=None, dtype=str)
    return [row.replace("", pd.NA).dropna().tolist() for _, row in df.iterrows()]

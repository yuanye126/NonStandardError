"""
Sobol / quasi-random sampling of the full spec list for the web preview (mode: sample).
"""
from __future__ import annotations

import hashlib
import random
from typing import Any


def _sobol_indices(n_total: int, sample_size: int, seed: int) -> list[int]:
    """
    Return `sample_size` indices in [0, n_total) via Sobol sequence when scipy
    is available, falling back to seeded random sampling.
    """
    if sample_size >= n_total:
        return list(range(n_total))

    try:
        from scipy.stats.qmc import Sobol
        # Sobol requires dimension >= 1 and sample count as power-of-2 for best uniformity.
        # We use 1-D Sobol to get uniform coverage across the index space.
        m = (sample_size - 1).bit_length()  # ceil log2
        sampler = Sobol(d=1, scramble=True, seed=seed)
        raw = sampler.random_base2(m)  # shape (2**m, 1)
        indices = (raw[:, 0] * n_total).astype(int).clip(0, n_total - 1).tolist()
        # Deduplicate while preserving order
        seen: set[int] = set()
        unique: list[int] = []
        for idx in indices:
            if idx not in seen:
                seen.add(idx)
                unique.append(idx)
        # If deduplication reduced count, pad with random
        if len(unique) < sample_size:
            rng = random.Random(seed + 1)
            remaining = [i for i in range(n_total) if i not in seen]
            rng.shuffle(remaining)
            unique.extend(remaining[: sample_size - len(unique)])
        return unique[:sample_size]
    except Exception:
        rng = random.Random(seed)
        return rng.sample(range(n_total), min(sample_size, n_total))


def sample_specs(
    specs: list[Any],
    sample_size: int,
    seed: int,
) -> list[Any]:
    """Return a reproducible sample of `specs` of length `sample_size`."""
    if sample_size >= len(specs):
        return specs
    indices = _sobol_indices(len(specs), sample_size, seed)
    return [specs[i] for i in indices]

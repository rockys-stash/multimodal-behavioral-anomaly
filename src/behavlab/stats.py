"""Aggregation over people: mean with a bootstrap interval, and paired tests with Holm correction."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

import numpy as np
from numpy.typing import NDArray
from scipy.stats import wilcoxon


def mean_ci(values: list[float | None], seed: int = 0, n_boot: int = 2000) -> dict[str, Any]:
    """Mean over people and a percentile bootstrap 95% interval (resampling people)."""
    x: NDArray[np.float64] = np.array([v for v in values if v is not None and np.isfinite(v)], dtype=np.float64)
    if len(x) == 0:
        return {"n": 0, "mean": None, "lo": None, "hi": None}
    rng = np.random.default_rng(seed)
    boots = rng.choice(x, size=(n_boot, len(x)), replace=True).mean(axis=1) if len(x) > 1 else x
    return {"n": len(x), "mean": float(x.mean()), "lo": float(np.quantile(boots, 0.025)),
            "hi": float(np.quantile(boots, 0.975))}  # fmt: skip


def paired(a: Mapping[str, float | None], b: Mapping[str, float | None]) -> dict[str, Any]:
    """Wilcoxon signed-rank test of b - a over people that have both values."""
    keys = [k for k in a if a[k] is not None and b.get(k) is not None]
    d: NDArray[np.float64] = np.array([b[k] - a[k] for k in keys], dtype=np.float64)  # type: ignore[operator]
    if len(d) < 5 or not np.any(d):
        return {"n": len(d), "mean_diff": float(d.mean()) if len(d) else None, "p": None}
    res = wilcoxon(d)
    return {"n": len(d), "mean_diff": float(d.mean()), "median_diff": float(np.median(d)),
            "better": int((d > 0).sum()), "worse": int((d < 0).sum()), "p": float(res.pvalue)}  # fmt: skip


def holm(ps: list[float | None]) -> list[float | None]:
    idx = [i for i, p in enumerate(ps) if p is not None]
    order = sorted(idx, key=lambda i: ps[i])  # type: ignore[arg-type,return-value]
    out: list[float | None] = [None] * len(ps)
    running = 0.0
    m = len(order)
    for rank, i in enumerate(order):
        adj = min(1.0, (m - rank) * ps[i])  # type: ignore[operator]
        running = max(running, adj)
        out[i] = running
    return out

"""Score one person with one model and detector, and measure detection.

Metrics (docs/METRICS.md), all on the person's test minutes whose truth is determined:

- precision, recall, F1 and false-positive rate of the per-minute alarms at the reference threshold;
- AUROC of the raw score (threshold-free);
- event recall: share of anomaly events with at least one alarm inside the event;
- detection latency: minutes from an event's first minute to its first alarm, over detected events;
- false alarms per hour: alarms on normal minutes, per hour of normal minutes.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np
from numpy.typing import NDArray
from sklearn.metrics import roc_auc_score

from behavlab import detectors
from behavlab.data import UserData
from behavlab.fusion import MODELS, available, fuse
from behavlab.truth import KIND, Truth, events, ground_truth

Array = NDArray[np.float64]
MIN_REFERENCE = 200  # minutes of usable reference data a person needs to be evaluated


@dataclass
class Scored:
    uuid: str
    model: str
    detector: str
    rows: NDArray[np.int64]  # minute indices (into the person's data) that were scored
    score: Array  # score per scored minute
    thr: float
    truth: Truth
    contributions: dict[str, Array] | None = None  # kNN only: per-modality share per scored minute
    reference_scores: Array | None = None  # out-of-sample scores of the reference minutes

    @property
    def alarm(self) -> NDArray[np.bool_]:
        return self.score > self.thr


def score_user(
    u: UserData,
    model: str,
    detector: str,
    seed: int = 0,
    truth: Truth | None = None,
    restrict: tuple[str, ...] | None = None,
    block_weighting: bool = True,
    explain: bool = False,
    k: int = 10,
) -> Scored | None:
    """Fit on reference minutes, score test minutes. ``restrict`` limits both to minutes that have
    every modality in it, so models are compared on the same minutes. None if too little data."""
    mods = MODELS[model]
    truth = truth or ground_truth(u)
    ok = available(u, restrict or mods)
    ref_rows = np.flatnonzero(truth.reference & ok)
    test_rows = np.flatnonzero(truth.test & ok)
    if len(ref_rows) < MIN_REFERENCE or len(test_rows) == 0:
        return None
    fit = np.zeros(u.n, dtype=bool)
    fit[ref_rows] = True
    fused = fuse(u, mods, fit, block_weighting)
    X_ref, X_test = fused.X[ref_rows], fused.X[test_rows]
    day = u.day()[ref_rows]
    half = day <= np.median(day)
    ref_scores = detectors.reference_scores(detector, X_ref, half, seed, k)
    thr = float(np.quantile(ref_scores, 1 - detectors.ALARM_RATE))
    det = detectors.make(detector, seed, k).fit(X_ref)
    s = det.score(X_test)
    contrib = None
    if explain and isinstance(det, detectors.KNN):
        contrib = det.contributions(X_test, fused.blocks)
    return Scored(u.uuid, model, detector, test_rows, s, thr, truth, contrib, ref_scores)


def measure(sc: Scored, ts: NDArray[np.int64], alarms: NDArray[np.bool_] | None = None) -> dict[str, Any]:
    """Detection metrics; ``alarms`` (one per scored minute) overrides the default threshold rule."""
    kind = sc.truth.kind[sc.rows]
    scored = kind >= 0
    y = kind[scored] > 0
    alarm = (sc.alarm if alarms is None else alarms)[scored]
    s = sc.score[scored]
    tp, fp = int((alarm & y).sum()), int((alarm & ~y).sum())
    fn, tn = int((~alarm & y).sum()), int((~alarm & ~y).sum())
    prec = tp / (tp + fp) if tp + fp else None
    rec = tp / (tp + fn) if tp + fn else None
    f1 = 2 * prec * rec / (prec + rec) if prec and rec else (0.0 if prec is not None and rec is not None else None)
    auroc = float(roc_auc_score(y, s)) if 0 < y.sum() < len(y) else None
    # events on the scored minutes, in time order
    rts = ts[sc.rows][scored]
    evs = events(rts, y)
    detected, lat = 0, []
    for a, b in evs:
        hit = np.flatnonzero(alarm[a : b + 1])
        if hit.size:
            detected += 1
            lat.append((rts[a + hit[0]] - rts[a]) / 60.0)
    normal_hours = (~y).sum() / 60.0
    by_kind = {}
    for k, name in KIND.items():
        sel = (kind[scored] == k) | ~y
        yk = kind[scored][sel] == k
        by_kind[f"auroc_{name.replace(' ', '_')}"] = (
            float(roc_auc_score(yk, s[sel])) if 0 < yk.sum() < len(yk) else None
        )
        by_kind[f"recall_{name.replace(' ', '_')}"] = float(alarm[sel][yk].mean()) if yk.any() else None
    return {
        "uuid": sc.uuid, "model": sc.model, "detector": sc.detector,
        "minutes": int(scored.sum()), "anomalous": int(y.sum()), "events": len(evs),
        "tp": tp, "fp": fp, "fn": fn, "tn": tn,
        "precision": prec, "recall": rec, "f1": f1, "fpr": fp / (fp + tn) if fp + tn else None,
        "auroc": auroc,
        "event_recall": detected / len(evs) if evs else None,
        "latency_min": float(np.median(lat)) if lat else None,
        "false_alarms_per_hour": fp / normal_hours if normal_hours else None,
        "threshold": sc.thr,
        **by_kind,
    }  # fmt: skip


def k_of_n(
    over: NDArray[np.bool_], ts: NDArray[np.int64], k: int, n: int, window_min: float = 10.0
) -> NDArray[np.bool_]:
    """Alarm at a minute when at least k of the last n records (within ``window_min``) exceed the threshold."""
    out = np.zeros(len(over), dtype=bool)
    for i in range(len(over)):
        lo = max(0, i - n + 1)
        recent = [j for j in range(lo, i + 1) if (ts[i] - ts[j]) / 60.0 <= window_min]
        out[i] = sum(bool(over[j]) for j in recent) >= k
    return out

"""Per-minute timelines of the primary model for the console.

For each person: every test minute's score, the threshold, the alarm, the ground truth, the main
activity, two raw motion summaries (accelerometer and gyroscope magnitude means) and the kNN
explanation, plus the anomaly events with their detection. Written to ``var/timelines`` (not
committed: it is per-minute data derived from the dataset, see data/DATASET.md).
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import numpy as np

from behavlab import data
from behavlab.data import MAIN
from behavlab.evaluate import measure, score_user
from behavlab.experiments.parallel import run as prun
from behavlab.truth import KIND, events, ground_truth

MODEL, DETECTOR, RESTRICT = "C", "knn", ("acc", "gyro")


def _col(u: data.UserData, modality: str, name: str) -> list[float | None]:
    i = u.feature_names[modality].index(name)
    return [None if not np.isfinite(v) else round(float(v), 4) for v in u.features[modality][:, i]]


def timeline(uuid: str) -> dict[str, Any] | None:
    u = data.load_user(uuid)
    truth = ground_truth(u)
    sc = score_user(u, MODEL, DETECTOR, 0, truth, restrict=RESTRICT, explain=True)
    if sc is None:
        return None
    acc = _col(u, "acc", "raw_acc:magnitude_stats:mean")
    gyro = _col(u, "gyro", "proc_gyro:magnitude_stats:mean")
    mods = list(sc.contributions or {})
    minutes = []
    for j, i in enumerate(sc.rows):
        minutes.append({
            "t": u.local[i].isoformat(timespec="minutes"), "score": round(float(sc.score[j]), 4),
            "alarm": bool(sc.alarm[j]), "kind": int(truth.kind[i]),
            "activity": MAIN[truth.activity[i]] if truth.activity[i] >= 0 else None,
            "acc": acc[i], "gyro": gyro[i],
            "why": {m: round(float(sc.contributions[m][j]), 3) for m in mods} if sc.contributions else None,
        })  # fmt: skip
    rts = u.ts[sc.rows]
    pos = truth.kind[sc.rows] > 0
    evs = []
    for a, b in events(rts, pos):
        hit = np.flatnonzero(sc.alarm[a : b + 1])
        evs.append({"start": minutes[a]["t"], "end": minutes[b]["t"], "minutes": b - a + 1,
                    "kind": KIND[int(truth.kind[sc.rows[a]])], "activity": minutes[a]["activity"],
                    "detected": bool(hit.size), "latency_min": float((rts[a + hit[0]] - rts[a]) / 60) if hit.size else None,
                    "first": a, "last": b})  # fmt: skip
    return {"uuid": uuid, "model": MODEL, "detector": DETECTOR, "threshold": sc.thr,
            "metrics": measure(sc, u.ts), "minutes": minutes, "events": evs}  # fmt: skip


def write_all(out: Path, workers: int = 4, uuids: tuple[str, ...] | None = None) -> Path:
    out.mkdir(parents=True, exist_ok=True)
    uuids = uuids or data.selected_users()
    index = []
    for tl in prun(timeline, [(u,) for u in uuids], workers):
        if tl is None:
            continue
        (out / f"{tl['uuid']}.json").write_text(json.dumps(tl, separators=(",", ":")), encoding="utf-8")
        m = tl["metrics"]
        index.append({"uuid": tl["uuid"], "minutes": len(tl["minutes"]), "events": len(tl["events"]),
                      "detected": sum(e["detected"] for e in tl["events"]), "alarms": sum(x["alarm"] for x in tl["minutes"]),
                      "auroc": m["auroc"], "f1": m["f1"], "fpr": m["fpr"],
                      "start": tl["minutes"][0]["t"], "end": tl["minutes"][-1]["t"]})  # fmt: skip
    (out / "index.json").write_text(json.dumps(index, indent=1), encoding="utf-8")
    return out

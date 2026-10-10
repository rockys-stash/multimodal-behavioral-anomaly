"""Data card computed from the archive: what the streams contain and how the ground truth falls."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import numpy as np

from behavlab import data
from behavlab.truth import NOVEL, OFF_SCHEDULE, UNDETERMINED, events, ground_truth


def check() -> dict[str, Any]:
    uuids = data.users()
    per: list[dict[str, Any]] = []
    for uid in uuids:
        u = data.load_user(uid)
        t = ground_truth(u)
        test = t.test
        ev = events(u.ts[test], t.kind[test] > 0)
        per.append({
            "uuid": uid, "minutes": u.n, "days": len(np.unique(u.day())),
            "acc": int(u.available["acc"].sum()), "gyro": int(u.available["gyro"].sum()),
            "location": int(u.available["location"].sum()),
            "main_activity_known": int((u.main_activity() >= 0).sum()),
            "reference": int(t.reference.sum()), "test": int(test.sum()),
            "scored": int(t.scored.sum()), "novel": int((t.kind == NOVEL).sum()),
            "off_schedule": int((t.kind == OFF_SCHEDULE).sum()),
            "undetermined_test": int((test & (t.kind == UNDETERMINED)).sum()), "events": len(ev),
            "timezone_agreement": data.timezone_agreement(u),
        })  # fmt: skip
    tot = {k: sum(p[k] for p in per) for k in per[0] if k not in ("uuid", "timezone_agreement")}
    return {
        "users": len(uuids),
        "expected": {"users": data.EXPECTED_USERS, "records": data.EXPECTED_RECORDS},
        "totals": tot,
        "users_with_anomalies": sum(p["novel"] + p["off_schedule"] > 0 for p in per),
        "timezone_agreement_median": float(np.median([p["timezone_agreement"] for p in per])),
        "timezone_agreement_min": float(np.min([p["timezone_agreement"] for p in per])),
        "per_user": per,
    }


def write_check(out: Path) -> Path:
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(check(), indent=1), encoding="utf-8")
    return out

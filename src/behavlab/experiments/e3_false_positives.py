"""E3 Error analysis of false positives.

For the model and detector fixed in the config before running (C with k-nearest neighbours, the
only detector whose score explains itself), every alarm on a normal minute is a false positive.
Each one is described by what the dataset records about that minute, and categories are compared
with the true negatives (normal minutes without an alarm) as a lift: how much more common the
category is among false positives than among true negatives. Categories:

- phone position (in pocket, hand, bag, on a table), from the person's labels;
- activity transition: the main activity differs from the previous record's, or the previous
  record is more than five minutes earlier (a resumed recording);
- the minute's main activity;
- which modality dominates the kNN explanation;
- secondary context labels reported that minute.

Real false-positive examples (time, labels, explanation) are saved for the report and the console.
"""

from __future__ import annotations

from collections import Counter
from pathlib import Path
from typing import Any

import numpy as np

from behavlab import data
from behavlab.data import MAIN
from behavlab.evaluate import score_user
from behavlab.experiments.common import result_dir, table
from behavlab.experiments.parallel import run as prun
from behavlab.truth import ground_truth

DESCRIPTION = "E3 false-positive error analysis for the primary model (C, kNN)"
PHONE = ("PHONE_IN_POCKET", "PHONE_IN_HAND", "PHONE_IN_BAG", "PHONE_ON_TABLE")
ACTIVITY_NAME = {"LYING_DOWN": "lying down", "SITTING": "sitting", "OR_standing": "standing",
                 "FIX_walking": "walking", "FIX_running": "running", "BICYCLING": "bicycling"}  # fmt: skip
SKIP_CONTEXT = set(MAIN) | set(PHONE)


def person(uuid: str, cfg: dict[str, Any]) -> dict[str, Any] | None:
    u = data.load_user(uuid)
    truth = ground_truth(u)
    sc = score_user(u, cfg["model"], cfg["detector"], 0, truth, restrict=tuple(cfg["restrict"]), explain=True)
    if sc is None:
        return None
    rows, kind = sc.rows, truth.kind[sc.rows]
    normal = kind == 0
    fp, tn = normal & sc.alarm, normal & ~sc.alarm
    act = truth.activity
    prev_act = np.concatenate([[-1], act[:-1]])
    transition = (act != prev_act) | (u.gap_before > 5)
    contrib = sc.contributions or {}
    mods = list(contrib)
    dominant = (
        np.array([mods[i] for i in np.argmax(np.stack([contrib[m] for m in mods], axis=1), axis=1)]) if mods else None
    )

    def cats(i: int, j: int) -> list[str]:
        """Categories of scored minute j (data row i)."""
        out = []
        pos = [p for p in PHONE if u.labels[p][i] == 1]
        out.append(
            "phone: " + (pos[0].removeprefix("PHONE_").replace("_", " ").lower() if len(pos) == 1 else "not reported")
        )
        out.append("transition: yes" if transition[i] else "transition: no")
        out.append("activity: " + ACTIVITY_NAME[MAIN[act[i]]])
        if dominant is not None:
            out.append(f"explanation: {dominant[j]} dominates")
        out += [f"context: {k}" for k, v in u.labels.items() if k not in SKIP_CONTEXT and v[i] == 1]
        return out

    c_fp: Counter[str] = Counter()
    c_tn: Counter[str] = Counter()
    examples = []
    for j in np.flatnonzero(fp):
        cs = cats(int(rows[j]), int(j))
        c_fp.update(cs)
        examples.append({"uuid": uuid, "time": u.local[rows[j]].isoformat(), "score": float(sc.score[j]),
                         "threshold": sc.thr, "categories": cs,
                         "explanation": {m: float(contrib[m][j]) for m in mods}})  # fmt: skip
    for j in np.flatnonzero(tn):
        c_tn.update(cats(int(rows[j]), int(j)))
    rng = np.random.default_rng(cfg["seed"])
    keep = (
        rng.choice(len(examples), size=min(cfg["examples_per_person"], len(examples)), replace=False)
        if examples
        else []
    )
    return {"uuid": uuid, "fp": int(fp.sum()), "tn": int(tn.sum()), "c_fp": dict(c_fp), "c_tn": dict(c_tn),
            "examples": [examples[i] for i in sorted(keep)]}  # fmt: skip


def run(cfg: dict[str, Any], results: Path | None = None) -> Path:
    uuids = data.selected_users()
    with result_dir("e3_false_positives", cfg, DESCRIPTION, results) as (rd, s):
        per = [p for p in prun(person, [(u, cfg) for u in uuids], cfg.get("workers", 1)) if p]
        fp_total, tn_total = sum(p["fp"] for p in per), sum(p["tn"] for p in per)
        c_fp: Counter[str] = Counter()
        c_tn: Counter[str] = Counter()
        for p in per:
            c_fp.update(p["c_fp"])
            c_tn.update(p["c_tn"])
        rows = []
        for cat in sorted(set(c_fp) | set(c_tn)):
            a, b = c_fp[cat] / max(fp_total, 1), c_tn[cat] / max(tn_total, 1)
            rows.append({"category": cat, "fp": c_fp[cat], "fp_share": a, "tn_share": b,
                         "lift": a / b if b > 0 else None})  # fmt: skip
        rd.write_json("categories.json", rows)
        rd.write_json("examples.json", [e for p in per for e in p["examples"]])
        rd.write_json("per_person.json", [{k: p[k] for k in ("uuid", "fp", "tn")} for p in per])
        s.title = "E3 False positives"
        s.question = "When the detector raises an alarm on normal behaviour, what is going on?"
        s.findings.append(f"{fp_total} false positives and {tn_total} true negatives over {len(per)} people "
                          f"(false-positive rate {fp_total / max(fp_total + tn_total, 1):.3f}).")  # fmt: skip
        groups = ["phone", "transition", "activity", "explanation"]
        for g in groups:
            sub = [r for r in rows if r["category"].startswith(g + ":")]
            s.tables.append(table(f"by_{g}", f"False positives by {g}",
                                  [("category", "Category", "l"), ("fp", "False positives", "r"),
                                   ("fp_share", "Share of FPs", "r"), ("tn_share", "Share of TNs", "r"), ("lift", "Lift", "r")],
                                  [{**r, "category": r["category"].split(": ", 1)[1], "fp_share": f"{r['fp_share']:.3f}",
                                    "tn_share": f"{r['tn_share']:.3f}", "lift": f"{r['lift']:.2f}" if r["lift"] else "n/a"}
                                   for r in sorted(sub, key=lambda r: -r["fp"])]))  # fmt: skip
        ctx = [r for r in rows if r["category"].startswith("context:") and r["fp"] >= cfg["min_count"] and r["lift"]]
        ctx.sort(key=lambda r: -r["lift"])
        s.tables.append(table("by_context", f"Context labels most over-represented among false positives (at least {cfg['min_count']} FPs)",
                              [("category", "Context label", "l"), ("fp", "False positives", "r"), ("fp_share", "Share of FPs", "r"),
                               ("tn_share", "Share of TNs", "r"), ("lift", "Lift", "r")],
                              [{**r, "category": r["category"].split(": ", 1)[1], "fp_share": f"{r['fp_share']:.3f}",
                                "tn_share": f"{r['tn_share']:.3f}", "lift": f"{r['lift']:.2f}"} for r in ctx[:12]]))  # fmt: skip
        for g in groups:
            sub = [
                r
                for r in rows
                if r["category"].startswith(g + ":") and r["lift"] and r["lift"] > 1 and r["fp"] >= cfg["min_count"]
            ]
            if sub:
                top = max(sub, key=lambda r: r["lift"])
                s.findings.append(f"Most over-represented {g}: {top['category'].split(': ', 1)[1]} "
                                  f"({top['fp_share']:.1%} of false positives against {top['tn_share']:.1%} of true negatives, lift {top['lift']:.2f}).")  # fmt: skip
        s.notes.append("Lift > 1 means the category is more common among false positives than among correctly quiet normal minutes. "
                       "Categories overlap (a minute has a phone position, an activity and several context labels).")  # fmt: skip
        s.notes.append(f"Primary model fixed before running: {cfg['model']} with {cfg['detector']}.")
    return rd.path

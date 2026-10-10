"""E4 Alarm rule: how much latency does it cost to cut false alarms?

For the primary model (C, kNN), the alarm threshold is set at several nominal reference alarm
rates, and alarms are raised either on any single minute over the threshold or only when k of the
last n records are (a persistence rule). Each setting is measured on the same test minutes: false
alarms per hour of normal behaviour, events detected and median detection latency.
"""

from __future__ import annotations

from collections import defaultdict
from pathlib import Path
from typing import Any

import numpy as np

from behavlab import data
from behavlab.evaluate import k_of_n, measure, score_user
from behavlab.experiments.common import result_dir, table
from behavlab.experiments.parallel import run as prun
from behavlab.stats import mean_ci
from behavlab.truth import ground_truth

DESCRIPTION = "E4 alarm threshold and persistence rule against false alarms and detection latency"


def person(uuid: str, cfg: dict[str, Any]) -> list[dict[str, Any]]:
    u = data.load_user(uuid)
    truth = ground_truth(u)
    sc = score_user(u, cfg["model"], cfg["detector"], 0, truth, restrict=tuple(cfg["restrict"]))
    if sc is None or sc.reference_scores is None:
        return []
    ts = u.ts[sc.rows]
    out = []
    for rate in cfg["rates"]:
        thr = float(np.quantile(sc.reference_scores, 1 - rate))
        over = sc.score > thr
        for k, n in cfg["rules"]:
            alarms = over if (k, n) == (1, 1) else k_of_n(over, ts, k, n)
            m = measure(sc, u.ts, alarms)
            out.append({"uuid": uuid, "rate": rate, "rule": f"{k} of {n}", **{x: m[x] for x in
                        ("false_alarms_per_hour", "fpr", "event_recall", "latency_min", "recall", "precision", "events")}})  # fmt: skip
    return out


def run(cfg: dict[str, Any], results: Path | None = None) -> Path:
    uuids = data.selected_users()
    with result_dir("e4_alarms", cfg, DESCRIPTION, results) as (rd, s):
        rows = [r for p in prun(person, [(u, cfg) for u in uuids], cfg.get("workers", 1)) for r in p]
        rd.write_json("per_person.json", rows)
        by: dict[tuple[float, str], list[dict[str, Any]]] = defaultdict(list)
        for r in rows:
            by[(r["rate"], r["rule"])].append(r)
        agg: list[dict[str, Any]] = []
        for (rate, rule), rs in sorted(by.items()):
            agg.append({"rate": rate, "rule": rule, **{m: mean_ci([r[m] for r in rs]) for m in
                        ("false_alarms_per_hour", "fpr", "event_recall", "latency_min", "precision")}})  # fmt: skip
        rd.write_json("aggregate.json", agg)

        def f(c: dict[str, Any], d: int = 3) -> str:
            return "n/a" if c["mean"] is None else f"{c['mean']:.{d}f} [{c['lo']:.{d}f}, {c['hi']:.{d}f}]"

        s.title = "E4 Alarm rule"
        s.question = "How much detection latency does it cost to cut false alarms?"
        s.tables.append(table("alarms", "Mean over people [95% bootstrap interval]",
                              [("rate", "Reference alarm rate", "r"), ("rule", "Rule", "l"),
                               ("false_alarms_per_hour", "False alarms / hour", "r"), ("fpr", "False-positive rate", "r"),
                               ("event_recall", "Events detected", "r"), ("latency_min", "Latency (min)", "r"),
                               ("precision", "Precision", "r")],
                              [{"rate": f"{a['rate']:.0%}", "rule": a["rule"],
                                "false_alarms_per_hour": f(a["false_alarms_per_hour"], 2), "fpr": f(a["fpr"]),
                                "event_recall": f(a["event_recall"]), "latency_min": f(a["latency_min"], 1),
                                "precision": f(a["precision"])} for a in agg]))  # fmt: skip
        base = next((a for a in agg if a["rate"] == cfg["default_rate"] and a["rule"] == "1 of 1"), None)
        for a in agg:
            if (
                base
                and a["rate"] == cfg["default_rate"]
                and a["rule"] != "1 of 1"
                and a["false_alarms_per_hour"]["mean"] is not None
            ):
                s.findings.append(
                    f"At a {a['rate']:.0%} reference alarm rate, '{a['rule']}' gives {a['false_alarms_per_hour']['mean']:.2f} false alarms per hour "
                    f"(single minute: {base['false_alarms_per_hour']['mean']:.2f}), detects {a['event_recall']['mean']:.1%} of events "
                    f"(single minute: {base['event_recall']['mean']:.1%}), median latency {a['latency_min']['mean']:.1f} min "
                    f"(single minute: {base['latency_min']['mean']:.1f})."
                )
        s.notes.append("Latency is measured from an event's first minute to its first alarm, over detected events only; "
                       "a rule that detects fewer events can therefore show a shorter latency.")  # fmt: skip
    return rd.path

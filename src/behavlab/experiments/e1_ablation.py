"""E1 modality ablation: which sensor information actually improves detection?

For every person, every model (A accelerometer; B + gyroscope; C + time of day; and the extensions
"accelerometer + time" and "C + location") and every detector is fitted on the person's reference
days and scored on their test days. Models A, B, C and "accelerometer + time" are compared on the
same minutes (those with both accelerometer and gyroscope); "C + location" is compared with C on
the minutes that also have location. Differences are tested per detector with paired Wilcoxon
tests over people, Holm-corrected within each detector.
"""

from __future__ import annotations

from collections import defaultdict
from pathlib import Path
from typing import Any

import numpy as np

from behavlab import data
from behavlab.detectors import DETECTOR_LABEL
from behavlab.evaluate import measure, score_user
from behavlab.experiments.common import Summary, result_dir, table
from behavlab.experiments.parallel import run as prun
from behavlab.fusion import MODEL_LABEL
from behavlab.stats import holm, mean_ci, paired
from behavlab.truth import KIND, ground_truth

DESCRIPTION = "E1 modality ablation: models A, B, C (+ time, + location) x detectors, per person"
METRICS = ["auroc", "f1", "precision", "recall", "fpr", "event_recall", "latency_min", "false_alarms_per_hour"]
METRIC_LABEL = {"auroc": "AUROC", "f1": "F1", "precision": "Precision", "recall": "Recall", "fpr": "False-positive rate",
                "event_recall": "Events detected", "latency_min": "Latency (min, median)",
                "false_alarms_per_hour": "False alarms per hour"}  # fmt: skip
# (evaluation set, baseline model, compared model): the comparisons the report tests
COMPARISONS = [("core", "A", "B"), ("core", "B", "C"), ("core", "A", "C"), ("core", "A", "A+time"),
               ("location", "C", "C+location")]  # fmt: skip
SETS = {"core": ("acc", "gyro"), "location": ("acc", "gyro", "location")}


def person(uuid: str, cfg: dict[str, Any]) -> list[dict[str, Any]]:
    u = data.load_user(uuid)
    truth = ground_truth(u)
    rows = []
    for set_name, models in cfg["sets"].items():
        for model in models:
            for det in cfg["detectors"]:
                seeds = cfg["seeds"] if det == "iforest" else [0]
                per_seed = []
                for seed in seeds:
                    sc = score_user(u, model, det, seed, truth, restrict=SETS[set_name],
                                    block_weighting=cfg.get("block_weighting", True))  # fmt: skip
                    if sc is not None:
                        per_seed.append(measure(sc, u.ts))
                if not per_seed:
                    continue
                row = dict(per_seed[0])
                for k, v in row.items():  # average numeric metrics over seeds
                    vals = [r[k] for r in per_seed]
                    if isinstance(v, float) or v is None:
                        num = [x for x in vals if x is not None]
                        row[k] = float(np.mean(num)) if num else None
                row.update(set=set_name, seeds=len(per_seed))
                rows.append(row)
    return rows


def aggregate(rows: list[dict[str, Any]], detectors: list[str]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    by: dict[tuple[str, str, str], dict[str, dict[str, Any]]] = defaultdict(dict)
    for r in rows:
        by[(r["set"], r["model"], r["detector"])][r["uuid"]] = r
    summary = []
    for (set_name, model, det), people in sorted(by.items()):
        entry = {"set": set_name, "model": model, "detector": det, "people": len(people)}
        for m in METRICS + [f"auroc_{k.replace(' ', '_')}" for k in KIND.values()]:
            entry[m] = mean_ci([p.get(m) for p in people.values()])
        summary.append(entry)
    tests = []
    for det in detectors:
        block = []
        for set_name, a, b in COMPARISONS:
            pa, pb = by.get((set_name, a, det), {}), by.get((set_name, b, det), {})
            for metric in ("auroc", "f1", "event_recall"):
                t = paired({k: v[metric] for k, v in pa.items()}, {k: v[metric] for k, v in pb.items()})
                block.append({"detector": det, "set": set_name, "a": a, "b": b, "metric": metric, **t})
        for t, p in zip(block, holm([t["p"] for t in block]), strict=True):
            t["p_holm"] = p
        tests += block
    return summary, tests


def _fmt(c: dict[str, Any], digits: int = 3) -> str:
    if c["mean"] is None:
        return "n/a"
    return f"{c['mean']:.{digits}f} [{c['lo']:.{digits}f}, {c['hi']:.{digits}f}]"


def summarise(s: Summary, summary: list[dict[str, Any]], tests: list[dict[str, Any]], people: int) -> None:
    s.title = "E1 Modality ablation"
    s.question = "Which sensor information actually improves anomaly detection?"
    for det in sorted({e["detector"] for e in summary}):
        rows = [e for e in summary if e["detector"] == det]
        s.tables.append(table(
            f"ablation_{det}", f"{DETECTOR_LABEL[det]}: mean over people [95% bootstrap interval]",
            [("model", "Model", "l"), ("set", "Minutes compared", "l"), ("people", "People scored / with anomalies", "r")]
            + [(m, METRIC_LABEL[m], "r") for m in ("auroc", "f1", "recall", "fpr", "event_recall", "latency_min")],
            [{"model": MODEL_LABEL[e["model"]], "set": "acc + gyro" if e["set"] == "core" else "acc + gyro + location",
              "people": f"{e['people']} / {e['auroc']['n']}", **{m: _fmt(e[m], 1 if m == "latency_min" else 3) for m in METRICS}} for e in rows],
        ))  # fmt: skip
    trows = []
    for t in tests:
        trows.append({"detector": DETECTOR_LABEL[t["detector"]], "comparison": f"{t['b']} vs {t['a']}",
                      "metric": METRIC_LABEL[t["metric"]], "n": t["n"],
                      "diff": f"{t['mean_diff']:+.3f}" if t.get("mean_diff") is not None else "n/a",
                      "better": f"{t.get('better', 0)}/{t.get('worse', 0)}",
                      "p": f"{t['p_holm']:.3g}" if t.get("p_holm") is not None else "n/a"})  # fmt: skip
    s.tables.append(table("tests", "Paired differences over people (Wilcoxon, Holm within detector)",
                          [("detector", "Detector", "l"), ("comparison", "Comparison", "l"), ("metric", "Metric", "l"),
                           ("n", "People", "r"), ("diff", "Mean difference", "r"),
                           ("better", "Better / worse", "r"), ("p", "p (Holm)", "r")], trows))  # fmt: skip
    for t in tests:
        if t["metric"] == "auroc" and t.get("p_holm") is not None:
            verdict = "significant" if t["p_holm"] < 0.05 else "not significant"
            s.findings.append(
                f"{DETECTOR_LABEL[t['detector']]}: {t['b']} vs {t['a']} AUROC {t['mean_diff']:+.3f} "
                f"(better for {t['better']} of {t['n']} people, Holm p = {t['p_holm']:.3g}, {verdict})."
            )
    s.notes.append(
        f"{people} people evaluated. AUROC, recall and events detected need at least one anomaly minute, so they average over "
        "fewer people than the false-positive rate. A person enters a comparison only if both models could be scored for them."
    )
    s.notes.append("Thresholds come from reference days only (95th percentile of cross-fitted reference scores); "
                   "AUROC does not depend on the threshold.")  # fmt: skip
    s.notes.append("'acc + time' and 'C + location' extend the specified A/B/C ablation.")


def run(cfg: dict[str, Any], results: Path | None = None) -> Path:
    uuids = data.selected_users()
    with result_dir("e1_ablation", cfg, DESCRIPTION, results) as (rd, s):
        per = prun(person, [(u, cfg) for u in uuids], cfg.get("workers", 1))
        rows = [r for p in per for r in p]
        rd.write_json("per_person.json", rows)
        summary, tests = aggregate(rows, cfg["detectors"])
        rd.write_json("aggregate.json", summary)
        rd.write_json("tests.json", tests)
        summarise(s, summary, tests, len({r["uuid"] for r in rows}))
    return rd.path

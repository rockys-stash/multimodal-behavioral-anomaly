"""E2 Which information helps which kind of anomaly?

Reads E1's per-person results and splits detection by anomaly kind: a novel activity (something
the person rarely or never did in the reference days) and an off-schedule activity (a familiar
activity at an unfamiliar time of day). Hypothesis stated before running: time of day helps the
off-schedule kind and not the novel kind, because a familiar activity at an odd hour looks normal
to the motion sensors alone.
"""

from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path
from typing import Any

from behavlab.detectors import DETECTOR_LABEL
from behavlab.experiments.common import ROOT, result_dir, table
from behavlab.fusion import MODEL_LABEL
from behavlab.stats import holm, mean_ci, paired

DESCRIPTION = "E2 detection by anomaly kind (novel activity vs off schedule), from E1's per-person results"
KINDS = {"novel_activity": "Novel activity", "off_schedule": "Off schedule"}
COMPARISONS = [("A", "B"), ("B", "C"), ("A", "A+time")]


def run(cfg: dict[str, Any], results: Path | None = None) -> Path:
    base = (results or ROOT / "results") / "e1_ablation"
    e1 = (base / "LATEST").read_text().strip()
    rows = json.loads((base / e1 / "per_person.json").read_text(encoding="utf-8"))
    rows = [r for r in rows if r["set"] == "core"]
    with result_dir("e2_kinds", {**cfg, "e1_result": e1}, DESCRIPTION, results) as (rd, s):
        by: dict[tuple[str, str], dict[str, dict[str, Any]]] = defaultdict(dict)
        for r in rows:
            by[(r["model"], r["detector"])][r["uuid"]] = r
        agg, tests = [], []
        for (model, det), people in sorted(by.items()):
            e: dict[str, Any] = {"model": model, "detector": det}
            for k in KINDS:
                e[f"auroc_{k}"] = mean_ci([p.get(f"auroc_{k}") for p in people.values()])
                e[f"recall_{k}"] = mean_ci([p.get(f"recall_{k}") for p in people.values()])
            agg.append(e)
        for det in sorted({d for _, d in by}):
            block = []
            for a, b in COMPARISONS:
                for k in KINDS:
                    m = f"auroc_{k}"
                    t = paired({u: r[m] for u, r in by[(a, det)].items()}, {u: r[m] for u, r in by[(b, det)].items()})
                    block.append({"detector": det, "a": a, "b": b, "kind": k, **t})
            for t, p in zip(block, holm([t["p"] for t in block]), strict=True):
                t["p_holm"] = p
            tests += block
        rd.write_json("aggregate.json", agg)
        rd.write_json("tests.json", tests)
        s.title = "E2 Anomaly kinds"
        s.question = "Which information helps detect which kind of anomaly?"

        def fmt(c: dict[str, Any]) -> str:
            return "n/a" if c["mean"] is None else f"{c['mean']:.3f} [{c['lo']:.3f}, {c['hi']:.3f}] (n={c['n']})"

        s.tables.append(table("kinds", "AUROC against normal minutes, mean over people [95% bootstrap interval]",
                              [("detector", "Detector", "l"), ("model", "Model", "l")]
                              + [(f"auroc_{k}", v, "r") for k, v in KINDS.items()],
                              [{"detector": DETECTOR_LABEL[e["detector"]], "model": MODEL_LABEL[e["model"]],
                                **{f"auroc_{k}": fmt(e[f"auroc_{k}"]) for k in KINDS}} for e in agg]))  # fmt: skip
        s.tables.append(table("tests", "Paired AUROC differences by kind (Wilcoxon, Holm within detector)",
                              [("detector", "Detector", "l"), ("comparison", "Comparison", "l"), ("kind", "Kind", "l"),
                               ("n", "People", "r"), ("diff", "Mean difference", "r"), ("p", "p (Holm)", "r")],
                              [{"detector": DETECTOR_LABEL[t["detector"]], "comparison": f"{t['b']} vs {t['a']}",
                                "kind": KINDS[t["kind"]], "n": t["n"],
                                "diff": f"{t['mean_diff']:+.3f}" if t.get("mean_diff") is not None else "n/a",
                                "p": f"{t['p_holm']:.3g}" if t.get("p_holm") is not None else "n/a"} for t in tests]))  # fmt: skip
        for t in tests:
            if t.get("p_holm") is not None and t["b"] in ("C", "A+time"):
                s.findings.append(
                    f"{DETECTOR_LABEL[t['detector']]}, {KINDS[t['kind']].lower()}: {t['b']} vs {t['a']} AUROC "
                    f"{t['mean_diff']:+.3f} over {t['n']} people (Holm p = {t['p_holm']:.3g})."
                )
        s.notes.append("A person counts for a kind only if their test days contain that kind and normal minutes.")
    return rd.path

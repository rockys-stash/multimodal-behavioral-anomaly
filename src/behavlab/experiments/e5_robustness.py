"""E5 Robustness: does the ablation's answer survive the choices made before running it?

The A / B / C AUROC comparison is repeated under one change at a time to a choice the study had to
make: plain concatenation instead of equal weight per modality; a stricter or looser definition of
a novel activity (0.5% or 2% of reference minutes instead of 1%); and fewer or more neighbours for
kNN (5 or 20 instead of 10). For each variant the sign of each mean difference and its Holm-adjusted
significance are compared with the default.
"""

from __future__ import annotations

from collections import defaultdict
from pathlib import Path
from typing import Any

from behavlab import data
from behavlab.evaluate import measure, score_user
from behavlab.experiments.common import result_dir, table
from behavlab.experiments.parallel import run as prun
from behavlab.stats import holm, paired
from behavlab.truth import ground_truth

DESCRIPTION = "E5 robustness of the A/B/C ablation to fusion weighting, anomaly definition and kNN k"
COMPARISONS = [("A", "B"), ("B", "C"), ("A", "C")]


def person(uuid: str, cfg: dict[str, Any]) -> list[dict[str, Any]]:
    u = data.load_user(uuid)
    out = []
    for v in cfg["variants"]:
        truth = ground_truth(u, rare=v.get("rare", 0.01))
        for det in v.get("detectors", cfg["detectors"]):
            for model in ("A", "B", "C"):
                sc = score_user(u, model, det, 0, truth, restrict=("acc", "gyro"),
                                block_weighting=v.get("block_weighting", True), k=v.get("k", 10))  # fmt: skip
                if sc is not None:
                    out.append({"uuid": uuid, "variant": v["name"], "detector": det, "model": model,
                                "auroc": measure(sc, u.ts)["auroc"]})  # fmt: skip
    return out


def run(cfg: dict[str, Any], results: Path | None = None) -> Path:
    uuids = data.selected_users()
    with result_dir("e5_robustness", cfg, DESCRIPTION, results) as (rd, s):
        rows = [r for p in prun(person, [(u, cfg) for u in uuids], cfg.get("workers", 1)) for r in p]
        rd.write_json("per_person.json", rows)
        by: dict[tuple[str, str, str], dict[str, float | None]] = defaultdict(dict)
        for r in rows:
            by[(r["variant"], r["detector"], r["model"])][r["uuid"]] = r["auroc"]
        tests = []
        for v in cfg["variants"]:
            for det in v.get("detectors", cfg["detectors"]):
                block = [{"variant": v["name"], "detector": det, "a": a, "b": b,
                          **paired(by[(v["name"], det, a)], by[(v["name"], det, b)])} for a, b in COMPARISONS]  # fmt: skip
                for t, p in zip(block, holm([t["p"] for t in block]), strict=True):
                    t["p_holm"] = p
                tests += block
        rd.write_json("tests.json", tests)
        default = {(t["detector"], t["a"], t["b"]): t for t in tests if t["variant"] == "default"}

        def verdict(t: dict[str, Any]) -> str:
            if t.get("mean_diff") is None:
                return "n/a"
            sig = t.get("p_holm") is not None and t["p_holm"] < 0.05
            return ("+" if t["mean_diff"] > 0 else "-") + (" sig." if sig else " n.s.")

        s.title = "E5 Robustness"
        s.question = "Does the ablation's answer survive the choices made before running it?"
        trs = []
        changed = 0
        for t in tests:
            d = default.get((t["detector"], t["a"], t["b"]))
            same = d is not None and verdict(d) == verdict(t)
            changed += t["variant"] != "default" and not same
            trs.append({"variant": t["variant"], "detector": t["detector"], "comparison": f"{t['b']} vs {t['a']}",
                        "n": t["n"], "diff": f"{t['mean_diff']:+.3f}" if t.get("mean_diff") is not None else "n/a",
                        "p": f"{t['p_holm']:.3g}" if t.get("p_holm") is not None else "n/a",
                        "same": "yes" if same else "no"})  # fmt: skip
        s.tables.append(table("robustness", "AUROC differences per variant (Wilcoxon, Holm within variant and detector)",
                              [("variant", "Variant", "l"), ("detector", "Detector", "l"), ("comparison", "Comparison", "l"),
                               ("n", "People", "r"), ("diff", "Mean difference", "r"), ("p", "p (Holm)", "r"),
                               ("same", "Same verdict as default", "l")], trs))  # fmt: skip
        n_var = sum(t["variant"] != "default" for t in tests)
        s.findings.append(
            f"{n_var - changed} of {n_var} variant comparisons reach the same verdict (direction and significance) as the default."
        )
        for t in tests:
            d = default.get((t["detector"], t["a"], t["b"]))
            if t["variant"] != "default" and d is not None and verdict(d) != verdict(t):
                s.findings.append(f"Changed under '{t['variant']}' ({t['detector']}): {t['b']} vs {t['a']} is {verdict(t)} "
                                  f"(default {verdict(d)}).")  # fmt: skip
        s.notes.append(
            "Holm correction here runs over the three AUROC comparisons of one variant and detector, a smaller family "
            "than E1's (five comparisons on three metrics), so 'significant' here is less conservative than in E1. "
            "E1 is the primary analysis; this experiment only asks whether verdicts move when a choice changes."
        )
    return rd.path

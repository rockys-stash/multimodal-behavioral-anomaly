"""Command line: fetch and check the data, run experiments, render results, build timelines, serve."""

from __future__ import annotations

import argparse
import importlib
import os
import sys
from pathlib import Path

from behavlab.experiments.common import ROOT, load_config

EXPERIMENTS = {
    "e1": "e1_ablation",
    "e2": "e2_kinds",
    "e3": "e3_false_positives",
    "e4": "e4_alarms",
    "e5": "e5_robustness",
}


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="behavlab", description=__doc__)
    sub = p.add_subparsers(dest="cmd", required=True)
    sub.add_parser("fetch", help="download the ExtraSensory features archive and check its SHA-256")
    c = sub.add_parser("check", help="data card: counts, modality coverage, timezone check, anomaly prevalence")
    c.add_argument("--out", type=Path, default=ROOT / "docs" / "generated" / "data_check.json")
    e = sub.add_parser("experiment", help="run one experiment (e1..e5) or all of them in order")
    e.add_argument("name", choices=[*EXPERIMENTS, "all"])
    e.add_argument("--configs", type=Path, default=ROOT / "configs")
    e.add_argument("--results", type=Path)
    e.add_argument("--workers", type=int)
    r = sub.add_parser("results", help="render docs/generated/results.md from results/*/LATEST")
    r.add_argument("--results", type=Path)
    r.add_argument("--out", type=Path, default=ROOT / "docs" / "generated" / "results.md")
    t = sub.add_parser("timelines", help="per-minute scores of the primary model for the console (var/timelines)")
    t.add_argument("--out", type=Path, default=ROOT / "var" / "timelines")
    t.add_argument("--workers", type=int, default=4)
    s = sub.add_parser("serve", help="serve the console and API")
    s.add_argument("--host", default=os.environ.get("BEHAVLAB_HOST", "127.0.0.1"))
    s.add_argument("--port", type=int, default=int(os.environ.get("BEHAVLAB_PORT", "8000")))
    s.add_argument("--results", type=Path)
    s.add_argument("--timelines", type=Path)
    a = p.parse_args(argv)

    if a.cmd == "fetch":
        from behavlab import data

        print(data.fetch())
        return 0
    if a.cmd == "check":
        from behavlab.check import write_check

        print(write_check(a.out))
        return 0
    if a.cmd == "experiment":
        names = list(EXPERIMENTS) if a.name == "all" else [a.name]
        for n in names:
            module = EXPERIMENTS[n]
            cfg = load_config(a.configs / f"{module}.yaml")
            if a.workers is not None:
                cfg["workers"] = a.workers
            exp = importlib.import_module(f"behavlab.experiments.{module}")
            print(f"{n}: running", file=sys.stderr, flush=True)
            print(exp.run(cfg, a.results))
        return 0
    if a.cmd == "results":
        from behavlab.results_md import write

        print(write(a.results or ROOT / "results", a.out))
        return 0
    if a.cmd == "timelines":
        from behavlab.timelines import write_all

        print(write_all(a.out, a.workers))
        return 0
    if a.cmd == "serve":
        import uvicorn

        from behavlab.api import check_bind, create_app

        check_bind(a.host)
        uvicorn.run(create_app(a.results, a.timelines), host=a.host, port=a.port, log_level="info")
        return 0
    return 1


if __name__ == "__main__":
    raise SystemExit(main())

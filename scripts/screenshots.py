"""Capture screenshots of the running console from the committed results and the built timelines.

Usage: uv run python scripts/screenshots.py [--out docs/screenshots]
Needs the built console (npm --prefix web run build), Chromium for Playwright, results/ and
var/timelines (make timelines).
"""

from __future__ import annotations

import argparse
import json
import socket
import threading
import time
import urllib.request
from pathlib import Path

import uvicorn
from playwright.sync_api import ViewportSize, sync_playwright

from behavlab.api import create_app

ROOT = Path(__file__).resolve().parents[1]
VIEWPORTS: dict[str, ViewportSize] = {
    "desktop": {"width": 1440, "height": 900},
    "mobile": {"width": 390, "height": 844},
}


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return int(s.getsockname()[1])


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", type=Path, default=ROOT / "docs" / "screenshots")
    ap.add_argument("--timelines", type=Path, default=ROOT / "var" / "timelines")
    args = ap.parse_args()
    index = json.loads((args.timelines / "index.json").read_text(encoding="utf-8"))
    # the person with the most anomaly events: the most informative timeline
    person = max(index, key=lambda r: (r["events"], r["uuid"]))["uuid"]
    app = create_app(ROOT / "results", args.timelines)
    port = _free_port()
    server = uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=port, log_level="warning"))
    threading.Thread(target=server.run, daemon=True).start()
    base = f"http://127.0.0.1:{port}"
    for _ in range(100):
        try:
            urllib.request.urlopen(base + "/api/health", timeout=1)
            break
        except OSError:
            time.sleep(0.1)
    shots = [("people", "/people"), ("timeline", f"/people/{person}"), ("ablation", "/ablation"),
             ("false-positives", "/errors"), ("experiments", "/experiments/e1_ablation"), ("method", "/method")]  # fmt: skip
    args.out.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        for vp, size in VIEWPORTS.items():
            for scheme in ("light", "dark"):
                if vp == "mobile" and scheme == "dark":
                    continue
                ctx = browser.new_context(viewport=size, color_scheme=scheme, device_scale_factor=1)
                page = ctx.new_page()
                for name, path in shots:
                    page.goto(base + path)
                    page.locator("h1").first.wait_for(timeout=30000)
                    page.wait_for_load_state("networkidle")
                    if page.locator(".skeleton").count():
                        page.locator(".skeleton").first.wait_for(state="detached", timeout=30000)
                    if name == "timeline":  # show an event's explanation
                        page.locator("table").last.locator("tbody tr button").first.click()
                        page.get_by_text("Why this score").wait_for()
                    out = args.out / f"{name}-{vp}{'-dark' if scheme == 'dark' else ''}.png"
                    page.screenshot(path=str(out), full_page=vp == "desktop")
                    print(out.relative_to(ROOT))
                ctx.close()
        browser.close()
    server.should_exit = True


if __name__ == "__main__":
    main()

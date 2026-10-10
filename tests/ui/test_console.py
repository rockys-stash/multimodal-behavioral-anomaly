"""Browser tests for the Cadence console.

The fixture runs the smoke configs (configs/smoke) for E1, E2 and E3 on the first four people into a
temporary results tree, and builds their timelines, so the console is tested on real pipeline output
while E4 and E5 stay pending. Run with ``uv run pytest -m ui`` after ``npm --prefix web run build``
and ``make data``.
"""

from __future__ import annotations

import socket
import threading
import time
import urllib.request
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest

from behavlab.cli import main as cli
from tests.conftest import needs_data

ROOT = Path(__file__).resolve().parents[2]
AXE = ROOT / "web" / "node_modules" / "axe-core" / "axe.min.js"
pytestmark = [pytest.mark.ui, needs_data]
playwright_api = pytest.importorskip("playwright.sync_api")

VIEWPORTS = {"desktop": {"width": 1440, "height": 900}, "mobile": {"width": 390, "height": 844}}


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return int(s.getsockname()[1])


@pytest.fixture(scope="module")
def base_url(tmp_path_factory: pytest.TempPathFactory) -> Iterator[str]:
    if not (ROOT / "web" / "dist" / "index.html").exists():
        pytest.skip("frontend not built (npm --prefix web run build)")
    import uvicorn

    from behavlab.api import create_app

    mp = pytest.MonkeyPatch()
    mp.setenv("BEHAVLAB_USERS", "4")
    mp.delenv("BEHAVLAB_API_TOKEN", raising=False)
    results = tmp_path_factory.mktemp("results")
    timelines = tmp_path_factory.mktemp("timelines")
    for e in ("e1", "e2", "e3"):
        assert cli(["experiment", e, "--configs", str(ROOT / "configs" / "smoke"), "--results", str(results)]) == 0
    assert cli(["timelines", "--out", str(timelines), "--workers", "1"]) == 0
    app = create_app(results, timelines)
    port = _free_port()
    server = uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=port, log_level="warning"))
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    url = f"http://127.0.0.1:{port}"
    for _ in range(100):
        try:
            urllib.request.urlopen(f"{url}/api/health", timeout=1)
            break
        except OSError:
            time.sleep(0.1)
    yield url
    server.should_exit = True
    thread.join(timeout=5)
    mp.undo()


@pytest.fixture(scope="module")
def browser() -> Iterator[Any]:
    with playwright_api.sync_playwright() as p:
        b = p.chromium.launch()
        yield b
        b.close()


PERSON = "0A986513-7828-4D53-AA1F-E02D6DF9561B"  # third person by id; has anomaly events on test days
PAGES = [
    ("people", "/people", "Timelines"),
    ("person", f"/people/{PERSON}", "Anomaly events"),
    ("ablation", "/ablation", "Paired tests over people"),
    ("errors", "/errors", "Examples"),
    ("e1", "/experiments/e1_ablation", "Findings"),
    ("e4-pending", "/experiments/e4_alarms", "Status: pending"),
    ("method", "/method", "Limits"),
    ("not-found", "/nowhere", "Page not found"),
]


def _open(browser: Any, base_url: str, viewport: str, path: str, marker: str, scheme: str = "light") -> Any:
    ctx = browser.new_context(viewport=VIEWPORTS[viewport], color_scheme=scheme)
    page = ctx.new_page()
    errors: list[str] = []
    page.on("console", lambda m: errors.append(m.text) if m.type == "error" and "404" not in m.text else None)
    page.on("pageerror", lambda e: errors.append(str(e)))
    page.goto(base_url + path)
    page.get_by_text(marker, exact=False).first.wait_for(timeout=30000)
    page.wait_for_load_state("networkidle")
    page.errors = errors
    return page


@pytest.mark.parametrize("viewport", list(VIEWPORTS))
@pytest.mark.parametrize(("name", "path", "marker"), PAGES)
def test_page_renders(browser: Any, base_url: str, viewport: str, name: str, path: str, marker: str) -> None:
    page = _open(browser, base_url, viewport, path, marker)
    assert page.locator("h1").count() == 1
    assert not page.locator(".skeleton").count(), "loading skeleton still visible"
    assert not page.locator("[role=alert]").count(), "error state rendered"
    overflow = page.evaluate("document.documentElement.scrollWidth - window.innerWidth")
    assert overflow <= 1, f"page scrolls horizontally by {overflow}px"
    assert not page.errors, page.errors
    page.context.close()


def test_timeline_keyboard_and_event_selection(browser: Any, base_url: str) -> None:
    page = _open(browser, base_url, "desktop", f"/people/{PERSON}", "Anomaly events")
    page.locator("table").last.locator("tbody tr button").first.click()
    page.get_by_text("Why this score").wait_for()
    t0 = page.locator("dl.kv dd").first.inner_text()
    page.locator("svg.chart-svg").focus()
    page.keyboard.press("ArrowRight")
    page.wait_for_function(f"document.querySelector('dl.kv dd').innerText !== {t0!r}")
    shares = page.locator(".bar-row .mono").all_inner_texts()
    assert len(shares) == 3 and abs(sum(int(s.rstrip("%")) for s in shares) - 100) <= 2
    page.context.close()


def test_people_table_links_to_a_timeline(browser: Any, base_url: str) -> None:
    page = _open(browser, base_url, "desktop", "/people", "Timelines")
    assert page.locator("table tbody tr").count() >= 3
    page.locator("table tbody tr button").first.click()
    page.get_by_text("Anomaly events").first.wait_for()
    assert "/people/" in page.url
    page.context.close()


@pytest.mark.parametrize("scheme", ["light", "dark"])
@pytest.mark.parametrize("viewport", list(VIEWPORTS))
def test_no_wcag_violations(browser: Any, base_url: str, viewport: str, scheme: str) -> None:
    """axe-core audit (WCAG 2.1 A/AA and best practices) of every view in both themes."""
    if not AXE.exists():
        pytest.skip("axe-core not installed (npm --prefix web ci)")
    ctx = browser.new_context(viewport=VIEWPORTS[viewport], color_scheme=scheme, bypass_csp=True)
    page = ctx.new_page()
    found: dict[str, list[str]] = {}
    for _, path, marker in PAGES:
        page.goto(base_url + path)
        page.get_by_text(marker, exact=False).first.wait_for(timeout=30000)
        page.wait_for_load_state("networkidle")
        page.add_script_tag(path=str(AXE))
        violations = page.evaluate(
            """async () => (await axe.run(document, {runOnly: ['wcag2a', 'wcag2aa', 'wcag21aa',
               'best-practice']})).violations.map(v => v.id + ': ' + v.nodes.map(n => n.target.join(' ')).join(', '))"""
        )
        if violations:
            found[path] = violations
    ctx.close()
    assert not found, found

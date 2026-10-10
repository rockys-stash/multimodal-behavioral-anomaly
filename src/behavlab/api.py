"""Read-only HTTP API for the Tremor console.

- Every route is a GET over finished result directories; nothing can be written or started.
- Every client is rate limited.
- With ``BEHAVLAB_API_TOKEN`` set, every ``/api`` route except ``/api/health`` needs
  ``Authorization: Bearer <token>``. Binding a non-loopback host without a token is refused.
"""

from __future__ import annotations

import hmac
import ipaddress
import json
import os
import re
import threading
import time
from functools import lru_cache
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse, Response
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint

from behavlab.experiments.common import ROOT

EXPERIMENTS = ("e1_ablation", "e2_kinds", "e3_false_positives", "e4_alarms", "e5_robustness")
_UUID = re.compile(r"^[0-9A-F]{8}-[0-9A-F]{4}-[0-9A-F]{4}-[0-9A-F]{4}-[0-9A-F]{12}$")
_RUN = re.compile(r"^[0-9]{8}T[0-9]{6}Z-[0-9a-z]{4,40}$")


class RateLimiter:
    """Token bucket per client address."""

    def __init__(self, rate: float, burst: int) -> None:
        self.rate, self.burst = rate, burst
        self._buckets: dict[str, tuple[float, float]] = {}
        self._lock = threading.Lock()

    def allow(self, key: str) -> bool:
        now = time.monotonic()
        with self._lock:
            tokens, last = self._buckets.get(key, (float(self.burst), now))
            tokens = min(self.burst, tokens + (now - last) * self.rate)
            if tokens < 1:
                self._buckets[key] = (tokens, now)
                return False
            self._buckets[key] = (tokens - 1, now)
            if len(self._buckets) > 10_000:
                self._buckets = dict(list(self._buckets.items())[-5_000:])
            return True


class GuardMiddleware(BaseHTTPMiddleware):
    def __init__(self, app: Any, token: str | None, limiter: RateLimiter) -> None:
        super().__init__(app)
        self.token, self.limiter = token, limiter

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        path = request.url.path
        if path.startswith("/api"):
            client = request.client.host if request.client else "unknown"
            if not self.limiter.allow(client):
                return JSONResponse({"detail": "rate limit exceeded"}, status_code=429, headers={"Retry-After": "1"})
            if request.method not in ("GET", "HEAD"):
                return JSONResponse({"detail": "read-only API"}, status_code=405)
            if self.token and path != "/api/health":
                supplied = request.headers.get("authorization", "").removeprefix("Bearer ").strip()
                if not hmac.compare_digest(supplied.encode(), self.token.encode()):
                    return JSONResponse({"detail": "unauthorized"}, status_code=401)
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; "
            "font-src 'self'; connect-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'self'"
        )
        return response


def is_loopback(host: str) -> bool:
    if host == "localhost":
        return True
    try:
        return ipaddress.ip_address(host).is_loopback
    except ValueError:
        return False


def check_bind(host: str) -> None:
    if not is_loopback(host) and not os.environ.get("BEHAVLAB_API_TOKEN"):
        raise SystemExit(f"refusing to serve on {host} without BEHAVLAB_API_TOKEN")


def create_app(results: Path | None = None, timelines: Path | None = None, static_dir: Path | None = None) -> FastAPI:
    results = (results or ROOT / "results").resolve()
    tl_dir = (timelines or ROOT / "var" / "timelines").resolve()
    static = (static_dir or ROOT / "web" / "dist").resolve()
    token = os.environ.get("BEHAVLAB_API_TOKEN") or None
    app = FastAPI(title="behavlab", docs_url=None, redoc_url=None, openapi_url=None)
    app.add_middleware(
        GuardMiddleware,
        token=token,
        limiter=RateLimiter(rate=float(os.environ.get("BEHAVLAB_RATE_PER_SEC", "30")), burst=120),
    )

    def run_dir(exp: str) -> Path | None:
        if exp not in EXPERIMENTS:
            raise HTTPException(404, "unknown experiment")
        marker = results / exp / "LATEST"
        if not marker.is_file():
            return None
        run_id = marker.read_text(encoding="utf-8").strip()
        if not _RUN.match(run_id):
            raise HTTPException(500, "corrupt LATEST marker")
        d = results / exp / run_id
        return d if (d / "summary.json").is_file() else None

    @lru_cache(maxsize=16)
    def _read(path: str, mtime: float) -> Any:
        return json.loads(Path(path).read_text(encoding="utf-8"))

    def read(p: Path) -> Any:
        if not p.is_file():
            raise HTTPException(404, f"{p.name} missing")
        return _read(str(p), p.stat().st_mtime)

    @app.get("/api/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/api/experiments")
    def experiments() -> dict[str, Any]:
        items = []
        for exp in EXPERIMENTS:
            d = run_dir(exp)
            if d is None:
                items.append({"experiment": exp, "status": "pending"})
            else:
                s = read(d / "summary.json")
                items.append({"experiment": exp, "status": "complete", "title": s["title"], "question": s["question"],
                              **read(d / "provenance.json")})  # fmt: skip
        return {"items": items}

    @app.get("/api/experiments/{exp}")
    def experiment(exp: str) -> dict[str, Any]:
        d = run_dir(exp)
        if d is None:
            raise HTTPException(404, "experiment has not been run")
        return {**read(d / "summary.json"), "provenance": read(d / "provenance.json")}

    @app.get("/api/ablation")
    def ablation() -> dict[str, Any]:
        d = run_dir("e1_ablation")
        if d is None:
            raise HTTPException(404, "e1_ablation has not been run")
        return {"aggregate": read(d / "aggregate.json"), "tests": read(d / "tests.json"),
                "provenance": read(d / "provenance.json")}  # fmt: skip

    @app.get("/api/false-positives")
    def false_positives() -> dict[str, Any]:
        d = run_dir("e3_false_positives")
        if d is None:
            raise HTTPException(404, "e3_false_positives has not been run")
        return {"categories": read(d / "categories.json"), "examples": read(d / "examples.json"),
                "provenance": read(d / "provenance.json")}  # fmt: skip

    @app.get("/api/people")
    def people() -> dict[str, Any]:
        p = tl_dir / "index.json"
        if not p.is_file():
            raise HTTPException(404, "timelines not built (behavlab timelines)")
        return {"items": read(p)}

    @app.get("/api/people/{uuid}")
    def person(uuid: str) -> Any:
        if not _UUID.match(uuid):
            raise HTTPException(404, "unknown person")
        return read(tl_dir / f"{uuid}.json")

    @app.get("/api/{rest:path}")
    def api_404(rest: str) -> Response:
        return JSONResponse({"detail": "not found"}, status_code=404)

    @app.get("/{rest:path}")
    def spa(rest: str) -> Response:
        if not static.exists():
            return JSONResponse({"detail": "console not built (npm --prefix web run build)"}, status_code=404)
        candidate = (static / rest).resolve()
        if rest and candidate.is_file() and candidate.is_relative_to(static):
            return FileResponse(candidate)
        return FileResponse(static / "index.html")

    return app

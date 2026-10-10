import json
from pathlib import Path

import numpy as np
import pytest
from fastapi.testclient import TestClient

from behavlab import data
from behavlab.api import create_app
from tests.conftest import needs_data

UUID = "00EABED2-271D-49D8-B599-1D4A09240601"


@pytest.fixture
def client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> TestClient:
    monkeypatch.delenv("BEHAVLAB_API_TOKEN", raising=False)
    tl = tmp_path / "tl"
    tl.mkdir()
    (tl / "index.json").write_text(json.dumps([{"uuid": UUID}]))
    (tl / f"{UUID}.json").write_text(json.dumps({"uuid": UUID, "minutes": []}))
    return TestClient(create_app(tmp_path / "results", tl, tmp_path / "static"))


def test_api_lists_pending_experiments_and_serves_timelines(client: TestClient) -> None:
    items = client.get("/api/experiments").json()["items"]
    assert {i["status"] for i in items} == {"pending"} and len(items) == 5
    assert client.get("/api/ablation").status_code == 404
    assert client.get("/api/people").json()["items"][0]["uuid"] == UUID
    assert client.get(f"/api/people/{UUID}").json()["uuid"] == UUID
    assert client.get("/api/people/..%2F..%2Fetc").status_code == 404
    assert client.get("/api/people/not-a-uuid").status_code == 404
    assert client.post("/api/experiments").status_code == 405
    r = client.get("/api/health")
    assert r.headers["x-frame-options"] == "DENY" and "default-src 'self'" in r.headers["content-security-policy"]


def test_api_token(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("BEHAVLAB_API_TOKEN", "s3cret")
    c = TestClient(create_app(tmp_path, tmp_path, tmp_path))
    assert c.get("/api/health").status_code == 200
    assert c.get("/api/experiments").status_code == 401
    assert c.get("/api/experiments", headers={"Authorization": "Bearer s3cret"}).status_code == 200


@needs_data
def test_real_archive_matches_the_paper_and_local_time_checks_out() -> None:
    assert len(data.users()) == data.EXPECTED_USERS
    u = data.load_user(UUID)
    assert u.n == 2287 and (np.diff(u.ts) > 0).all()
    assert data.timezone_agreement(u) > 0.9
    assert u.features["acc"].shape[1] == 26 and u.features["gyro"].shape[1] == 26

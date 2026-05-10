"""FastAPI upload route — wiring only; pipeline mocked where noted."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from src.api.app import app


@pytest.fixture
def client(monkeypatch: pytest.MonkeyPatch, tmp_path):
    monkeypatch.setattr("src.api.app.repo_root", lambda: tmp_path)
    return TestClient(app)


def test_upload_valid_csv_invokes_pipeline(monkeypatch: pytest.MonkeyPatch, tmp_path):
    monkeypatch.setattr("src.api.app.repo_root", lambda: tmp_path)
    called: list = []
    monkeypatch.setattr(
        "src.api.app.run_health_pipeline",
        lambda repo: called.append(repo),
    )
    c = TestClient(app)
    body = "date,steps\n2026-05-09,100\n"
    res = c.post("/upload", files={"file": ("universal.csv", body, "text/csv")})
    assert res.status_code == 200
    assert res.json() == {"status": "ok"}
    assert len(called) == 1
    assert (tmp_path / "rawdata" / "universal.csv").read_text(encoding="utf-8") == body


def test_upload_invalid_csv_returns_error(client: TestClient) -> None:
    res = client.post(
        "/upload",
        files={"file": ("bad.csv", "not,a,header\n1,2,3\n", "text/csv")},
    )
    assert res.status_code == 400
    data = res.json()
    assert "error" in data
    assert "date" in data["error"].lower()

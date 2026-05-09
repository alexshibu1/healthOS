"""Tests for SnapshotData JSON emitted by src/report/snapshot_builder.py."""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path

import pandas as pd
import pytest

from src.report.snapshot_builder import SnapshotBuildError, build_snapshot


def _contrib_json_stub() -> str:
    return json.dumps(
        [
            {
                "name": "sri",
                "years_pulled": 0.25,
                "share_of_total": 0.4,
                "rationale": "SRI mildly below anchor.",
            },
            {
                "name": "hrv_trend",
                "years_pulled": -0.05,
                "share_of_total": 0.2,
                "rationale": "Mild favorable drift.",
            },
            {
                "name": "rhr_baseline",
                "years_pulled": 0.3,
                "share_of_total": 0.4,
                "rationale": "RHR creep vs baseline.",
            },
        ]
    )


def _write_min_repo(tmp_root: Path) -> None:
    scores = tmp_root / "data" / "scores"
    scores.mkdir(parents=True)
    rng = pd.date_range("2024-11-01", "2025-06-05", freq="D")
    n = len(rng)

    composite = pd.DataFrame({
        "date": rng.date,
        "state": ["recovered"] * (n - 2) + ["insufficient_data", "recovered"],
        "score": [72] * (n - 5) + [60, 60, 60, 0, 73],
        "primary_signal": ["nlr_hrv"] * n,
        "divergence_flags": json.dumps([]),
        "reasoning": ["State: recovered."] * (n - 2) + ["Insufficient data.", "State: recovered."],
        "confidence": [0.88] * n,
    })
    composite.loc[composite["state"] == "insufficient_data", "score"] = 0
    composite.loc[composite["state"] == "insufficient_data", "confidence"] = 0.3
    composite.to_parquet(scores / "composite.parquet", index=False)

    nlr = pd.DataFrame({
        "date": rng.date,
        "score": [0.92] * (n - 1) + [0.0],
        "tier": ["green"] * (n - 2) + ["unknown", "green"],
        "confidence": [0.9] * n,
        "reasoning": [
            ("Insufficient HRV baseline: 2 valid day(s). Spec §4.4." if i == n - 2 else "Green fuse.")
            for i in range(n)
        ],
    })
    nlr.to_parquet(scores / "nlr_hrv.parquet", index=False)

    sri = pd.DataFrame({
        "date": rng.date,
        "score": [74] * n,
        "tier": ["moderate"] * (n - 2) + ["unknown", "moderate"],
        "reasoning": [""] * n,
        "window_days": [14] * n,
    })
    sri.to_parquet(scores / "sri.parquet", index=False)

    ado = pd.DataFrame({
        "date": rng.date,
        "zscore": [(i % 7) / 10.0 - 0.2 for i in range(n)],
        "tier": ["drift"] * (n - 2) + ["unknown", "drift"],
        "reasoning": [""] * n,
        "window_days": [30] * n,
    })
    ado.to_parquet(scores / "aerobic_decoupling.parquet", index=False)

    cjson = _contrib_json_stub()
    bio = pd.DataFrame({
        "date": rng.date,
        "proxy_age": [22.8] * n,
        "gap_years": [1.8] * n,
        "contributors_json": [cjson] * n,
    })
    bio.to_parquet(scores / "bio_age.parquet", index=False)

    (tmp_root / "data" / "profile.yaml").write_text("age: 21\nsex: male\n", encoding="utf-8")

    yaml_txt = """illness_windows:
  - start: '2025-01-01'
    end: '2025-01-07'
    note: 'test window'
travel_windows: []
injury_windows: []
"""
    (tmp_root / "data" / "context_flags.yaml").write_text(yaml_txt, encoding="utf-8")


_SNAPSHOT_KEYS = {
    "state",
    "score",
    "todayDelta",
    "subline",
    "action",
    "todayReasoning",
    "monthlyContext",
    "monthlyTrajectory",
    "monthlyHistory",
    "sevenDayState",
    "secondaryReadouts",
    "streams",
    "flagship",
    "divergence",
    "interventions",
}


def test_snapshot_top_level_contract(tmp_path: Path) -> None:
    _write_min_repo(tmp_path)
    scoring = date(2025, 5, 22)
    snap = build_snapshot(scoring, repo_root=tmp_path.resolve())
    assert _SNAPSHOT_KEYS <= set(snap.keys())
    assert isinstance(snap["flagship"]["nlrHrv"]["sparkline"], list)


def test_insufficient_sets_today_em_dash(tmp_path: Path) -> None:
    _write_min_repo(tmp_path)
    scoring = date(2025, 6, 4)
    snap = build_snapshot(scoring, repo_root=tmp_path.resolve())
    assert snap["state"] == "insufficient_data"
    assert snap["todayScoreDisplay"] == "—"
    assert snap["flagship"]["nlrHrv"]["displayScore"] == "—"


def test_raises_on_missing_scores(tmp_path: Path) -> None:
    """Refuse startup when parquet directory empty."""

    (tmp_path / "data").mkdir(parents=True)
    (tmp_path / "data" / "scores").mkdir()
    (tmp_path / "data" / "profile.yaml").write_text("age: 21\nsex: male\n", encoding="utf-8")
    (tmp_path / "data" / "context_flags.yaml").write_text(
        "illness_windows: []\ntravel_windows: []\ninjury_windows: []\n",
        encoding="utf-8",
    )
    with pytest.raises(SnapshotBuildError) as ei:
        build_snapshot(date(2025, 1, 1), repo_root=tmp_path.resolve())
    assert "composite.parquet" in str(ei.value)

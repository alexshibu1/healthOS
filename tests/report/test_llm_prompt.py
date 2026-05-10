"""Tests for ``src.report.llm_prompt``."""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

_REPO = Path(__file__).resolve().parents[2]

pytest.importorskip("yaml")


def test_build_prompt_nonempty_and_markers() -> None:
    from src.report.llm_prompt import build_recommendation_prompt

    snap = _REPO / "web" / "src" / "data" / "snapshot.json"
    profile = _REPO / "data" / "examples" / "alex_demo" / "profile.yaml"
    skill = _REPO / "skills" / "health-reasoning.md"
    os.environ["CONTEXT_FLAGS"] = str(
        _REPO / "data" / "examples" / "alex_demo" / "context_flags.yaml"
    )
    text = build_recommendation_prompt(snap, profile, skill)
    assert text.strip()
    markers = (
        "## Your role",
        "## The user",
        "## Today's reading",
        "## Three flagship lenses",
        "## Output format",
    )
    for m in markers:
        assert m in text, f"missing marker {m!r}"


def test_insufficient_data_called_out_in_todays_reading(tmp_path: Path) -> None:
    from src.report.llm_prompt import build_recommendation_prompt

    minimal = {
        "state": "insufficient_data",
        "score": 0,
        "todayReasoning": (
            "insufficient_data — wedge unknown. Composite scorer confidence `0.30`."
        ),
        "monthlyTrajectory": {"month": "May 2026", "todayDayOfMonth": 9},
        "subline": "",
        "action": "",
        "flagship": {
            "nlrHrv": {"tier": "unknown"},
            "sri": {"score": 65, "tier": "irregular", "windowDays": 14},
            "decoupling": {"tier": "unknown", "windowDays": 30},
        },
        "divergence": {"triggered": False},
    }
    snap_path = tmp_path / "snap.json"
    snap_path.write_text(json.dumps(minimal), encoding="utf-8")
    profile = _REPO / "data" / "examples" / "alex_demo" / "profile.yaml"
    skill = _REPO / "skills" / "health-reasoning.md"
    text = build_recommendation_prompt(snap_path, profile, skill)
    assert "insufficient_data" in text
    idx = text.index("## Today's reading")
    chunk = text[idx : idx + 800]
    assert "insufficient_data" in chunk

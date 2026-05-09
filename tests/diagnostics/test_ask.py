"""Tests for src/diagnostics/ask.py — four spec-mandated cases."""

from __future__ import annotations

import csv
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import pytest

from src.diagnostics.ask import (
    active_diagnostic_flags,
    get_priority_questions,
    log_answer,
)
from src.score.composite import NlrHrvInput, score_day


# ── shared test YAML (minimal subset; no SRI/EF triggers needed here) ──────────

_QUESTIONS_YAML = """\
questions:
  - id: recent_illness_check
    trigger: "divergence=autonomic_leading_nlr_elevated"
    question: "Illness symptoms in past 7 days?"
    answer_type: binary
    options:
      yes_illness: "Yes"
      no: "No"
    shift_potential: 0.85
    decay_days: 7
    effects:
      yes_illness: {illness: true}
      no: {}
    effect_template: "Illness flagged."

  - id: hard_workout_yesterday
    trigger: "divergence=convergent_stress"
    question: "Max-effort session yesterday?"
    answer_type: binary
    options:
      yes_hard: "Yes"
      no: "No"
    shift_potential: 0.60
    decay_days: 2
    effects:
      yes_hard: {hard_workout_confound: true}
      no: {}
    effect_template: "Hard workout flagged."
"""


@pytest.fixture()
def questions_file(tmp_path: Path) -> Path:
    p = tmp_path / "diagnostic_questions.yaml"
    p.write_text(_QUESTIONS_YAML, encoding="utf-8")
    return p


# ── Test 1: priority ranking ────────────────────────────────────────────────────

def test_priority_questions_sorted_by_shift_potential(questions_file: Path):
    """Questions matching snapshot are sorted by shift_potential descending."""
    snapshot = {
        "divergence_flags": ["autonomic_leading_nlr_elevated", "convergent_stress"]
    }
    result = get_priority_questions(snapshot, questions_path=questions_file)
    assert len(result) == 2
    # recent_illness_check has shift_potential 0.85 > hard_workout_yesterday 0.60
    assert result[0]["id"] == "recent_illness_check"
    assert result[1]["id"] == "hard_workout_yesterday"
    assert result[0]["shift_potential"] > result[1]["shift_potential"]


# ── Test 2: answer logging with expiry ─────────────────────────────────────────

def test_log_answer_writes_correct_row(questions_file: Path, tmp_path: Path):
    """log_answer appends one row; expires_at_utc = ts + decay_days."""
    answers_path = tmp_path / "answers.csv"
    ts = datetime(2026, 5, 8, 10, 0, 0, tzinfo=timezone.utc)

    log_answer(
        "recent_illness_check",
        "yes_illness",
        ts,
        questions_path=questions_file,
        answers_path=answers_path,
    )

    assert answers_path.exists()
    rows = list(csv.DictReader(answers_path.open()))
    assert len(rows) == 1
    row = rows[0]
    assert row["question_id"] == "recent_illness_check"
    assert row["answer_value"] == "yes_illness"
    assert row["ts_utc"] == "2026-05-08T10:00:00Z"
    # decay_days=7 → expires 2026-05-15
    assert row["expires_at_utc"] == "2026-05-15T10:00:00Z"


# ── Test 3: expired flag filtering ─────────────────────────────────────────────

def test_active_diagnostic_flags_ignores_expired(questions_file: Path, tmp_path: Path):
    """An expired answer (expires_at_utc in the past) produces no flags."""
    answers_path = tmp_path / "answers.csv"
    # Write a row that expired yesterday
    past_ts = datetime(2026, 4, 1, 0, 0, 0, tzinfo=timezone.utc)
    log_answer(
        "recent_illness_check",
        "yes_illness",
        past_ts,
        questions_path=questions_file,
        answers_path=answers_path,
    )

    flags = active_diagnostic_flags(
        date(2026, 5, 8),
        questions_path=questions_file,
        answers_path=answers_path,
    )
    assert flags == {}


# ── Test 4: composite state shift after diagnostic answer ──────────────────────

def test_composite_shifts_to_illness_risk_with_diagnostic_illness():
    """
    A C1 input in deload tier + diagnostic illness=True → illness-risk state.
    Reasoning must contain 'diagnostic answer' (provenance attribution).
    """
    c1 = NlrHrvInput(
        tier="deload",
        score=2.5,
        confidence=0.75,
        nlr_term=1.4,
        hrv_term=0.9,
    )
    result = score_day(
        date(2026, 5, 8),
        c1,
        context_flags={"illness": False, "travel": False, "injury": False},
        diagnostic_flags={"illness": True},
    )
    assert result.state == "illness-risk"
    assert "diagnostic answer" in result.reasoning

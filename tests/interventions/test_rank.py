"""Tests for intervention lookup ranking."""

from __future__ import annotations

from pathlib import Path

from src.interventions.rank import rank_interventions, trigger_matches, write_interventions_json


def test_trigger_equals_and_and():
    snap = {"state": "deload", "illness_active": True}
    assert trigger_matches("state=deload AND illness_active", snap)


def test_trigger_comparison_numeric():
    snap = {"sri_score": 65}
    assert trigger_matches("sri_score<70", snap)


def test_rank_interventions_top_three_high_impact_order(tmp_path: Path):
    lookup = Path(__file__).resolve().parents[2] / "src" / "interventions" / "lookup.yaml"
    snap = {
        "state": "deload",
        "illness_active": True,
        "nlr_value": 5.37,
        "sri_value": 65,
        "readiness_score": 48,
        "gap_years": 3.1,
        "target_time": "23:00",
        "subjective_energy_1_10": 4,
    }
    out = rank_interventions(snap, lookup_path=lookup, limit=3)
    assert len(out) == 3
    impacts = [x["impact"] for x in out]
    assert impacts[0] == "HIGH"
    write_interventions_json(out, as_of_date="2026-04-30", out_dir=tmp_path)
    assert (tmp_path / "2026-04-30.json").exists()

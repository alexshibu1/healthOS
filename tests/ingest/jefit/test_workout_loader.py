"""
tests/ingest/jefit/test_workout_loader.py
Tests for the JeFit EXERCISE LOGS loader.
"""

from pathlib import Path

import pytest

from src.ingest.jefit.workout_loader import load

FIXTURES    = Path(__file__).parent / "fixtures"
JEFIT_CSV   = FIXTURES / "exercise_logs_fixture.csv"
ROOT        = FIXTURES


def _load():
    return load(JEFIT_CSV, rawdata_root=ROOT)


def test_load_returns_10_observations():
    """10 exercise log rows → 10 observations, no rejects."""
    obs, rej = _load()
    assert len(obs) == 10
    assert len(rej) == 0


def test_volume_kg_calculation_barbell_deadlift():
    """
    Row 1 (Barbell Deadlift): "44.10x5,44.10x5,88.20x5"
    volume_lbs = (44.10*5 + 44.10*5 + 88.20*5) = 882
    volume_kg  = 882 * 0.453592 ≈ 400.068
    """
    obs, _ = _load()
    deadlift = next(
        o for o in obs if o.payload["exercise_name"] == "Barbell Deadlift"
    )
    expected_volume_kg = (44.10 * 5 + 44.10 * 5 + 88.20 * 5) * 0.453592
    assert deadlift.value_numeric == pytest.approx(expected_volume_kg, rel=1e-4)
    assert deadlift.value_unit == "kg"


def test_sets_payload_populated():
    """
    Payload must include sets_kg, sets_lbs, num_sets, and exercise_name.
    Verified on the Barbell Military Press row (3 sets).
    """
    obs, _ = _load()
    press = next(
        o for o in obs if o.payload["exercise_name"] == "Barbell Military Press"
    )
    assert press.payload["num_sets"] == 3
    assert len(press.payload["sets_lbs"]) == 3
    assert len(press.payload["sets_kg"]) == 3
    # sets_lbs should all be 11.03
    for weight, _ in press.payload["sets_lbs"]:
        assert weight == pytest.approx(11.03)


def test_ts_utc_from_unix_logtime():
    """
    Row 1: logTime=1689782037 (Unix UTC).
    1689782037 → 2023-07-19 20:13:57 UTC.
    """
    from datetime import datetime, timezone
    obs, _ = _load()
    deadlift = next(
        o for o in obs if o.payload["exercise_name"] == "Barbell Deadlift"
    )
    expected = datetime(2023, 7, 19, 15, 53, 57, tzinfo=timezone.utc)
    assert deadlift.ts_utc == expected
    assert deadlift.tz_original == "UTC"


def test_observation_ids_are_deterministic():
    """Two loads of the same file produce identical observation_ids."""
    obs1, _ = _load()
    obs2, _ = _load()
    assert [o.observation_id for o in obs1] == [o.observation_id for o in obs2]

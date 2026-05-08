"""
tests/ingest/strava/test_loader.py
Tests for the Strava activities.csv loader.
"""

from pathlib import Path

import pytest

from src.ingest.strava.loader import load, _dedup_fieldnames

FIXTURES       = Path(__file__).parent / "fixtures"
ACTIVITIES_CSV = FIXTURES / "activities_fixture.csv"
ROOT           = FIXTURES


def _load(tz="America/New_York"):
    return load(ACTIVITIES_CSV, tz_name=tz, rawdata_root=ROOT)


def test_five_parent_workout_session_events():
    """5 activities in fixture → 5 parent workout_session observations."""
    obs, rej = _load()
    parents = [o for o in obs if o.metric_kind == "workout_session"]
    assert len(parents) == 5
    assert len(rej) == 0


def test_components_created_for_non_zero_metrics():
    """
    Component observations exist for each non-zero metric.
    The two run activities have distance, moving_time, avg_hr, etc.
    At least one workout_distance component must be present.
    """
    obs, _ = _load()
    components = [o for o in obs if o.metric_kind != "workout_session"]
    assert len(components) > 0
    metric_kinds = {o.metric_kind for o in components}
    assert "workout_distance" in metric_kinds
    assert "workout_moving_time" in metric_kinds


def test_dedup_fieldnames_renames_duplicates():
    """_dedup_fieldnames must append _2, _3 to repeated column names."""
    header = ["Distance", "Elapsed Time", "Distance", "Max Heart Rate",
              "Commute", "Distance", "Max Heart Rate"]
    result = _dedup_fieldnames(header)
    assert result == [
        "Distance", "Elapsed Time", "Distance_2",
        "Max Heart Rate", "Commute", "Distance_3", "Max Heart Rate_2",
    ]


def test_avg_pace_derived_from_average_speed():
    """
    Run activity (Activity ID 18378776863): Average Speed=2.211 m/s.
    Expected avg pace = 1000 / 2.211 ≈ 452.3 s/km.
    """
    obs, _ = _load()
    pace_obs = [o for o in obs
                if o.metric_kind == "workout_avg_pace"
                and "18378776863" in o.source_row_id]
    assert len(pace_obs) == 1
    expected_pace = 1000.0 / 2.211
    assert pace_obs[0].value_numeric == pytest.approx(expected_pace, rel=1e-3)
    assert pace_obs[0].value_unit == "s_per_km"


def test_tz_assumed_flag_on_all_observations():
    """Every observation (parent and component) must carry 'tz_assumed' flag."""
    obs, _ = _load()
    for o in obs:
        assert "tz_assumed" in o.quality_flags, (
            f"Missing tz_assumed on {o.observation_id} ({o.metric_kind})"
        )

"""
tests/ingest/amazfit/test_activity_loader.py
Tests for the Amazfit activity loader (ACTIVITY, ACTIVITY_MINUTE, ACTIVITY_STAGE).
"""

from datetime import timezone
from pathlib import Path

import pytest

from src.ingest.amazfit.activity_loader import load

FIXTURES      = Path(__file__).parent / "fixtures"
ACTIVITY_CSV  = FIXTURES / "activity_fixture.csv"
MINUTE_CSV    = FIXTURES / "activity_minute_fixture.csv"
STAGE_CSV     = FIXTURES / "activity_stage_fixture.csv"
ROOT          = FIXTURES


def _load(tz="America/New_York"):
    return load(ACTIVITY_CSV, MINUTE_CSV, STAGE_CSV,
                tz_name=tz, rawdata_root=ROOT)


def test_daily_emits_four_metrics_per_day():
    """
    activity_fixture.csv has 10 rows, each with steps/distance/runDistance/calories.
    Expect 40 observations from the daily section.
    """
    obs, rej = _load()
    daily = [o for o in obs if o.source_section == "ACTIVITY"]
    assert len(daily) == 40
    metric_kinds = {o.metric_kind for o in daily}
    assert metric_kinds == {
        "activity_steps", "activity_distance",
        "activity_run_distance", "activity_calories",
    }


def test_minute_stream_observations():
    """
    activity_minute_fixture.csv has 10 data rows → 10 stream observations.
    """
    obs, rej = _load()
    minute = [o for o in obs if o.source_section == "ACTIVITY_MINUTE"]
    assert len(minute) == 10
    for o in minute:
        assert o.cadence_kind == "stream"
        assert o.metric_kind == "activity_steps_minute"
        assert o.value_unit == "count"


def test_stage_events_count():
    """
    activity_stage_fixture.csv has 10 data rows → 10 event observations.
    Each must have ts_end_utc set (start/stop interval).
    """
    obs, rej = _load()
    stages = [o for o in obs if o.source_section == "ACTIVITY_STAGE"]
    assert len(stages) == 10
    for o in stages:
        assert o.cadence_kind == "event"
        assert o.metric_kind == "activity_stage"
        assert o.ts_end_utc is not None
        assert o.ts_end_utc >= o.ts_utc


def test_daily_ts_utc_is_local_midnight():
    """
    Daily rows use midnight of the local date as ts_utc.
    2026-01-05 midnight in America/New_York (EST=UTC-5) → 05:00 UTC.
    """
    obs, _ = _load()
    jan05 = [o for o in obs
             if o.source_section == "ACTIVITY" and "2026-01-05" in o.ts_original]
    assert len(jan05) == 4   # 4 metrics for Jan 05
    for o in jan05:
        assert o.ts_utc.hour == 5
        assert o.ts_utc.minute == 0
        assert o.ts_utc.tzinfo is not None


def test_observation_ids_are_deterministic():
    """Two loads of the same files produce identical observation_ids."""
    obs1, _ = _load()
    obs2, _ = _load()
    assert [o.observation_id for o in obs1] == [o.observation_id for o in obs2]

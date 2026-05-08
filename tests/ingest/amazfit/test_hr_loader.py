"""
tests/ingest/amazfit/test_hr_loader.py
Tests for the Amazfit HEARTRATE_AUTO loader.
"""

from datetime import timezone
from pathlib import Path

import pytest

from src.ingest.amazfit.hr_loader import load

FIXTURES = Path(__file__).parent / "fixtures"
HR_CSV   = FIXTURES / "hr_fixture.csv"
ROOT     = FIXTURES   # rel_path computed from here


def test_load_returns_10_stream_observations():
    """10 data rows → 10 stream observations, no rejects."""
    obs, rej = load(HR_CSV, tz_name="America/New_York", rawdata_root=ROOT)
    assert len(obs) == 10
    assert len(rej) == 0


def test_metric_kind_and_cadence_kind():
    """Every observation must be metric_kind='hr' and cadence_kind='stream'."""
    obs, _ = load(HR_CSV, tz_name="America/New_York", rawdata_root=ROOT)
    for o in obs:
        assert o.metric_kind == "hr"
        assert o.cadence_kind == "stream"
        assert o.value_unit == "bpm"


def test_observation_ids_are_deterministic():
    """Two loads of the same file produce identical observation_ids."""
    obs1, _ = load(HR_CSV, tz_name="America/New_York", rawdata_root=ROOT)
    obs2, _ = load(HR_CSV, tz_name="America/New_York", rawdata_root=ROOT)
    ids1 = [o.observation_id for o in obs1]
    ids2 = [o.observation_id for o in obs2]
    assert ids1 == ids2


def test_ts_utc_reconstructed_from_local_time():
    """
    First row: date=2026-01-05, time=17:17, America/New_York (EST = UTC-5).
    Expected UTC: 2026-01-05 22:17:00+00:00.
    """
    obs, _ = load(HR_CSV, tz_name="America/New_York", rawdata_root=ROOT)
    first = obs[0]
    assert first.ts_utc.tzinfo is not None
    assert first.ts_utc == first.ts_utc.astimezone(timezone.utc)
    assert first.ts_utc.year == 2026
    assert first.ts_utc.month == 1
    assert first.ts_utc.day == 5
    assert first.ts_utc.hour == 22
    assert first.ts_utc.minute == 17


def test_tz_assumed_flag_and_source_confidence():
    """All observations must carry 'tz_assumed' flag and source_confidence=0.75."""
    obs, _ = load(HR_CSV, tz_name="America/New_York", rawdata_root=ROOT)
    for o in obs:
        assert "tz_assumed" in o.quality_flags
        assert o.source_confidence == pytest.approx(0.75)

"""
tests/ingest/amazfit/test_sleep_loader.py

Five unit tests for src/ingest/amazfit/sleep_loader.py.

Fixtures are derived from the first 10 rows of the real SLEEP export
and the first 15 rows of the real SLEEP_MINUTE export.  No synthetic data;
no mocking of file I/O.

Design decisions validated here:
  - Sentinel row detection and flagging (not rejection)
  - Observation count matches raw row count exactly
  - Observation IDs are deterministic across repeated loads
  - UTC reconstruction from explicit +0000 offset is correct
  - SLEEP_MINUTE rows link to the correct SLEEP parent via interval containment
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import pytest

from src.ingest.amazfit.sleep_loader import (
    _extract_tz_suffix,
    _find_parent,
    _int_or_none,
    load,
)
from src.ingest.schema import make_observation_id

# ── fixture paths ─────────────────────────────────────────────────────────────

FIXTURE_DIR        = Path(__file__).parent / "fixtures"
SLEEP_FIXTURE      = FIXTURE_DIR / "sleep_fixture.csv"
SLEEP_MIN_FIXTURE  = FIXTURE_DIR / "sleep_minute_fixture.csv"

# The test timezone must match what we'd use for real data.
# See config.py and sleep_loader.py docstring for the derivation.
_TEST_TZ = "America/New_York"


# ── helpers ────────────────────────────────────────────────────────────────────

def _load_fixtures(
    sleep_csv=SLEEP_FIXTURE,
    minute_csv=SLEEP_MIN_FIXTURE,
):
    """Load both fixture files; pass fixture dir as rawdata_root so
    source_file paths are relative and deterministic in tests."""
    return load(
        sleep_csv        = sleep_csv,
        sleep_minute_csv = minute_csv,
        tz_name          = _TEST_TZ,
        rawdata_root     = FIXTURE_DIR,
    )


# ── test 1 ────────────────────────────────────────────────────────────────────

def test_sentinel_row_flagged_not_rejected():
    """
    The Jan 05 row has start == stop and all durations == 0.
    It should be kept as a valid Observation with quality_flags
    containing "no_sleep_recorded".  It must NOT appear in rejects.

    Physiological rationale: the sentinel documents that no sleep was
    recorded for that night.  Silently dropping it would create a gap
    in the date series that looks like missing data rather than confirmed
    no-sleep.  The scorer needs to distinguish the two.
    """
    observations, rejects = _load_fixtures()

    sentinel_obs = [
        o for o in observations
        if o.metric_kind == "sleep_summary" and o.source_row_id == "2026-01-05"
    ]
    sentinel_rej = [
        r for r in rejects
        if r.source_row_id == "2026-01-05"
    ]

    assert len(sentinel_obs) == 1,  "sentinel row must produce exactly one Observation"
    assert len(sentinel_rej) == 0,  "sentinel row must not appear in rejects"
    assert "no_sleep_recorded" in sentinel_obs[0].quality_flags, (
        f"expected 'no_sleep_recorded' flag; got {sentinel_obs[0].quality_flags}"
    )


# ── test 2 ────────────────────────────────────────────────────────────────────

def test_sleep_event_count_matches_csv_rows():
    """
    The fixture has 10 data rows (header excluded).  The loader must
    produce exactly 10 sleep_summary events and zero rejects from
    the SLEEP file.  This guards against silent row-drops.
    """
    observations, rejects = _load_fixtures()

    events = [o for o in observations if o.metric_kind == "sleep_summary"]
    event_rejects = [r for r in rejects]  # there should be none at all

    assert len(events) == 10, (
        f"expected 10 sleep_summary events, got {len(events)}"
    )
    assert len(event_rejects) == 0, (
        f"expected zero rejects, got {len(event_rejects)}: "
        + "; ".join(str(r.reasons) for r in event_rejects)
    )


# ── test 3 ────────────────────────────────────────────────────────────────────

def test_observation_ids_are_deterministic():
    """
    Loading the same fixture twice must produce byte-identical observation_ids
    in the same order.

    This verifies the idempotency contract from schema.md §Identity rule:
    re-ingesting the same file must produce the same IDs so an
    "insert or replace" strategy never creates duplicate rows.
    """
    obs_first,  _ = _load_fixtures()
    obs_second, _ = _load_fixtures()

    ids_first  = [o.observation_id for o in obs_first]
    ids_second = [o.observation_id for o in obs_second]

    assert ids_first == ids_second, (
        "observation_ids are not deterministic across repeated loads"
    )


# ── test 4 ────────────────────────────────────────────────────────────────────

def test_ts_utc_parsed_correctly_from_explicit_offset():
    """
    SLEEP row for 2026-01-06 has:
        start = "2026-01-06 05:50:00+0000"
        stop  = "2026-01-06 13:42:00+0000"

    Both carry an explicit +0000 offset → should be parsed as exact UTC
    instants with no timezone conversion guesswork.

    Also verifies tz_original is the verbatim offset string "+0000",
    not an IANA name (since the source file explicitly provided the offset).
    """
    observations, _ = _load_fixtures()

    jan06 = next(
        (o for o in observations
         if o.metric_kind == "sleep_summary" and o.source_row_id == "2026-01-06"),
        None,
    )

    assert jan06 is not None, "observation for 2026-01-06 not found"

    expected_start = datetime(2026, 1, 6, 5, 50, 0, tzinfo=timezone.utc)
    expected_stop  = datetime(2026, 1, 6, 13, 42, 0, tzinfo=timezone.utc)

    assert jan06.ts_utc     == expected_start, (
        f"ts_utc mismatch: expected {expected_start}, got {jan06.ts_utc}"
    )
    assert jan06.ts_end_utc == expected_stop, (
        f"ts_end_utc mismatch: expected {expected_stop}, got {jan06.ts_end_utc}"
    )
    assert jan06.tz_original == "+0000", (
        f"tz_original should be '+0000' (verbatim from source), got {jan06.tz_original!r}"
    )
    assert jan06.ts_original == "2026-01-06 05:50:00+0000", (
        f"ts_original must be the verbatim source string, got {jan06.ts_original!r}"
    )


# ── test 5 ────────────────────────────────────────────────────────────────────

def test_sleep_minute_rows_link_to_jan07_parent():
    """
    The SLEEP_MINUTE fixture has 15 rows, all at 2026-01-07 00:50–01:04 local.

    Using America/New_York (EST = UTC-5 in January):
        00:50 local → 05:50 UTC
        01:04 local → 06:04 UTC

    The Jan 07 SLEEP event spans 2026-01-07T05:10Z – 2026-01-07T13:16Z.
    All 15 epochs (05:50–06:04 UTC) fall strictly inside that window.

    Assertions:
      - All 15 stream rows have a non-null parent_event_id.
      - That parent_event_id matches the observation_id of the Jan 07 event.
      - No stream row carries the "orphan_stream_row" flag.

    This validates the UTC interval-containment linking strategy and the
    timezone reconstruction logic together (quirks 3 and 7 from docstring).
    """
    observations, rejects = _load_fixtures()

    stream_rows = [o for o in observations if o.metric_kind == "sleep_stage"]
    assert len(stream_rows) == 15, (
        f"expected 15 sleep_stage rows from fixture, got {len(stream_rows)}"
    )

    # Compute the expected parent_event_id using the same formula as the loader
    jan07_parent_id = make_observation_id(
        source         = "amazfit",
        source_file    = SLEEP_FIXTURE.name,  # relative to FIXTURE_DIR
        source_section = "SLEEP",
        source_row_id  = "2026-01-07",
        metric_kind    = "sleep_summary",
    )

    for obs in stream_rows:
        assert obs.parent_event_id is not None, (
            f"stream row {obs.source_row_id} has no parent_event_id"
        )
        assert obs.parent_event_id == jan07_parent_id, (
            f"stream row {obs.source_row_id} linked to wrong parent: "
            f"expected {jan07_parent_id}, got {obs.parent_event_id}"
        )
        assert "orphan_stream_row" not in obs.quality_flags, (
            f"stream row {obs.source_row_id} unexpectedly flagged as orphan"
        )

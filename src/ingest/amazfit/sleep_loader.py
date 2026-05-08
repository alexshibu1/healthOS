"""
src/ingest/amazfit/sleep_loader.py
Amazfit Helio — sleep data loader.

Reads two source files and returns observations conforming to schema.md:

  SLEEP/SLEEP_*.csv
      One row per night → one `event` observation per row.
      metric_kind = "sleep_summary"
      payload carries the four duration buckets and raw naps JSON.

  SLEEP_MINUTE/SLEEP_MINUTE_*.csv
      One row per minute of sleep → one `stream` observation per row.
      metric_kind = "sleep_stage"
      value_text ∈ {LIGHT, DEEP, REM, WAKE}
      payload carries hr and respiratory_rate (frequently null).

Quirks handled
──────────────
1.  UTF-8 BOM in every Amazfit export file → encoding='utf-8-sig'

2.  SLEEP start/stop have an explicit UTC offset written as "+0000".
    Parsed with strptime "%Y-%m-%d %H:%M:%S%z" → directly UTC.
    tz_original is extracted from the trailing "+0000" suffix verbatim.

3.  SLEEP_MINUTE carries no inline timezone.  date+time columns are
    LOCAL time in the user's wall-clock timezone.  We reconstruct UTC
    via config.USER_TZ (default "America/New_York").
    Rationale: SLEEP start=2026-01-07T05:10Z; first SLEEP_MINUTE epoch
    is 2026-01-07 00:50 local.  With UTC-5 (EST Jan) → 05:50 UTC, which
    is 40 min inside the session.  UTC-4 gives 04:50 UTC, 20 min *before*
    onset — physically impossible.  America/New_York handles the DST
    boundary automatically.  Every SLEEP_MINUTE row gets quality_flags
    += ["tz_assumed"].

4.  Sentinel row: 2026-01-05 has start == stop and all durations == 0.
    This means no sleep was recorded for that night.  The row is kept
    (not rejected) but flagged quality_flags += ["no_sleep_recorded"].
    Sentinel events are also excluded from parent-linking so a
    SLEEP_MINUTE epoch at the same instant does not incorrectly attach.

5.  naps field is sometimes a JSON array of mini-wake objects
    (e.g., '[{"start":"...","end":"..."}]').  The embedded timestamps
    appear to be test/default data (dates from 2024 inside a 2026 export).
    We preserve it raw as payload["naps_raw"] without parsing.
    schema.md rule: never alter original values.

6.  SLEEP_MINUTE hr and respiratory_rate are frequently empty (2 243 /
    55 210 rows have null hr; respiratory_rate is almost always null).
    Stored as None in payload — not promoted to typed columns because they
    are attributes of the sleep stage observation, not independent metrics.
    (See schema.md §Sleep stage handling rule.)

7.  Linking strategy: SLEEP_MINUTE rows are linked to their parent
    SLEEP event via UTC interval containment, not by date-string matching.
    Date-string matching breaks for cross-midnight sleeps (sleep starts
    23:30 local → SLEEP_MINUTE rows span two calendar dates but one
    SLEEP event).  Interval containment is always correct.
    A SLEEP_MINUTE epoch with no containing event is flagged "orphan_stream_row"
    and kept (not rejected).

Source confidence (schema.md §Source confidence ladder)
──────────────────────────────────────────────────────
  sleep_summary  0.65  actigraphy-based; not EEG
  sleep_stage    0.65  same device, same caveat

Output
──────
  load() → (list[Observation], list[Reject])
  Rejects carry the raw row and a list of violated invariants.
  The caller is responsible for writing rejects to a rejects/ table.
"""

from __future__ import annotations

import csv
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional
from zoneinfo import ZoneInfo

from src.ingest.config import RAWDATA_ROOT, USER_TZ
from src.ingest.schema import (
    Observation,
    Reject,
    make_observation_id,
    validate_observation,
)

# ── module-level constants ────────────────────────────────────────────────────

_SOURCE         = "amazfit"
_SECTION_SLEEP  = "SLEEP"
_SECTION_MINUTE = "SLEEP_MINUTE"

# schema.md §Source confidence ladder
_CONF_SLEEP_SUMMARY = 0.65
_CONF_SLEEP_STAGE   = 0.65

# strptime format for SLEEP start/stop columns: "2026-01-06 05:50:00+0000"
_TS_FMT = "%Y-%m-%d %H:%M:%S%z"


# ── public API ────────────────────────────────────────────────────────────────

def load(
    sleep_csv: Path,
    sleep_minute_csv: Path,
    tz_name: str = USER_TZ,
    rawdata_root: Optional[Path] = None,
) -> tuple[list[Observation], list[Reject]]:
    """
    Normalise Amazfit sleep exports into unified schema observations.

    Parameters
    ----------
    sleep_csv :
        Path to SLEEP/SLEEP_*.csv (nightly summaries).
    sleep_minute_csv :
        Path to SLEEP_MINUTE/SLEEP_MINUTE_*.csv (per-minute stages).
    tz_name :
        IANA timezone for SLEEP_MINUTE local-time reconstruction.
        Defaults to config.USER_TZ.  Override in tests or for travel periods.
    rawdata_root :
        Root directory used to build relative source_file paths.
        Defaults to config.RAWDATA_ROOT.  Override in tests.

    Returns
    -------
    (observations, rejects)
        observations : valid Observation rows, events first then stream.
        rejects      : rows that failed schema validation, with reasons.
    """
    root = rawdata_root or RAWDATA_ROOT

    events, event_rejects   = _load_sleep_events(sleep_csv, tz_name, root)
    stream, stream_rejects  = _load_sleep_stream(sleep_minute_csv, events, tz_name, root)

    return events + stream, event_rejects + stream_rejects


# ── SLEEP summary events ──────────────────────────────────────────────────────

def _load_sleep_events(
    sleep_csv: Path,
    tz_name: str,
    rawdata_root: Path,
) -> tuple[list[Observation], list[Reject]]:
    """
    Read SLEEP_*.csv → one `event` Observation per row.

    Columns used:
        date              local calendar date of sleep onset (YYYY-MM-DD)
        deepSleepTime     deep sleep minutes
        shallowSleepTime  light sleep minutes  (Amazfit calls it "shallow")
        wakeTime          wake minutes
        REMTime           REM minutes
        start             UTC datetime with explicit offset, e.g. "2026-01-06 05:50:00+0000"
        stop              same format
        naps              empty or JSON array of mini-wake objects
    """
    rel_path   = _rel(sleep_csv, rawdata_root)
    observations: list[Observation] = []
    rejects:      list[Reject]      = []

    with open(sleep_csv, encoding="utf-8-sig", newline="") as fh:
        reader = csv.DictReader(fh)

        for row in reader:
            source_row_id = row["date"].strip()
            start_str     = row["start"].strip()
            stop_str      = row["stop"].strip()

            # ── parse UTC timestamps ──
            try:
                ts_utc     = datetime.strptime(start_str, _TS_FMT).astimezone(timezone.utc)
                ts_end_utc = datetime.strptime(stop_str,  _TS_FMT).astimezone(timezone.utc)
            except ValueError as exc:
                rejects.append(Reject(
                    source        = _SOURCE,
                    source_file   = rel_path,
                    source_row_id = source_row_id,
                    raw_row       = dict(row),
                    reasons       = [f"timestamp parse error: {exc}"],
                ))
                continue

            # ── quality flags ──
            flags: list[str] = []

            all_durations_zero = all(
                _int_or_none(row.get(k)) in (0, None)
                for k in ("deepSleepTime", "shallowSleepTime", "wakeTime", "REMTime")
            )
            if ts_utc == ts_end_utc and all_durations_zero:
                # sentinel row: watch recorded no sleep this night
                flags.append("no_sleep_recorded")

            if ts_end_utc < ts_utc:
                flags.append("invalid_interval")

            # ── tz_original ──
            # start_str ends with "+0000"; extract that suffix as the canonical
            # representation of the timezone as it appears in the source file.
            tz_original = _extract_tz_suffix(start_str) or "+0000"

            # ── payload ──
            naps_raw = row.get("naps", "").strip()
            payload = {
                "deep_min":      _int_or_none(row.get("deepSleepTime")),
                "light_min":     _int_or_none(row.get("shallowSleepTime")),
                "wake_min":      _int_or_none(row.get("wakeTime")),
                "rem_min":       _int_or_none(row.get("REMTime")),
                "naps_raw":      naps_raw if naps_raw else None,
                "stop_original": stop_str,
            }

            obs_id = make_observation_id(
                _SOURCE, rel_path, _SECTION_SLEEP, source_row_id, "sleep_summary"
            )

            obs = Observation(
                observation_id    = obs_id,
                source            = _SOURCE,
                source_file       = rel_path,
                source_section    = _SECTION_SLEEP,
                source_row_id     = source_row_id,
                cadence_kind      = "event",
                metric_kind       = "sleep_summary",
                ts_utc            = ts_utc,
                ts_end_utc        = ts_end_utc,
                tz_original       = tz_original,
                ts_original       = start_str,
                value_numeric     = None,
                value_unit        = None,
                value_text        = None,
                source_confidence = _CONF_SLEEP_SUMMARY,
                quality_flags     = flags,
                payload           = payload,
            )

            errs = validate_observation(obs)
            if errs:
                rejects.append(Reject(
                    source        = _SOURCE,
                    source_file   = rel_path,
                    source_row_id = source_row_id,
                    raw_row       = dict(row),
                    reasons       = errs,
                ))
            else:
                observations.append(obs)

    return observations, rejects


# ── SLEEP_MINUTE stream ───────────────────────────────────────────────────────

def _load_sleep_stream(
    sleep_minute_csv: Path,
    sleep_events: list[Observation],
    tz_name: str,
    rawdata_root: Path,
) -> tuple[list[Observation], list[Reject]]:
    """
    Read SLEEP_MINUTE_*.csv → one `stream` Observation per minute.

    Columns used:
        date               local calendar date (YYYY-MM-DD); no timezone
        time               local wall-clock time (HH:MM); no timezone
        stage              LIGHT | DEEP | REM | WAKE
        hr                 heart rate in bpm (often null late in night)
        respiratory_rate   breaths/min (almost always null in this export)

    UTC is reconstructed by localising date+time with tz_name, then
    converting to UTC.  Rows carry quality_flags = ["tz_assumed"].
    """
    rel_path   = _rel(sleep_minute_csv, rawdata_root)
    tz         = ZoneInfo(tz_name)
    observations: list[Observation] = []
    rejects:      list[Reject]      = []

    with open(sleep_minute_csv, encoding="utf-8-sig", newline="") as fh:
        reader = csv.DictReader(fh)

        for row in reader:
            date_str      = row["date"].strip()
            time_str      = row["time"].strip()
            source_row_id = f"{date_str}T{time_str}"

            # ── reconstruct UTC from local date + time ──
            try:
                year, month, day    = map(int, date_str.split("-"))
                hour, minute        = map(int, time_str.split(":"))
                local_dt            = datetime(year, month, day, hour, minute, tzinfo=tz)
                ts_utc              = local_dt.astimezone(timezone.utc)
            except (ValueError, OverflowError) as exc:
                rejects.append(Reject(
                    source        = _SOURCE,
                    source_file   = rel_path,
                    source_row_id = source_row_id,
                    raw_row       = dict(row),
                    reasons       = [f"timestamp reconstruction error: {exc}"],
                ))
                continue

            # ── quality flags ──
            flags: list[str] = ["tz_assumed"]

            # ── link to parent event via UTC interval containment ──
            # Sentinel events (no_sleep_recorded) are excluded so a stray
            # epoch at the sentinel instant does not incorrectly attach.
            parent_id = _find_parent(ts_utc, sleep_events)
            if parent_id is None:
                flags.append("orphan_stream_row")

            # ── payload ──
            hr_str = row.get("hr", "").strip()
            rr_str = row.get("respiratory_rate", "").strip()
            payload = {
                "hr":               float(hr_str) if hr_str else None,
                "respiratory_rate": float(rr_str) if rr_str else None,
            }

            obs_id = make_observation_id(
                _SOURCE, rel_path, _SECTION_MINUTE, source_row_id, "sleep_stage"
            )

            obs = Observation(
                observation_id    = obs_id,
                parent_event_id   = parent_id,
                source            = _SOURCE,
                source_file       = rel_path,
                source_section    = _SECTION_MINUTE,
                source_row_id     = source_row_id,
                cadence_kind      = "stream",
                metric_kind       = "sleep_stage",
                ts_utc            = ts_utc,
                tz_original       = tz_name,
                ts_original       = f"{date_str} {time_str}",
                value_numeric     = None,
                value_unit        = None,
                value_text        = row.get("stage", "").strip() or None,
                source_confidence = _CONF_SLEEP_STAGE,
                quality_flags     = flags,
                payload           = payload,
            )

            errs = validate_observation(obs)
            if errs:
                rejects.append(Reject(
                    source        = _SOURCE,
                    source_file   = rel_path,
                    source_row_id = source_row_id,
                    raw_row       = dict(row),
                    reasons       = errs,
                ))
            else:
                observations.append(obs)

    return observations, rejects


# ── helpers ───────────────────────────────────────────────────────────────────

def _find_parent(
    ts_utc: datetime,
    sleep_events: list[Observation],
) -> Optional[str]:
    """
    Return observation_id of the SLEEP event whose UTC interval
    [ts_utc, ts_end_utc] contains ts_utc.  Returns None if no match.

    Excludes sentinel events (no_sleep_recorded) — a sentinel has
    start == end, so it could falsely match an exact-boundary epoch.

    Complexity: O(n_events) per call.  With ~122 events × 55k minutes
    this is ~6.7 M simple datetime comparisons — negligible at this scale.
    If the dataset grows significantly, replace with an interval tree.
    """
    for event in sleep_events:
        if event.ts_end_utc is None:
            continue
        if "no_sleep_recorded" in event.quality_flags:
            continue
        if event.ts_utc <= ts_utc <= event.ts_end_utc:
            return event.observation_id
    return None


def _rel(path: Path, root: Path) -> str:
    """
    POSIX-style path relative to root.
    Falls back to the absolute path string if path is outside root
    (e.g., test fixtures in a different directory tree).
    """
    try:
        return path.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        return path.resolve().as_posix()


def _extract_tz_suffix(ts_str: str) -> Optional[str]:
    """
    Extract the timezone offset suffix from a timestamp string.
    Handles "+0000" and "-0500" style suffixes (5 chars incl. sign).

    Examples:
        "2026-01-06 05:50:00+0000" → "+0000"
        "2026-01-06 00:00:00-0500" → "-0500"
        "2026-01-06 05:50:00"      → None
    """
    for sign in ("+", "-"):
        idx = ts_str.rfind(sign)
        if idx != -1 and len(ts_str) - idx == 5:
            return ts_str[idx:]
    return None


def _int_or_none(val: Optional[str]) -> Optional[int]:
    """Convert string to int; return None for empty / null-like values."""
    if val is None or val.strip() == "":
        return None
    try:
        return int(val)
    except ValueError:
        return None

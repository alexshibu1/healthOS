"""
src/ingest/strava/loader.py
Strava activities.csv loader.

Reads activities.csv → one parent `event` per activity + component rows per metric.

Schema pattern (per schema.md):
  Parent:    metric_kind="workout_session", value_text=activity_type
  Component: metric_kind ∈ {workout_distance, workout_moving_time, workout_avg_hr,
             workout_max_hr, workout_elevation_gain, workout_calories,
             workout_avg_pace, workout_avg_power, workout_training_load}
  Components carry parent_event_id = parent observation_id.

Quirks:
1. Duplicate column names in Strava CSV: "Distance", "Elapsed Time",
   "Max Heart Rate", "Commute" each appear twice with different semantics.
   csv.DictReader overwrites on duplicate keys — we pre-read the header and
   deduplicate by appending "_2", "_3" to later occurrences.
   The raw API columns (Distance_2 = meters, Max Heart Rate_2 = bpm) are used;
   user-facing columns (Distance col 7, Max Heart Rate col 8) are ignored.

2. Activity Date ("May 7, 2026, 12:09:41 AM") is LOCAL time with no inline
   timezone. Reconstructed to UTC via config.USER_TZ.
   Every observation gets quality_flags += ["tz_assumed"].
   Caveat: activities in other timezones (e.g., a hike in Israel) will have
   incorrect UTC offsets until per-activity timezone data is available.

3. Component rows are only created for non-null, non-zero numeric values.
   This avoids a flood of zero-valued components for activity types that lack
   specific metrics (e.g., weight training has no distance).

4. workout_avg_pace is derived from Average Speed (m/s) → s/km (1000 / speed).
   Only emitted for activities with Average Speed > 0.
   Unit = s_per_km, per schema.md canonical units.

5. Strava HR zones are often miscalibrated (CLAUDE.md) → source_confidence = 0.60
   for all HR components. Pace/power/distance = 0.90–0.95.

Note on aerobic decoupling: activities.csv carries only session-level averages.
The Pa:HR decoupling spec (aerobic-decoupling-spec.md) requires per-minute
pace/HR samples from the raw .fit/.gpx files. Those are separate binary files
in the export's activities/ subdirectory. A future fit_loader.py will handle them.
The current loader produces the session envelope only.
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

_SOURCE  = "strava"
_SECTION = "activities"

# source_confidence per metric kind  (schema.md §Source confidence ladder)
_CONF: dict[str, float] = {
    "workout_session":        0.95,
    "workout_distance":       0.90,
    "workout_moving_time":    0.95,
    "workout_avg_hr":         0.60,   # CLAUDE.md: HR zones often miscalibrated
    "workout_max_hr":         0.60,
    "workout_elevation_gain": 0.90,
    "workout_calories":       0.80,
    "workout_avg_pace":       0.95,   # CLAUDE.md: trust pace over HR
    "workout_avg_power":      0.95,
    "workout_training_load":  0.85,
}

# strptime format for "May 7, 2026, 12:09:41 AM"
_DATE_FMT = "%b %d, %Y, %I:%M:%S %p"


def load(
    activities_csv: Path,
    tz_name: str = USER_TZ,
    rawdata_root: Optional[Path] = None,
) -> tuple[list[Observation], list[Reject]]:
    """
    Load Strava activities.csv → workout_session parents + component observations.

    Parameters
    ----------
    activities_csv : Path to the Strava activities.csv export.
    tz_name        : IANA timezone for Activity Date reconstruction.
    rawdata_root   : Root for relative source_file paths.
    """
    root     = rawdata_root or RAWDATA_ROOT
    rel_path = _rel(activities_csv, root)
    tz       = ZoneInfo(tz_name)

    observations: list[Observation] = []
    rejects:      list[Reject]      = []

    with open(activities_csv, encoding="utf-8", newline="") as fh:
        raw_reader  = csv.reader(fh)
        raw_header  = next(raw_reader)
        fieldnames  = _dedup_fieldnames(raw_header)

        for raw_row in raw_reader:
            # Pad short rows (some activities lack trailing columns)
            if len(raw_row) < len(fieldnames):
                raw_row = raw_row + [""] * (len(fieldnames) - len(raw_row))
            row = dict(zip(fieldnames, raw_row))

            activity_id   = row.get("Activity ID", "").strip()
            date_raw      = row.get("Activity Date", "").strip()
            activity_type = row.get("Activity Type", "").strip()
            activity_name = row.get("Activity Name", "").strip()
            source_row_id = activity_id or date_raw

            if not date_raw:
                rejects.append(Reject(
                    source=_SOURCE, source_file=rel_path,
                    source_row_id=source_row_id, raw_row=row,
                    reasons=["Activity Date is empty"],
                ))
                continue

            # ── parse local time → UTC ──
            try:
                local_dt = datetime.strptime(date_raw, _DATE_FMT)
                # Localize naive datetime to user's timezone
                local_dt = local_dt.replace(tzinfo=tz)
                ts_utc   = local_dt.astimezone(timezone.utc)
            except ValueError as exc:
                rejects.append(Reject(
                    source=_SOURCE, source_file=rel_path,
                    source_row_id=source_row_id, raw_row=row,
                    reasons=[f"date parse error on {date_raw!r}: {exc}"],
                ))
                continue

            parent_id = make_observation_id(
                _SOURCE, rel_path, _SECTION, source_row_id, "workout_session"
            )

            # ── parent event ──
            parent = Observation(
                observation_id    = parent_id,
                source            = _SOURCE,
                source_file       = rel_path,
                source_section    = _SECTION,
                source_row_id     = source_row_id,
                cadence_kind      = "event",
                metric_kind       = "workout_session",
                ts_utc            = ts_utc,
                tz_original       = tz_name,
                ts_original       = date_raw,
                value_text        = activity_type or None,
                source_confidence = _CONF["workout_session"],
                quality_flags     = ["tz_assumed"],
                payload           = {
                    "activity_name": activity_name,
                    "activity_id":   activity_id,
                    "filename":      row.get("Filename", "").strip() or None,
                },
            )
            errs = validate_observation(parent)
            if errs:
                rejects.append(Reject(
                    source=_SOURCE, source_file=rel_path,
                    source_row_id=source_row_id, raw_row=row, reasons=errs,
                ))
                continue
            observations.append(parent)

            # ── component rows ──
            components = _build_components(row, parent_id, rel_path, ts_utc, tz_name, date_raw)
            for comp in components:
                errs = validate_observation(comp)
                if errs:
                    rejects.append(Reject(
                        source=_SOURCE, source_file=rel_path,
                        source_row_id=comp.source_row_id, raw_row=row, reasons=errs,
                    ))
                else:
                    observations.append(comp)

    return observations, rejects


# ── component builder ─────────────────────────────────────────────────────────

def _build_components(
    row: dict,
    parent_id: str,
    rel_path: str,
    ts_utc: datetime,
    tz_name: str,
    ts_original: str,
) -> list[Observation]:
    """
    Emit component observations for non-null, non-zero numeric metrics.

    Each component shares ts_utc / tz_original / ts_original with the parent.
    source_row_id = f"{parent_source_row_id}:{metric_kind}" for determinism.
    """
    parent_row_id = row.get("Activity ID", "").strip() or ts_original
    components    = []

    # Ordered list of (csv_column, metric_kind, unit, converter)
    # converter: callable(str) → float | None
    specs: list[tuple[str, str, str]] = [
        ("Distance_2",        "workout_distance",       "m"),
        ("Moving Time",       "workout_moving_time",    "s"),
        ("Average Heart Rate","workout_avg_hr",         "bpm"),
        ("Max Heart Rate_2",  "workout_max_hr",         "bpm"),
        ("Elevation Gain",    "workout_elevation_gain", "m"),
        ("Calories",          "workout_calories",       "kcal"),
        ("Average Watts",     "workout_avg_power",      "W"),
        ("Training Load",     "workout_training_load",  "au"),
    ]

    for csv_col, metric_kind, unit in specs:
        val = _pos_float(row.get(csv_col, ""))
        if val is None:
            continue

        source_row_id = f"{parent_row_id}:{metric_kind}"
        obs_id        = make_observation_id(
            _SOURCE, rel_path, _SECTION, source_row_id, metric_kind
        )
        components.append(Observation(
            observation_id    = obs_id,
            parent_event_id   = parent_id,
            source            = _SOURCE,
            source_file       = rel_path,
            source_section    = _SECTION,
            source_row_id     = source_row_id,
            cadence_kind      = "event",
            metric_kind       = metric_kind,
            ts_utc            = ts_utc,
            tz_original       = tz_name,
            ts_original       = ts_original,
            value_numeric     = val,
            value_unit        = unit,
            source_confidence = _CONF.get(metric_kind, 0.80),
            quality_flags     = ["tz_assumed"],
            payload           = {},
        ))

    # ── derived: avg pace s/km from avg speed m/s ──
    avg_speed = _pos_float(row.get("Average Speed", ""))
    if avg_speed is not None and avg_speed > 0:
        pace_s_per_km = 1000.0 / avg_speed
        source_row_id = f"{parent_row_id}:workout_avg_pace"
        obs_id        = make_observation_id(
            _SOURCE, rel_path, _SECTION, source_row_id, "workout_avg_pace"
        )
        components.append(Observation(
            observation_id    = obs_id,
            parent_event_id   = parent_id,
            source            = _SOURCE,
            source_file       = rel_path,
            source_section    = _SECTION,
            source_row_id     = source_row_id,
            cadence_kind      = "event",
            metric_kind       = "workout_avg_pace",
            ts_utc            = ts_utc,
            tz_original       = tz_name,
            ts_original       = ts_original,
            value_numeric     = pace_s_per_km,
            value_unit        = "s_per_km",
            source_confidence = _CONF["workout_avg_pace"],
            quality_flags     = ["tz_assumed"],
            payload           = {"avg_speed_m_per_s": avg_speed},
        ))

    return components


# ── helpers ───────────────────────────────────────────────────────────────────

def _dedup_fieldnames(header: list[str]) -> list[str]:
    """
    Rename duplicate column names by appending _2, _3, etc.

    Strava CSV has duplicate 'Distance', 'Elapsed Time', 'Max Heart Rate',
    'Commute'. The second occurrence is the raw API value (meters, seconds, bpm).
    """
    seen:   dict[str, int] = {}
    result: list[str]      = []
    for name in header:
        if name not in seen:
            seen[name] = 1
            result.append(name)
        else:
            seen[name] += 1
            result.append(f"{name}_{seen[name]}")
    return result


def _pos_float(val: str) -> Optional[float]:
    """Return float if val is a positive number; else None."""
    if not val or not val.strip():
        return None
    try:
        f = float(val.strip())
        return f if f > 0 else None
    except ValueError:
        return None


def _rel(path: Path, root: Path) -> str:
    try:
        return path.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        return path.resolve().as_posix()

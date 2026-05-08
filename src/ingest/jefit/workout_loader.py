"""
src/ingest/jefit/workout_loader.py
JeFit backup export loader — EXERCISE LOGS section.

The JeFit backup file is a multi-section CSV where each section has its own
header row, separated by "### SECTION NAME ###" sentinel lines. This is NOT
a standard CSV — csv.DictReader cannot be used on the whole file.

Strategy: scan the file to locate the ### EXERCISE LOGS ### section, then
read only those rows with that section's schema.

Section extracted: EXERCISE LOGS
  USERID, TIMESTAMP, belongSys, logs, _id, record, mydate, eid, ename,
  day_item_id, belongsession, logTime, interval_logs, auto_generated

One Observation per exercise row (not per set — sets are in payload).

Key fields:
  logTime       Unix timestamp (UTC) of when this exercise was logged in-app.
                Used as ts_utc — the most reliable timestamp in this section.
  belongsession Unix timestamp (UTC) of the session start.
                Preserved in payload so the scorer can group by session.
  mydate        Local calendar date of the workout (YYYY-MM-DD).
  ename         Exercise name (free text).
  eid           Exercise ID (integer, links to JeFit exercise catalog).
  logs          Set logs: "weight×reps,weight×reps,..." in lbs.
  record        JeFit-computed 1RM estimate in lbs (Epley-ish formula).
  _id           Sequential exercise log ID — used as source_row_id.

Unit conversions (CLAUDE.md: SETTING.mass=" lbs"):
  All weights in `logs` and `record` are in imperial pounds.
  Converted to kg at load time: 1 lb = 0.453592 kg.
  Original lbs values preserved in payload.

value_numeric = total_volume_kg (sum of weight_kg × reps across all sets).
  For bodyweight exercises (weight=0), volume=0 but sets/reps preserved in payload.
  A "bodyweight_exercise" flag is added when all set weights == 0.

Source confidence = 0.85 (schema.md: "JeFit lift volume — user actively logs
sets; high engagement = high reliability").

Caveats:
  - TIMESTAMP column is when the record was last synced to server, NOT the
    workout date. Use logTime (Unix UTC) or mydate for temporal queries.
  - belongsession is the session start Unix timestamp and doubles as session ID.
  - record (1RM estimate) precision varies; treat as approximate.
  - This loader does NOT parse WORKOUT SESSIONS, EXERCISE SET LOGS, CARDIO LOGS,
    or other sections. Future loaders can extract those.
"""

from __future__ import annotations

import csv
import io
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from src.ingest.config import RAWDATA_ROOT
from src.ingest.schema import (
    Observation,
    Reject,
    make_observation_id,
    validate_observation,
)

_SOURCE        = "jefit"
_SECTION_NAME  = "EXERCISE LOGS"
_SECTION_LABEL = "EXERCISE_LOGS"   # used as source_section (no spaces)
_CONF          = 0.85              # schema.md: JeFit lift volume

_LBS_TO_KG     = 0.453592

# The ### sentinel that marks the start of EXERCISE LOGS
_SECTION_SENTINEL = "### EXERCISE LOGS"
# The schema of rows in this section
_EXERCISE_LOGS_HEADER = (
    "USERID,TIMESTAMP,belongSys,logs,_id,record,mydate,eid,ename,"
    "day_item_id,belongsession,logTime,interval_logs,auto_generated"
)


def load(
    jefit_csv: Path,
    rawdata_root: Optional[Path] = None,
) -> tuple[list[Observation], list[Reject]]:
    """
    Load the EXERCISE LOGS section from a JeFit backup CSV.

    Parameters
    ----------
    jefit_csv    : Path to the JeFit backup file (e.g., bigApple*.csv).
    rawdata_root : Root for relative source_file paths.
    """
    root     = rawdata_root or RAWDATA_ROOT
    rel_path = _rel(jefit_csv, root)

    section_rows = _extract_section(jefit_csv)
    if not section_rows:
        raise ValueError(
            f"EXERCISE LOGS section not found in {jefit_csv}. "
            "Check that this is a JeFit backup export."
        )

    observations: list[Observation] = []
    rejects:      list[Reject]      = []

    reader = csv.DictReader(io.StringIO("\n".join(section_rows)))

    for row in reader:
        source_row_id = row.get("_id", "").strip()
        if not source_row_id:
            continue   # blank/malformed row

        log_time_str      = row.get("logTime",       "").strip()
        belong_session_str= row.get("belongsession", "").strip()
        logs_str          = row.get("logs",          "").strip().strip('"')
        record_str        = row.get("record",        "").strip()
        exercise_name     = row.get("ename",         "").strip().strip('"')
        exercise_id       = row.get("eid",           "").strip()
        my_date           = row.get("mydate",        "").strip()

        # ── ts_utc from logTime (Unix UTC) ──
        try:
            log_time_unix = int(log_time_str)
            ts_utc        = datetime.fromtimestamp(log_time_unix, tz=timezone.utc)
        except (ValueError, OverflowError, OSError) as exc:
            rejects.append(Reject(
                source=_SOURCE, source_file=rel_path,
                source_row_id=source_row_id, raw_row=dict(row),
                reasons=[f"logTime parse error ({log_time_str!r}): {exc}"],
            ))
            continue

        # ── parse sets from logs field: "w×r,w×r,..." ──
        sets_lbs  = _parse_sets(logs_str)
        sets_kg   = [(w * _LBS_TO_KG, r) for w, r in sets_lbs]

        volume_kg = sum(w * r for w, r in sets_kg)

        flags: list[str] = []
        if sets_lbs and all(w == 0.0 for w, _ in sets_lbs):
            flags.append("bodyweight_exercise")

        # ── 1RM estimate ──
        record_lbs = _float_or_none(record_str)
        record_kg  = record_lbs * _LBS_TO_KG if record_lbs is not None else None

        # ── session ID ──
        session_ts = _int_or_none(belong_session_str)

        obs_id = make_observation_id(
            _SOURCE, rel_path, _SECTION_LABEL, source_row_id, "jefit_exercise"
        )

        obs = Observation(
            observation_id    = obs_id,
            source            = _SOURCE,
            source_file       = rel_path,
            source_section    = _SECTION_LABEL,
            source_row_id     = source_row_id,
            cadence_kind      = "event",
            metric_kind       = "jefit_exercise",
            ts_utc            = ts_utc,
            tz_original       = "UTC",   # logTime is unambiguously UTC
            ts_original       = log_time_str,
            value_numeric     = volume_kg,
            value_unit        = "kg",    # total volume = weight_kg × reps
            source_confidence = _CONF,
            quality_flags     = flags,
            payload           = {
                "exercise_name":   exercise_name,
                "exercise_id":     exercise_id,
                "mydate":          my_date,
                "session_id":      session_ts,
                "sets_logs_raw":   logs_str,
                "sets_kg":         [[round(w, 4), r] for w, r in sets_kg],
                "sets_lbs":        [[round(w, 4), r] for w, r in sets_lbs],
                "record_1rm_kg":   round(record_kg, 4) if record_kg else None,
                "record_1rm_lbs":  record_lbs,
                "num_sets":        len(sets_lbs),
            },
        )

        errs = validate_observation(obs)
        if errs:
            rejects.append(Reject(
                source=_SOURCE, source_file=rel_path,
                source_row_id=source_row_id, raw_row=dict(row), reasons=errs,
            ))
        else:
            observations.append(obs)

    return observations, rejects


# ── section extractor ─────────────────────────────────────────────────────────

def _extract_section(csv_path: Path) -> list[str]:
    """
    Return raw text lines from the EXERCISE LOGS section, including the
    data header row. Stops at the next ### sentinel or end of file.

    Returns empty list if the section is not found.
    """
    lines:         list[str] = []
    in_section:    bool      = False
    found_header:  bool      = False

    with open(csv_path, encoding="utf-8", newline="") as fh:
        for line in fh:
            stripped = line.rstrip("\n\r")

            if stripped.startswith(_SECTION_SENTINEL):
                in_section   = True
                found_header = False
                continue

            if in_section:
                # Next ### sentinel ends the section
                if stripped.startswith("###"):
                    break

                # Skip blank lines before the data header
                if not stripped:
                    continue

                # First non-blank line after sentinel is the data header
                if not found_header:
                    if "USERID" in stripped and "logTime" in stripped:
                        lines.append(stripped)
                        found_header = True
                    continue

                lines.append(stripped)

    return lines


# ── set parser ────────────────────────────────────────────────────────────────

def _parse_sets(logs_str: str) -> list[tuple[float, int]]:
    """
    Parse JeFit logs field into (weight_lbs, reps) tuples.

    Format: "44.10x5,44.10x5,88.20x5"
    Handles: integer weights, decimal weights, zero-weight bodyweight sets.
    Skips malformed parts silently (logs field is user-generated).
    """
    sets: list[tuple[float, int]] = []
    if not logs_str:
        return sets

    for part in logs_str.split(","):
        part = part.strip()
        if "x" not in part:
            continue
        weight_str, reps_str = part.split("x", 1)
        try:
            w = float(weight_str.strip())
            r = int(float(reps_str.strip()))   # cast via float to handle "3.0"
            sets.append((w, r))
        except ValueError:
            continue

    return sets


# ── helpers ───────────────────────────────────────────────────────────────────

def _rel(path: Path, root: Path) -> str:
    try:
        return path.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        return path.resolve().as_posix()


def _float_or_none(val: Optional[str]) -> Optional[float]:
    if not val or not val.strip():
        return None
    try:
        return float(val.strip())
    except ValueError:
        return None


def _int_or_none(val: Optional[str]) -> Optional[int]:
    if not val or not val.strip():
        return None
    try:
        return int(val.strip())
    except ValueError:
        return None

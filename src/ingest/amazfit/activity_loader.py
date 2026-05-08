"""
src/ingest/amazfit/activity_loader.py
Amazfit Helio — activity data loader.

Handles three files from the same export:

  ACTIVITY/ACTIVITY_*.csv
      Daily summaries → four flat `event` observations per day:
      activity_steps, activity_distance, activity_run_distance, activity_calories.
      (Flat per-metric, not parent+component — daily aggregates are queried
      by metric_kind, not by session.)

  ACTIVITY_MINUTE/ACTIVITY_MINUTE_*.csv
      Per-minute step counts (sparse — only minutes with movement are recorded)
      → one `stream` observation per row.

  ACTIVITY_STAGE/ACTIVITY_STAGE_*.csv
      Detected activity segments (walk/run bouts) with start, stop, distance,
      calories, steps → one `event` observation per segment.

Quirks:
1. UTF-8 BOM on all three files → encoding='utf-8-sig'
2. All times are LOCAL (no inline timezone) → reconstruct UTC via config.USER_TZ.
   All observations get quality_flags += ["tz_assumed"].
3. ACTIVITY has only a date (YYYY-MM-DD), no time.
   ts_utc = midnight of that date in USER_TZ (i.e. 05:00 UTC in EST).
4. ACTIVITY_STAGE start/stop are HH:MM on the given date.
   Midnight crossing: if stop < start (HH:MM comparison), stop is on the next
   calendar day → ts_end_utc += 1 day and quality_flags += ["midnight_crossing"].
5. Distance in ACTIVITY and ACTIVITY_STAGE is in meters (verified by step count
   cross-check: steps × ~0.65 m/step ≈ distance value).
6. Calories in ACTIVITY are kcal.
7. Source confidence = 0.80 for all activity metrics (wearable step/activity
   tracking; reliable for trends, less so for precise calorie counting).
"""

from __future__ import annotations

import csv
from datetime import datetime, timezone, timedelta
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

_SOURCE = "amazfit"
_CONF   = 0.80


# ── public API ────────────────────────────────────────────────────────────────

def load(
    activity_csv: Path,
    activity_minute_csv: Path,
    activity_stage_csv: Path,
    tz_name: str = USER_TZ,
    rawdata_root: Optional[Path] = None,
) -> tuple[list[Observation], list[Reject]]:
    """
    Load all three Amazfit activity files.

    Parameters
    ----------
    activity_csv        : ACTIVITY_*.csv (daily summaries)
    activity_minute_csv : ACTIVITY_MINUTE_*.csv (per-minute steps)
    activity_stage_csv  : ACTIVITY_STAGE_*.csv (detected activity segments)
    tz_name             : IANA timezone for local-time reconstruction.
    rawdata_root        : Root for relative source_file paths.
    """
    root = rawdata_root or RAWDATA_ROOT

    daily_obs,  daily_rej  = _load_daily(activity_csv, tz_name, root)
    minute_obs, minute_rej = _load_minute(activity_minute_csv, tz_name, root)
    stage_obs,  stage_rej  = _load_stages(activity_stage_csv, tz_name, root)

    return (
        daily_obs + minute_obs + stage_obs,
        daily_rej + minute_rej + stage_rej,
    )


# ── ACTIVITY daily summaries ──────────────────────────────────────────────────

def _load_daily(
    csv_path: Path,
    tz_name: str,
    rawdata_root: Path,
) -> tuple[list[Observation], list[Reject]]:
    """
    One row per day → four metric observations per day.

    Metrics emitted (if value > 0):
      activity_steps           count
      activity_distance        m
      activity_run_distance    m
      activity_calories        kcal
    """
    rel_path = _rel(csv_path, rawdata_root)
    tz       = ZoneInfo(tz_name)
    observations: list[Observation] = []
    rejects:      list[Reject]      = []

    _METRICS = [
        ("steps",       "activity_steps",        "count"),
        ("distance",    "activity_distance",      "m"),
        ("runDistance", "activity_run_distance",  "m"),
        ("calories",    "activity_calories",      "kcal"),
    ]

    with open(csv_path, encoding="utf-8-sig", newline="") as fh:
        reader = csv.DictReader(fh)

        for row in reader:
            date_str = row["date"].strip()

            # ts_utc = midnight of that local date
            try:
                year, month, day = map(int, date_str.split("-"))
                local_midnight   = datetime(year, month, day, 0, 0, tzinfo=tz)
                ts_utc           = local_midnight.astimezone(timezone.utc)
            except (ValueError, OverflowError) as exc:
                rejects.append(Reject(
                    source=_SOURCE, source_file=rel_path,
                    source_row_id=date_str, raw_row=dict(row),
                    reasons=[f"date parse error: {exc}"],
                ))
                continue

            for csv_col, metric_kind, unit in _METRICS:
                raw = row.get(csv_col, "").strip()
                try:
                    val = float(raw)
                except ValueError:
                    continue   # missing column → skip this metric for this day

                source_row_id = f"{date_str}:{metric_kind}"
                obs_id        = make_observation_id(
                    _SOURCE, rel_path, "ACTIVITY", source_row_id, metric_kind
                )

                obs = Observation(
                    observation_id    = obs_id,
                    source            = _SOURCE,
                    source_file       = rel_path,
                    source_section    = "ACTIVITY",
                    source_row_id     = source_row_id,
                    cadence_kind      = "event",
                    metric_kind       = metric_kind,
                    ts_utc            = ts_utc,
                    tz_original       = tz_name,
                    ts_original       = date_str,
                    value_numeric     = val,
                    value_unit        = unit,
                    source_confidence = _CONF,
                    quality_flags     = ["tz_assumed"],
                    payload           = {},
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


# ── ACTIVITY_MINUTE stream ────────────────────────────────────────────────────

def _load_minute(
    csv_path: Path,
    tz_name: str,
    rawdata_root: Path,
) -> tuple[list[Observation], list[Reject]]:
    """
    One row per logged minute → stream of step-count observations.

    Rows are sparse: only minutes with detected movement are present.
    """
    rel_path = _rel(csv_path, rawdata_root)
    tz       = ZoneInfo(tz_name)
    observations: list[Observation] = []
    rejects:      list[Reject]      = []

    with open(csv_path, encoding="utf-8-sig", newline="") as fh:
        reader = csv.DictReader(fh)

        for row in reader:
            date_str      = row["date"].strip()
            time_str      = row["time"].strip()
            source_row_id = f"{date_str}T{time_str}"

            try:
                year, month, day = map(int, date_str.split("-"))
                hour, minute     = map(int, time_str.split(":"))
                ts_utc = datetime(year, month, day, hour, minute, tzinfo=tz).astimezone(
                    timezone.utc
                )
            except (ValueError, OverflowError) as exc:
                rejects.append(Reject(
                    source=_SOURCE, source_file=rel_path,
                    source_row_id=source_row_id, raw_row=dict(row),
                    reasons=[f"timestamp error: {exc}"],
                ))
                continue

            steps_str = row.get("steps", "").strip()
            try:
                steps = float(steps_str)
            except ValueError:
                rejects.append(Reject(
                    source=_SOURCE, source_file=rel_path,
                    source_row_id=source_row_id, raw_row=dict(row),
                    reasons=[f"steps not numeric: {steps_str!r}"],
                ))
                continue

            obs_id = make_observation_id(
                _SOURCE, rel_path, "ACTIVITY_MINUTE", source_row_id, "activity_steps_minute"
            )
            obs = Observation(
                observation_id    = obs_id,
                source            = _SOURCE,
                source_file       = rel_path,
                source_section    = "ACTIVITY_MINUTE",
                source_row_id     = source_row_id,
                cadence_kind      = "stream",
                metric_kind       = "activity_steps_minute",
                ts_utc            = ts_utc,
                tz_original       = tz_name,
                ts_original       = f"{date_str} {time_str}",
                value_numeric     = steps,
                value_unit        = "count",
                source_confidence = _CONF,
                quality_flags     = ["tz_assumed"],
                payload           = {},
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


# ── ACTIVITY_STAGE events ─────────────────────────────────────────────────────

def _load_stages(
    csv_path: Path,
    tz_name: str,
    rawdata_root: Path,
) -> tuple[list[Observation], list[Reject]]:
    """
    One row per activity segment → event observation with start/stop interval.

    value_numeric = steps (most useful for strain proxy query).
    payload = {distance_m, calories_kcal, steps}.
    """
    rel_path = _rel(csv_path, rawdata_root)
    tz       = ZoneInfo(tz_name)
    observations: list[Observation] = []
    rejects:      list[Reject]      = []

    with open(csv_path, encoding="utf-8-sig", newline="") as fh:
        reader = csv.DictReader(fh)

        for lineno, row in enumerate(reader, start=2):
            date_str  = row["date"].strip()
            start_str = row["start"].strip()  # HH:MM local
            stop_str  = row["stop"].strip()   # HH:MM local

            # Use lineno as the row key (no natural unique ID in this file)
            source_row_id = f"{date_str}T{start_str}:{lineno}"

            try:
                year, month, day      = map(int, date_str.split("-"))
                s_hour, s_min         = map(int, start_str.split(":"))
                e_hour, e_min         = map(int, stop_str.split(":"))

                ts_utc = datetime(
                    year, month, day, s_hour, s_min, tzinfo=tz
                ).astimezone(timezone.utc)

                ts_end_local = datetime(year, month, day, e_hour, e_min, tzinfo=tz)

                # Midnight crossing: if stop HH:MM < start HH:MM, stop is next day
                flags: list[str] = ["tz_assumed"]
                if (e_hour, e_min) < (s_hour, s_min):
                    ts_end_local = ts_end_local + timedelta(days=1)
                    flags.append("midnight_crossing")

                ts_end_utc = ts_end_local.astimezone(timezone.utc)

            except (ValueError, OverflowError) as exc:
                rejects.append(Reject(
                    source=_SOURCE, source_file=rel_path,
                    source_row_id=source_row_id, raw_row=dict(row),
                    reasons=[f"timestamp error: {exc}"],
                ))
                continue

            steps_str    = row.get("steps",    "0").strip()
            dist_str     = row.get("distance", "0").strip()
            cal_str      = row.get("calories", "0").strip()

            steps    = _float_or_none(steps_str)
            dist_m   = _float_or_none(dist_str)
            cal_kcal = _float_or_none(cal_str)

            obs_id = make_observation_id(
                _SOURCE, rel_path, "ACTIVITY_STAGE", source_row_id, "activity_stage"
            )
            obs = Observation(
                observation_id    = obs_id,
                source            = _SOURCE,
                source_file       = rel_path,
                source_section    = "ACTIVITY_STAGE",
                source_row_id     = source_row_id,
                cadence_kind      = "event",
                metric_kind       = "activity_stage",
                ts_utc            = ts_utc,
                ts_end_utc        = ts_end_utc,
                tz_original       = tz_name,
                ts_original       = f"{date_str} {start_str}",
                value_numeric     = steps,
                value_unit        = "count" if steps is not None else None,
                source_confidence = _CONF,
                quality_flags     = flags,
                payload           = {
                    "distance_m":   dist_m,
                    "calories_kcal": cal_kcal,
                    "steps":        steps,
                    "stop_original": stop_str,
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


# ── helpers ───────────────────────────────────────────────────────────────────

def _rel(path: Path, root: Path) -> str:
    try:
        return path.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        return path.resolve().as_posix()


def _float_or_none(val: str) -> Optional[float]:
    if not val:
        return None
    try:
        return float(val)
    except ValueError:
        return None

"""
src/ingest/amazfit/hr_loader.py
Amazfit Helio — continuous heart rate loader (HEARTRATE_AUTO).

Reads HEARTRATE_AUTO/HEARTRATE_AUTO_*.csv → one `stream` observation per row.

Quirks:
1. UTF-8 BOM → encoding='utf-8-sig'
2. date+time columns are LOCAL wall-clock time (no inline timezone).
   UTC reconstructed via config.USER_TZ.
   Every row gets quality_flags = ["tz_assumed"].
3. heartRate is an integer; stored as float per value_numeric convention.
4. Source confidence = 0.75 (schema.md: "Amazfit HR continuous, minute-level —
   optical, but continuous; trend signal stronger than point values").

Note on HRV: HEARTRATE_AUTO carries resting/active HR, not HRV.
The HEALTH_DATA and HEARTRATE files in the Amazfit export were empty in
this export version. If HRV data exists, it would require a separate
loader targeting the HRV/Stress tracking export from the Zepp app.
The NLR × HRV score (nlr-hrv-readiness-spec.md) will flag MISSING_HRV
until that data is available.
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

_SOURCE   = "amazfit"
_SECTION  = "HEARTRATE_AUTO"
_CONF     = 0.75   # schema.md §Source confidence ladder


def load(
    heartrate_csv: Path,
    tz_name: str = USER_TZ,
    rawdata_root: Optional[Path] = None,
) -> tuple[list[Observation], list[Reject]]:
    """
    Load HEARTRATE_AUTO_*.csv → stream of heart-rate observations.

    Parameters
    ----------
    heartrate_csv  : Path to the HEARTRATE_AUTO CSV file.
    tz_name        : IANA timezone for local-time reconstruction.
    rawdata_root   : Root for relative source_file paths.
    """
    root     = rawdata_root or RAWDATA_ROOT
    rel_path = _rel(heartrate_csv, root)
    tz       = ZoneInfo(tz_name)

    observations: list[Observation] = []
    rejects:      list[Reject]      = []

    with open(heartrate_csv, encoding="utf-8-sig", newline="") as fh:
        reader = csv.DictReader(fh)

        for row in reader:
            date_str      = row["date"].strip()
            time_str      = row["time"].strip()
            source_row_id = f"{date_str}T{time_str}"

            # ── reconstruct UTC ──
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

            # ── parse HR ──
            hr_str = row.get("heartRate", "").strip()
            try:
                hr = float(hr_str)
            except ValueError:
                rejects.append(Reject(
                    source=_SOURCE, source_file=rel_path,
                    source_row_id=source_row_id, raw_row=dict(row),
                    reasons=[f"heartRate not numeric: {hr_str!r}"],
                ))
                continue

            obs_id = make_observation_id(
                _SOURCE, rel_path, _SECTION, source_row_id, "hr"
            )
            obs = Observation(
                observation_id    = obs_id,
                source            = _SOURCE,
                source_file       = rel_path,
                source_section    = _SECTION,
                source_row_id     = source_row_id,
                cadence_kind      = "stream",
                metric_kind       = "hr",
                ts_utc            = ts_utc,
                tz_original       = tz_name,
                ts_original       = f"{date_str} {time_str}",
                value_numeric     = hr,
                value_unit        = "bpm",
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


def _rel(path: Path, root: Path) -> str:
    try:
        return path.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        return path.resolve().as_posix()

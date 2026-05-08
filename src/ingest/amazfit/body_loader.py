"""
src/ingest/amazfit/body_loader.py
Amazfit Helio — body composition loader (BODY).

Reads BODY/BODY_*.csv → one `event` observation per weighing.

Quirks:
1. UTF-8 BOM → encoding='utf-8-sig'
2. Timestamps have explicit UTC offset (+0000) — parsed directly, no tz assumption.
3. Body composition columns (fatRate, bodyWaterRate, boneMass, metabolism,
   muscleRate, visceralFat) are all literal "null" strings in this export —
   not empty, not None. Stored as None in payload.
4. Height fluctuates across rows (158.0 vs 166.0). User profile shows 166.0 cm.
   Rows with height != 166.0 get quality_flags += ["height_mismatch"].
   The weight itself may still be valid; these rows are kept, not rejected.
5. Four measurements total in this export (sparse, episodic).

Source confidence = 0.70 (actual scale measurement, better than self-reported
but no body composition metrics populated in this export).

Note: the "null" literal string issue is a Zepp export artifact, not missing data.
Do not confuse with empty string (which would indicate no measurement taken).
"""

from __future__ import annotations

import csv
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

_SOURCE       = "amazfit"
_SECTION      = "BODY"
_CONF         = 0.70
_EXPECTED_HEIGHT_CM = 166.0   # from USER_*.csv profile; flag deviations
_TS_FMT       = "%Y-%m-%d %H:%M:%S%z"   # "2026-01-06 01:39:37+0000"

# All of these arrive as the literal string "null" in the export
_BODY_COMP_FIELDS = (
    "fatRate", "bodyWaterRate", "boneMass",
    "metabolism", "muscleRate", "visceralFat",
)


def load(
    body_csv: Path,
    rawdata_root: Optional[Path] = None,
) -> tuple[list[Observation], list[Reject]]:
    """
    Load BODY_*.csv → episodic weight observations.

    Timestamps carry explicit UTC offset so no tz_name parameter is needed.
    """
    root     = rawdata_root or RAWDATA_ROOT
    rel_path = _rel(body_csv, root)

    observations: list[Observation] = []
    rejects:      list[Reject]      = []

    with open(body_csv, encoding="utf-8-sig", newline="") as fh:
        reader = csv.DictReader(fh)

        for row in reader:
            time_str      = row["time"].strip()
            source_row_id = time_str   # timestamp is the natural row key

            # ── parse UTC timestamp ──
            try:
                ts_utc = datetime.strptime(time_str, _TS_FMT).astimezone(timezone.utc)
            except ValueError as exc:
                rejects.append(Reject(
                    source=_SOURCE, source_file=rel_path,
                    source_row_id=source_row_id, raw_row=dict(row),
                    reasons=[f"timestamp parse error: {exc}"],
                ))
                continue

            # ── parse weight ──
            weight_str = row.get("weight", "").strip()
            try:
                weight_kg = float(weight_str)
            except ValueError:
                rejects.append(Reject(
                    source=_SOURCE, source_file=rel_path,
                    source_row_id=source_row_id, raw_row=dict(row),
                    reasons=[f"weight not numeric: {weight_str!r}"],
                ))
                continue

            # ── quality flags ──
            flags: list[str] = []
            height_str = row.get("height", "").strip()
            try:
                height = float(height_str)
                if abs(height - _EXPECTED_HEIGHT_CM) > 0.1:
                    flags.append("height_mismatch")
            except ValueError:
                flags.append("height_missing")

            # ── tz_original from the explicit offset in the timestamp ──
            tz_original = _extract_tz_suffix(time_str) or "+0000"

            # ── payload: body composition (mostly null in this export) ──
            payload: dict = {
                "height_cm": _null_or_float(row.get("height")),
                "bmi":       _null_or_float(row.get("bmi")),
            }
            for field in _BODY_COMP_FIELDS:
                payload[field] = _null_or_float(row.get(field))

            obs_id = make_observation_id(
                _SOURCE, rel_path, _SECTION, source_row_id, "body_weight"
            )
            obs = Observation(
                observation_id    = obs_id,
                source            = _SOURCE,
                source_file       = rel_path,
                source_section    = _SECTION,
                source_row_id     = source_row_id,
                cadence_kind      = "event",
                metric_kind       = "body_weight",
                ts_utc            = ts_utc,
                tz_original       = tz_original,
                ts_original       = time_str,
                value_numeric     = weight_kg,
                value_unit        = "kg",
                source_confidence = _CONF,
                quality_flags     = flags,
                payload           = payload,
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


def _extract_tz_suffix(ts_str: str) -> Optional[str]:
    for sign in ("+", "-"):
        idx = ts_str.rfind(sign)
        if idx != -1 and len(ts_str) - idx == 5:
            return ts_str[idx:]
    return None


def _null_or_float(val: Optional[str]) -> Optional[float]:
    """Convert empty string or literal "null" to None; else parse float."""
    if val is None:
        return None
    v = val.strip()
    if v == "" or v.lower() == "null":
        return None
    try:
        return float(v)
    except ValueError:
        return None

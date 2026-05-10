"""
Universal wide CSV — see spec.md in this directory.
"""

from __future__ import annotations

import csv
import math
import sys
from datetime import date, datetime, time, timezone
from pathlib import Path
from typing import Any, Optional
from zoneinfo import ZoneInfo

from src.ingest.config import RAWDATA_ROOT, USER_TZ
from src.ingest.schema import Observation, Reject, make_observation_id, validate_observation

_SOURCE = "universal_csv"
_REL_NAME = "universal.csv"
_SECTION = "row"

_METRIC_ANALYTE = "blood_panel_analyte"

_CONF: dict[str, float] = {
    "hr": 0.60,
    "hrv": 0.60,
    "rhr": 0.70,
    "sleep_summary": 0.65,
    "activity_steps": 0.75,
    "body_weight": 0.70,
    "workout_session": 0.85,
    "workout_distance": 0.90,
    "workout_moving_time": 0.95,
    "workout_avg_hr": 0.60,
    "workout_avg_pace": 0.85,
    "blood_glucose": 0.90,
}


def _rel(path: Path, root: Path) -> str:
    try:
        return path.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        return path.resolve().as_posix()


def _blank(cell: Optional[str]) -> bool:
    return cell is None or str(cell).strip() == ""


def _norm_header(h: str) -> str:
    return h.strip().lower()


def _parse_float(cell: Optional[str]) -> Optional[float]:
    if _blank(cell):
        return None
    s = str(cell).strip().replace(",", "")
    try:
        return float(s)
    except ValueError:
        return None


def _parse_date_iso(cell: Optional[str]) -> Optional[date]:
    if _blank(cell):
        return None
    s = str(cell).strip()[:10]
    try:
        return date.fromisoformat(s)
    except ValueError:
        return None


def _local_midnight_utc(d: date, tz: ZoneInfo) -> datetime:
    local = datetime.combine(d, time(0, 0), tzinfo=tz)
    return local.astimezone(timezone.utc)


def _local_noon_utc(d: date, tz: ZoneInfo) -> datetime:
    local = datetime.combine(d, time(12, 0), tzinfo=tz)
    return local.astimezone(timezone.utc)


def _parse_instant(cell: Optional[str], tz: ZoneInfo) -> Optional[datetime]:
    """Parse ISO datetime; naive strings use tz."""
    if _blank(cell):
        return None
    s = str(cell).strip()
    try:
        dt = datetime.fromisoformat(s.replace("Z", "+00:00"))
    except ValueError:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=tz)
    return dt.astimezone(timezone.utc)


def load(
    universal_csv: Path,
    rawdata_root: Optional[Path] = None,
    tz_name: str = USER_TZ,
) -> tuple[list[Observation], list[Reject]]:
    root = rawdata_root or RAWDATA_ROOT
    rel_path = _rel(universal_csv, root)
    tz = ZoneInfo(tz_name)

    observations: list[Observation] = []
    rejects: list[Reject] = []

    with open(universal_csv, encoding="utf-8", newline="") as fh:
        reader = csv.DictReader(fh)
        if reader.fieldnames is None:
            return observations, rejects

        def get_cell(row: dict[str, str], canonical: str) -> Optional[str]:
            for hk, hv in row.items():
                if _norm_header(hk) == canonical.lower():
                    return hv
            return None

        for idx, raw_row in enumerate(reader):
            row = {str(k): ("" if v is None else str(v)) for k, v in raw_row.items()}
            source_row_id = f"row_{idx}"

            date_cell = get_cell(row, "date")
            d = _parse_date_iso(date_cell)
            if d is None:
                rejects.append(
                    Reject(
                        source=_SOURCE,
                        source_file=rel_path,
                        source_row_id=source_row_id,
                        raw_row=row,
                        reasons=["missing_date"],
                    )
                )
                continue

            ts_day = _local_midnight_utc(d, tz)
            ts_orig = date_cell.strip() if date_cell else d.isoformat()

            notes = get_cell(row, "notes")
            if notes is not None and not _blank(notes):
                print(f"[{_SOURCE}] notes={notes!r} row={source_row_id}", file=sys.stderr)

            # ── scalars (daily anchor midnight local → UTC) ─────────────────
            for cell_key, metric, unit, conf_key in (
                # Must be ``hrv`` (not ``hr``) so NLR×HRV scorer picks it up — see ``nlr_hrv_readiness.HRV_METRIC_KIND``.
                ("hrv_ms", "hrv", "ms", "hrv"),
                ("rhr_bpm", "rhr", "bpm", "rhr"),
                ("steps", "activity_steps", "count", "activity_steps"),
                ("glucose_mmol", "blood_glucose", "mmol/L", "blood_glucose"),
            ):
                val = _parse_float(get_cell(row, cell_key))
                if val is None:
                    continue
                conf = _CONF[conf_key]
                oid = make_observation_id(_SOURCE, rel_path, _SECTION, f"{source_row_id}:{metric}", metric)
                obs = Observation(
                    observation_id=oid,
                    source=_SOURCE,
                    source_file=rel_path,
                    source_section=_SECTION,
                    source_row_id=f"{source_row_id}:{metric}",
                    cadence_kind="event",
                    metric_kind=metric,
                    ts_utc=ts_day,
                    tz_original=tz_name,
                    ts_original=ts_orig,
                    value_numeric=val,
                    value_unit=unit,
                    source_confidence=conf,
                    quality_flags=["tz_assumed"],
                    payload={"column": cell_key},
                )
                errs = validate_observation(obs)
                if errs:
                    rejects.append(
                        Reject(
                            source=_SOURCE,
                            source_file=rel_path,
                            source_row_id=obs.source_row_id,
                            raw_row=row,
                            reasons=errs,
                        )
                    )
                else:
                    observations.append(obs)

            wt = _parse_float(get_cell(row, "weight_kg"))
            if wt is not None:
                oid = make_observation_id(
                    _SOURCE, rel_path, _SECTION, f"{source_row_id}:body_weight", "body_weight"
                )
                obs = Observation(
                    observation_id=oid,
                    source=_SOURCE,
                    source_file=rel_path,
                    source_section=_SECTION,
                    source_row_id=f"{source_row_id}:body_weight",
                    cadence_kind="event",
                    metric_kind="body_weight",
                    ts_utc=ts_day,
                    tz_original=tz_name,
                    ts_original=ts_orig,
                    value_numeric=wt,
                    value_unit="kg",
                    source_confidence=_CONF["body_weight"],
                    quality_flags=["tz_assumed"],
                    payload={},
                )
                errs = validate_observation(obs)
                if errs:
                    rejects.append(
                        Reject(
                            source=_SOURCE,
                            source_file=rel_path,
                            source_row_id=obs.source_row_id,
                            raw_row=row,
                            reasons=errs,
                        )
                    )
                else:
                    observations.append(obs)

            # ── sleep_summary ────────────────────────────────────────────────
            onset_raw = get_cell(row, "sleep_onset")
            offset_raw = get_cell(row, "sleep_offset")
            if not _blank(onset_raw) and not _blank(offset_raw):
                ts_start = _parse_instant(onset_raw, tz)
                ts_end = _parse_instant(offset_raw, tz)
                if ts_start is not None and ts_end is not None:
                    sh = _parse_float(get_cell(row, "sleep_hours"))
                    payload: dict[str, Any] = {}
                    if sh is not None and not math.isnan(sh):
                        payload["sleep_hours"] = sh
                    oid = make_observation_id(
                        _SOURCE, rel_path, _SECTION, f"{source_row_id}:sleep_summary", "sleep_summary"
                    )
                    obs = Observation(
                        observation_id=oid,
                        source=_SOURCE,
                        source_file=rel_path,
                        source_section=_SECTION,
                        source_row_id=f"{source_row_id}:sleep_summary",
                        cadence_kind="event",
                        metric_kind="sleep_summary",
                        ts_utc=ts_start,
                        tz_original=tz_name,
                        ts_original=f"{onset_raw}|{offset_raw}",
                        ts_end_utc=ts_end,
                        source_confidence=_CONF["sleep_summary"],
                        quality_flags=["tz_assumed"],
                        payload=payload,
                    )
                    errs = validate_observation(obs)
                    if errs:
                        rejects.append(
                            Reject(
                                source=_SOURCE,
                                source_file=rel_path,
                                source_row_id=obs.source_row_id,
                                raw_row=row,
                                reasons=errs,
                            )
                        )
                    else:
                        observations.append(obs)

            # ── workout_session + components ───────────────────────────────
            w_dist = _parse_float(get_cell(row, "workout_distance_m"))
            w_time = _parse_float(get_cell(row, "workout_moving_time_s"))
            w_hr = _parse_float(get_cell(row, "workout_avg_hr"))
            w_pace = _parse_float(get_cell(row, "workout_avg_pace_s_per_km"))
            w_type = get_cell(row, "workout_type")
            w_type_s = w_type.strip() if w_type else ""

            has_workout_nums = any(x is not None for x in (w_dist, w_time, w_hr, w_pace))
            if w_type_s or has_workout_nums:
                ts_work = _local_noon_utc(d, tz)
                parent_sid = f"{source_row_id}:workout"
                pid = make_observation_id(_SOURCE, rel_path, _SECTION, parent_sid, "workout_session")
                parent = Observation(
                    observation_id=pid,
                    source=_SOURCE,
                    source_file=rel_path,
                    source_section=_SECTION,
                    source_row_id=parent_sid,
                    cadence_kind="event",
                    metric_kind="workout_session",
                    ts_utc=ts_work,
                    tz_original=tz_name,
                    ts_original=ts_orig,
                    value_text=w_type_s or None,
                    source_confidence=_CONF["workout_session"],
                    quality_flags=["tz_assumed"],
                    payload={},
                )
                errs = validate_observation(parent)
                parent_ok = not errs
                if errs:
                    rejects.append(
                        Reject(
                            source=_SOURCE,
                            source_file=rel_path,
                            source_row_id=parent_sid,
                            raw_row=row,
                            reasons=errs,
                        )
                    )
                else:
                    observations.append(parent)

                specs: list[tuple[str, str, str, float]] = []
                if w_dist is not None:
                    specs.append(("workout_distance_m", "workout_distance", "m", _CONF["workout_distance"]))
                if w_time is not None:
                    specs.append(
                        ("workout_moving_time_s", "workout_moving_time", "s", _CONF["workout_moving_time"])
                    )
                if w_hr is not None:
                    specs.append(("workout_avg_hr", "workout_avg_hr", "bpm", _CONF["workout_avg_hr"]))
                if w_pace is not None:
                    specs.append(
                        ("workout_avg_pace_s_per_km", "workout_avg_pace", "s_per_km", _CONF["workout_avg_pace"])
                    )

                if not parent_ok:
                    specs.clear()

                for csv_key, mkind, unit, conf in specs:
                    sid = f"{parent_sid}:{mkind}"
                    oid = make_observation_id(_SOURCE, rel_path, _SECTION, sid, mkind)
                    val = {
                        "workout_distance_m": w_dist,
                        "workout_moving_time_s": w_time,
                        "workout_avg_hr": w_hr,
                        "workout_avg_pace_s_per_km": w_pace,
                    }[csv_key]
                    comp = Observation(
                        observation_id=oid,
                        parent_event_id=pid,
                        source=_SOURCE,
                        source_file=rel_path,
                        source_section=_SECTION,
                        source_row_id=sid,
                        cadence_kind="event",
                        metric_kind=mkind,
                        ts_utc=ts_work,
                        tz_original=tz_name,
                        ts_original=ts_orig,
                        value_numeric=val,
                        value_unit=unit,
                        source_confidence=conf,
                        quality_flags=["tz_assumed"],
                        payload={},
                    )
                    errs = validate_observation(comp)
                    if errs:
                        rejects.append(
                            Reject(
                                source=_SOURCE,
                                source_file=rel_path,
                                source_row_id=sid,
                                raw_row=row,
                                reasons=errs,
                            )
                        )
                    else:
                        observations.append(comp)

            # ── blood panel (three absolutes required) ───────────────────────
            n_abs = _parse_float(get_cell(row, "neutrophils_abs"))
            l_abs = _parse_float(get_cell(row, "lymphocytes_abs"))
            m_abs = _parse_float(get_cell(row, "monocytes_abs"))
            if n_abs is not None and l_abs is not None and m_abs is not None:
                draw_sid = f"{source_row_id}:blood_panel"
                parent_draw_id = make_observation_id(
                    _SOURCE, rel_path, _SECTION, draw_sid, "blood_panel_draw"
                )
                parent_draw = Observation(
                    observation_id=parent_draw_id,
                    source=_SOURCE,
                    source_file=rel_path,
                    source_section="cbc",
                    source_row_id=draw_sid,
                    cadence_kind="event",
                    metric_kind="blood_panel_draw",
                    ts_utc=ts_day,
                    tz_original=tz_name,
                    ts_original=ts_orig,
                    source_confidence=1.0,
                    quality_flags=["from_universal_csv"],
                    payload={
                        "draw_date": d.isoformat(),
                        "episode": "universal_csv_row",
                    },
                )
                errs = validate_observation(parent_draw)
                if errs:
                    rejects.append(
                        Reject(
                            source=_SOURCE,
                            source_file=rel_path,
                            source_row_id=draw_sid,
                            raw_row=row,
                            reasons=errs,
                        )
                    )
                else:
                    observations.append(parent_draw)

                for slug, val in (
                    ("neutrophils_abs", n_abs),
                    ("lymphocytes_abs", l_abs),
                    ("monocytes_abs", m_abs),
                ):
                    sid = f"{draw_sid}:{slug}"
                    oid = make_observation_id(_SOURCE, rel_path, "cbc", sid, _METRIC_ANALYTE)
                    analyte = Observation(
                        observation_id=oid,
                        parent_event_id=parent_draw_id,
                        source=_SOURCE,
                        source_file=rel_path,
                        source_section="cbc",
                        source_row_id=sid,
                        cadence_kind="event",
                        metric_kind=_METRIC_ANALYTE,
                        ts_utc=ts_day,
                        tz_original=tz_name,
                        ts_original=ts_orig,
                        value_numeric=val,
                        value_unit="10^9/L",
                        source_confidence=1.0,
                        quality_flags=[],
                        payload={
                            "analyte_slug": slug,
                            "marker_display_name": slug.replace("_", " ").title(),
                        },
                    )
                    errs = validate_observation(analyte)
                    if errs:
                        rejects.append(
                            Reject(
                                source=_SOURCE,
                                source_file=rel_path,
                                source_row_id=sid,
                                raw_row=row,
                                reasons=errs,
                            )
                        )
                    else:
                        observations.append(analyte)

    return observations, rejects

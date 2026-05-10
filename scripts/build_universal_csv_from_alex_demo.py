#!/usr/bin/env python3
"""
Build ``rawdata/universal.csv`` from committed **Amazfit Helio** exports under
``data/examples/alex_demo/amazfit helio/``.

Aggregates whole-calendar coverage present in those files (typically Mar–Apr)
into one wide universal CSV:

- **SLEEP** — ``sleep_onset`` / ``sleep_offset`` (ISO from export), ``sleep_hours``
  from span (or stage-sum fallback when span is invalid).
- **ACTIVITY** — daily ``steps`` (authoritative totals vs summing minute buckets).
- **HEARTRATE_AUTO** — morning-window minimum HR as ``rhr_bpm`` proxy (04:00–09:59 local).
- **SLEEP_MINUTE** — nightly mean sleep HR → ``hrv_ms`` via ``3000 / mean`` (same idea as
  ``amazfit.sleep_loader.load_hrv_proxy``).
- **ACTIVITY_STAGE** — longest walking/running segment per day → workout distance/time
  (+ derived pace when possible).

Adds **one CBC row** on **2026-03-28** from ``blood_panels/synthetic_panel.md`` (fixture).

Run from repo root::

    PYTHONPATH=. python scripts/build_universal_csv_from_alex_demo.py
"""

from __future__ import annotations

import csv
import statistics
from collections import defaultdict
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

ROOT = Path(__file__).resolve().parents[1]
HELIO = ROOT / "data/examples/alex_demo/amazfit helio"
OUT_CSV = ROOT / "rawdata/universal.csv"

FIELDNAMES = [
    "date",
    "hrv_ms",
    "rhr_bpm",
    "sleep_onset",
    "sleep_offset",
    "sleep_hours",
    "steps",
    "weight_kg",
    "workout_type",
    "workout_distance_m",
    "workout_moving_time_s",
    "workout_avg_hr",
    "workout_avg_pace_s_per_km",
    "neutrophils_abs",
    "lymphocytes_abs",
    "monocytes_abs",
    "glucose_mmol",
    "notes",
]

# Morning window for RHR proxy from minute HR export (local clock on each row’s date).
RHR_START_MIN = 4 * 60
RHR_END_MIN = 10 * 60 - 1

MIN_SLEEP_MINUTE_SAMPLES = 30


def _glob_one(pattern: str) -> Path:
    matches = sorted(HELIO.glob(pattern))
    if not matches:
        raise FileNotFoundError(f"No file matching {HELIO}/{pattern}")
    return matches[0]


def _hm_to_minutes(hm: str) -> int:
    p = hm.strip().split(":")
    return int(p[0]) * 60 + int(p[1])


def _stage_duration_seconds(start_hm: str, stop_hm: str) -> int:
    sm = _hm_to_minutes(start_hm)
    em = _hm_to_minutes(stop_hm)
    if em < sm:
        em += 24 * 60
    return (em - sm) * 60


def _parse_sleep_iso(s: str) -> Optional[datetime]:
    s = (s or "").strip()
    if not s:
        return None
    try:
        return datetime.fromisoformat(s.replace("Z", "+00:00"))
    except ValueError:
        return None


def load_sleep() -> dict[str, dict[str, object]]:
    """date -> onset, offset (ISO strings UTC), sleep_hours."""
    path = _glob_one("SLEEP/SLEEP_*.csv")
    out: dict[str, dict[str, object]] = {}
    with open(path, encoding="utf-8", newline="") as fh:
        for row in csv.DictReader(fh):
            d = (row.get("date") or "").strip()
            if not d:
                continue
            start = _parse_sleep_iso(row.get("start", ""))
            stop = _parse_sleep_iso(row.get("stop", ""))
            if start is None or stop is None:
                continue
            if stop <= start:
                continue
            hours = (stop - start).total_seconds() / 3600.0
            # Stage-sum fallback when export looks broken or zero span
            try:
                deep = float(row.get("deepSleepTime") or 0)
                shallow = float(row.get("shallowSleepTime") or 0)
                rem = float(row.get("REMTime") or 0)
                wake_m = float(row.get("wakeTime") or 0)
                stage_min = deep + shallow + rem + wake_m
                if hours < 0.5 and stage_min > 30:
                    hours = stage_min / 60.0
            except (TypeError, ValueError):
                pass
            out[d] = {
                "sleep_onset": start.isoformat(),
                "sleep_offset": stop.isoformat(),
                "sleep_hours": round(hours, 2),
            }
    return out


def load_activity_steps() -> dict[str, int]:
    path = _glob_one("ACTIVITY/ACTIVITY_*.csv")
    out: dict[str, int] = {}
    with open(path, encoding="utf-8", newline="") as fh:
        for row in csv.DictReader(fh):
            d = (row.get("date") or "").strip()
            if not d:
                continue
            try:
                out[d] = int(float(row.get("steps") or 0))
            except (TypeError, ValueError):
                continue
    return out


def load_rhr_proxy() -> dict[str, int]:
    """Minimum HR during 04:00–09:59 on each local date."""
    path = _glob_one("HEARTRATE_AUTO/HEARTRATE_AUTO_*.csv")
    buckets: dict[str, list[int]] = defaultdict(list)
    with open(path, encoding="utf-8", newline="") as fh:
        for row in csv.DictReader(fh):
            d = (row.get("date") or "").strip()
            tm = (row.get("time") or "").strip()
            if not d or not tm:
                continue
            try:
                hr = int(float(row.get("heartRate") or 0))
            except (TypeError, ValueError):
                continue
            if hr <= 0 or hr > 220:
                continue
            try:
                m = _hm_to_minutes(tm)
            except (IndexError, ValueError):
                continue
            if RHR_START_MIN <= m <= RHR_END_MIN:
                buckets[d].append(hr)
    return {d: min(v) for d, v in buckets.items() if v}


def load_hrv_proxy_from_sleep_minute() -> dict[str, float]:
    """Mean sleep HR per night -> 3000/mean (ms proxy)."""
    path = _glob_one("SLEEP_MINUTE/SLEEP_MINUTE_*.csv")
    hrs: dict[str, list[float]] = defaultdict(list)
    with open(path, encoding="utf-8", newline="") as fh:
        for row in csv.DictReader(fh):
            d = (row.get("date") or "").strip()
            raw = (row.get("hr") or "").strip()
            if not d or not raw:
                continue
            try:
                hr = float(raw)
            except ValueError:
                continue
            if hr <= 0 or hr > 220:
                continue
            hrs[d].append(hr)
    out: dict[str, float] = {}
    for d, series in hrs.items():
        if len(series) < MIN_SLEEP_MINUTE_SAMPLES:
            continue
        mean_hr = statistics.mean(series)
        out[d] = round(3000.0 / mean_hr, 2)
    return out


def load_primary_workout_per_day() -> dict[str, dict[str, float]]:
    """Longest ACTIVITY_STAGE segment per calendar date (distance ~ meters)."""
    path = _glob_one("ACTIVITY_STAGE/ACTIVITY_STAGE_*.csv")
    best: dict[str, tuple[float, dict[str, float]]] = {}
    with open(path, encoding="utf-8", newline="") as fh:
        for row in csv.DictReader(fh):
            d = (row.get("date") or "").strip()
            st = (row.get("start") or "").strip()
            ed = (row.get("stop") or "").strip()
            if not d or not st or not ed:
                continue
            try:
                dur_s = float(_stage_duration_seconds(st, ed))
                dist_m = float(row.get("distance") or 0)
            except (TypeError, ValueError):
                continue
            if dur_s <= 0:
                continue
            payload = {"moving_s": dur_s, "dist_m": dist_m}
            prev = best.get(d)
            if prev is None or dur_s > prev[0]:
                best[d] = (dur_s, payload)
    out: dict[str, dict[str, float]] = {}
    for d, (_, payload) in best.items():
        dist = payload["dist_m"]
        sec = payload["moving_s"]
        pace_str = ""
        if dist > 10:
            km = dist / 1000.0
            pace_str = str(round(sec / km, 1))
        wtype = "run" if dist >= 1000 else "walk"
        out[d] = {
            "workout_type": wtype,
            "workout_distance_m": dist,
            "workout_moving_time_s": sec,
            "workout_avg_pace_s_per_km": pace_str,
        }
    return out


def main() -> None:
    OUT_CSV.parent.mkdir(parents=True, exist_ok=True)

    sleep = load_sleep()
    steps = load_activity_steps()
    rhr = load_rhr_proxy()
    hrv = load_hrv_proxy_from_sleep_minute()
    workouts = load_primary_workout_per_day()

    dates = sorted(
        set(sleep) | set(steps) | set(rhr) | set(hrv) | set(workouts),
        key=lambda s: s,
    )

    rows: list[dict[str, str]] = []
    for d in dates:
        sl = sleep.get(d, {})
        wo = workouts.get(d, {})
        pace_s = str(wo.get("workout_avg_pace_s_per_km", "") or "")

        hrv_s = ""
        if d in hrv:
            hrv_s = str(hrv[d])

        rhr_s = ""
        if d in rhr:
            rhr_s = str(rhr[d])

        wdist = wo.get("workout_distance_m")
        wtime = wo.get("workout_moving_time_s")
        row = {
            "date": d,
            "hrv_ms": hrv_s,
            "rhr_bpm": rhr_s,
            "sleep_onset": str(sl.get("sleep_onset", "")),
            "sleep_offset": str(sl.get("sleep_offset", "")),
            "sleep_hours": str(sl.get("sleep_hours", "")),
            "steps": str(steps.get(d, "")) if d in steps else "",
            "weight_kg": "",
            "workout_type": str(wo.get("workout_type", "")),
            "workout_distance_m": str(int(round(wdist))) if wdist is not None else "",
            "workout_moving_time_s": str(int(round(wtime))) if wtime is not None else "",
            "workout_avg_hr": "",
            "workout_avg_pace_s_per_km": pace_s,
            "neutrophils_abs": "",
            "lymphocytes_abs": "",
            "monocytes_abs": "",
            "glucose_mmol": "",
            "notes": "aggregated from amazfit helio export (alex_demo)",
        }
        # Drop empty strings for optional fields to keep CSV tidy — actually keep for stable columns
        rows.append(row)

    # Synthetic CBC — merge onto lab draw date if present, else append.
    lab = {
        "neutrophils_abs": "10.2",
        "lymphocytes_abs": "1.9",
        "monocytes_abs": "1.2",
        "notes": "CBC alex_demo synthetic_panel.md draw 2026-03-28 (x10^9/L absolutes)",
    }
    merged = False
    for r in rows:
        if r["date"] == "2026-03-28":
            r["neutrophils_abs"] = lab["neutrophils_abs"]
            r["lymphocytes_abs"] = lab["lymphocytes_abs"]
            r["monocytes_abs"] = lab["monocytes_abs"]
            r["notes"] = r["notes"] + " | " + lab["notes"]
            merged = True
            break
    if not merged:
        rows.append(
            {
                "date": "2026-03-28",
                "hrv_ms": "",
                "rhr_bpm": "",
                "sleep_onset": "",
                "sleep_offset": "",
                "sleep_hours": "",
                "steps": "",
                "weight_kg": "",
                "workout_type": "",
                "workout_distance_m": "",
                "workout_moving_time_s": "",
                "workout_avg_hr": "",
                "workout_avg_pace_s_per_km": "",
                "neutrophils_abs": lab["neutrophils_abs"],
                "lymphocytes_abs": lab["lymphocytes_abs"],
                "monocytes_abs": lab["monocytes_abs"],
                "glucose_mmol": "",
                "notes": lab["notes"],
            }
        )
        rows.sort(key=lambda x: x["date"])

    with open(OUT_CSV, "w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=FIELDNAMES)
        w.writeheader()
        w.writerows(rows)

    print(f"Wrote {OUT_CSV} ({len(rows)} rows) from {HELIO}")


if __name__ == "__main__":
    main()

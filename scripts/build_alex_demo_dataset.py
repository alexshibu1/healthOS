#!/usr/bin/env python3
"""
Slice local ``rawdata/`` exports into ``data/examples/alex_demo/`` (public demo).

Preserves directory layout expected by ``src.ingest.load_all``. Keeps the most
recent ``--days`` calendar days ending at ``--end-date`` from each CSV source.

Run from repo root::

    python scripts/build_alex_demo_dataset.py --end-date 2026-04-30 --days 60

Requires a populated ``rawdata/`` tree on the developer machine (gitignored).
"""

from __future__ import annotations

import argparse
import csv
import shutil
from datetime import date, datetime, timedelta
from pathlib import Path


def _filter_csv_by_sleep_date(
    src: Path,
    dst: Path,
    start: date,
    end: date,
    *,
    date_column: str = "date",
) -> None:
    dst.parent.mkdir(parents=True, exist_ok=True)
    with src.open(encoding="utf-8-sig", newline="") as fin:
        reader = csv.DictReader(fin)
        raw_fn = list(reader.fieldnames or [])
        if not raw_fn:
            raise ValueError(f"No header in {src}")
        fieldnames = [k.lstrip("\ufeff").strip() for k in raw_fn]
        if date_column not in fieldnames:
            raise ValueError(f"{date_column} not in {src.name} columns {fieldnames}")
        rows_out: list[dict[str, str]] = []
        for row in reader:
            norm = {fieldnames[i]: row.get(raw_fn[i], "") for i in range(len(raw_fn))}
            raw = (norm.get(date_column) or "").strip()
            try:
                d = date.fromisoformat(raw[:10])
            except ValueError:
                continue
            if start <= d <= end:
                rows_out.append(norm)

    with dst.open("w", encoding="utf-8", newline="") as fout:
        w = csv.DictWriter(fout, fieldnames=fieldnames)
        w.writeheader()
        w.writerows(rows_out)


def _filter_strava(src: Path, dst: Path, start: date, end: date) -> None:
    """Strava uses Activity Date column like ``Apr 30, 2026, 12:00:00 AM``."""
    dst.parent.mkdir(parents=True, exist_ok=True)
    with src.open(encoding="utf-8", errors="replace", newline="") as fin:
        reader = csv.DictReader(fin)
        fieldnames = reader.fieldnames
        if not fieldnames:
            raise ValueError("No Strava header")
        rows_out = []
        for row in reader:
            ds = (row.get("Activity Date") or "").strip()
            if not ds:
                continue
            try:
                # Strava export format: "Apr 30, 2026, 12:00:00 AM"
                dt = datetime.strptime(ds[:17].strip(), "%b %d, %Y")
                d = dt.date()
            except ValueError:
                continue
            if start <= d <= end:
                rows_out.append(row)

    with dst.open("w", encoding="utf-8", newline="") as fout:
        w = csv.DictWriter(fout, fieldnames=fieldnames)
        w.writeheader()
        w.writerows(rows_out)


def main() -> None:
    repo = Path(__file__).resolve().parents[1]
    ap = argparse.ArgumentParser(description="Build alex_demo dataset from rawdata/.")
    ap.add_argument(
        "--rawdata",
        type=Path,
        default=repo / "rawdata",
        help="Source rawdata root (default: ./rawdata).",
    )
    ap.add_argument(
        "--out",
        type=Path,
        default=repo / "data" / "examples" / "alex_demo",
        help="Destination demo root.",
    )
    ap.add_argument("--end-date", required=True, help="Inclusive end YYYY-MM-DD.")
    ap.add_argument("--days", type=int, default=60, help="Calendar-day window length.")
    args = ap.parse_args()

    raw: Path = args.rawdata.resolve()
    out: Path = args.out.resolve()
    end = date.fromisoformat(args.end_date)
    start = end - timedelta(days=args.days - 1)

    amazfit = raw / "amazfit helio"
    if not amazfit.is_dir():
        raise SystemExit(f"Missing {amazfit} — export Amazfit CSVs first.")

    # Amazfit: filter CSVs that use `date` column (sleep, body, activity*, hr uses ts — copy subset by sleep dates)
    for sub, pattern, dcol in [
        ("SLEEP", "SLEEP_*.csv", "date"),
        ("BODY", "BODY_*.csv", "time"),
        ("ACTIVITY", "ACTIVITY_*.csv", "date"),
        ("ACTIVITY_MINUTE", "ACTIVITY_MINUTE_*.csv", "date"),
        ("ACTIVITY_STAGE", "ACTIVITY_STAGE_*.csv", "date"),
    ]:
        matches = list((amazfit / sub).glob(pattern))
        if len(matches) != 1:
            raise SystemExit(f"Expected exactly one {pattern} in {amazfit/sub}, got {matches}")
        src_f = matches[0]
        dst_f = out / "amazfit helio" / sub / src_f.name
        _filter_csv_by_sleep_date(src_f, dst_f, start, end, date_column=dcol)

    # HEARTRATE_AUTO — minute CSV may use different date column; filter by first column date if present
    hr_dir = amazfit / "HEARTRATE_AUTO"
    hr_matches = list(hr_dir.glob("HEARTRATE_AUTO_*.csv"))
    if len(hr_matches) != 1:
        raise SystemExit(f"Expected one HEARTRATE_AUTO CSV in {hr_dir}")
    hr_src = hr_matches[0]
    with hr_src.open(encoding="utf-8-sig", errors="replace", newline="") as fin:
        hr_reader = csv.DictReader(fin)
        fn = hr_reader.fieldnames or []
        # Zepp HEARTRATE_AUTO exports vary; try common keys
        date_key = None
        for cand in ("date", "Date", "timestamp", "TIME"):
            if cand in fn:
                date_key = cand
                break
        if date_key is None and fn:
            date_key = fn[0]
        rows_hr = []
        for row in hr_reader:
            raw_d = (row.get(date_key, "") if date_key else "") or ""
            raw_d = str(raw_d).strip()
            parsed = None
            for fmt in ("%Y-%m-%d", "%Y/%m/%d"):
                try:
                    parsed = datetime.strptime(raw_d[:10], fmt).date()
                    break
                except ValueError:
                    continue
            if parsed is None:
                continue
            if start <= parsed <= end:
                rows_hr.append(row)

    hr_dst = out / "amazfit helio" / "HEARTRATE_AUTO" / hr_src.name
    hr_dst.parent.mkdir(parents=True, exist_ok=True)
    with hr_dst.open("w", encoding="utf-8", newline="") as fout:
        w = csv.DictWriter(fout, fieldnames=fn)
        w.writeheader()
        w.writerows(rows_hr)

    # SLEEP_MINUTE — large file; filter rows whose local date falls in range (best-effort via UTC date)
    sm_matches = list((amazfit / "SLEEP_MINUTE").glob("SLEEP_MINUTE_*.csv"))
    if len(sm_matches) != 1:
        raise SystemExit("Expected one SLEEP_MINUTE CSV")
    sm_src = sm_matches[0]
    with sm_src.open(encoding="utf-8-sig", errors="replace", newline="") as fin:
        sm_reader = csv.DictReader(fin)
        sm_fn = sm_reader.fieldnames or []
        sm_rows = []
        time_key = "timestamp" if "timestamp" in sm_fn else sm_fn[0] if sm_fn else None
        for row in sm_reader:
            ts = str(row.get(time_key, "")).strip() if time_key else ""
            parsed = None
            if len(ts) >= 10:
                try:
                    parsed = date.fromisoformat(ts[:10])
                except ValueError:
                    parsed = None
            if parsed is None:
                continue
            if start <= parsed <= end:
                sm_rows.append(row)

    sm_dst = out / "amazfit helio" / "SLEEP_MINUTE" / sm_src.name
    sm_dst.parent.mkdir(parents=True, exist_ok=True)
    with sm_dst.open("w", encoding="utf-8", newline="") as fout:
        w = csv.DictWriter(fout, fieldnames=sm_fn)
        w.writeheader()
        w.writerows(sm_rows)

    # Strava — keep full export if the 60d window is empty in this machine’s export
    # (pacing for decoupling still needs *some* runs; file stays small).
    strava_src = raw / "strava" / "activities.csv"
    if strava_src.is_file():
        (out / "strava").mkdir(parents=True, exist_ok=True)
        dst_s = out / "strava" / "activities.csv"
        _filter_strava(strava_src, dst_s, start, end)
        lines = dst_s.read_text(encoding="utf-8", errors="replace").count("\n")
        if lines <= 2:
            shutil.copy2(strava_src, dst_s)

    # JeFit — root-level bigApple*.csv
    jefits = list(raw.glob("bigApple*.csv"))
    if len(jefits) != 1:
        raise SystemExit(f"Expected exactly one bigApple*.csv in {raw}, got {jefits}")
    # Multi-section JeFit backup — the loader slices ### EXERCISE LOGS ### internally.
    # Copy whole file to preserve format; size stays modest vs Amazfit minute files.
    shutil.copy2(jefits[0], out / jefits[0].name)

    print(f"Wrote demo slice {start} → {end} to {out}")


if __name__ == "__main__":
    main()

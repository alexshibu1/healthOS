"""
src/ingest/load_all.py
Master loader — pulls every source and returns a unified DataFrame + episodic list.

Usage
-----
    from src.ingest.load_all import load_all
    df, episodic = load_all(since="2024-08-01")

CLI
---
    python -m src.ingest.load_all --since 2024-08-01

Output
------
df        : pd.DataFrame, one row per Observation that passes the --since filter.
            All stream + event observations except episodic sources.
            Columns match Observation dataclass fields (see src/ingest/schema.py).
            ts_utc is UTC-aware datetime.

episodic  : list[Observation] — CBC draws, body weight, anything not time-series.
            NOT filtered by --since (scorer needs last-known anchor regardless
            of date range).

Failures
--------
Loader exceptions propagate immediately (no silent swallowing).
Reject rows are collected into df["_rejected"] = True slices — NOT in the main
df. They are printed to stderr at the end so you know what was dropped.
"""

from __future__ import annotations

import argparse
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import pandas as pd

from src.ingest.config import RAWDATA_ROOT
from src.ingest.schema import Observation

# ── source loaders ────────────────────────────────────────────────────────────
from src.ingest.amazfit.sleep_loader    import load as load_sleep
from src.ingest.amazfit.hr_loader       import load as load_hr
from src.ingest.amazfit.body_loader     import load as load_body
from src.ingest.amazfit.activity_loader import load as load_activity
from src.ingest.strava.loader           import load as load_strava
from src.ingest.jefit.workout_loader    import load as load_jefit


# Metric kinds that are treated as episodic (not filtered by --since).
# Scorer needs full history for these to compute anchors / last-known values.
_EPISODIC_METRIC_KINDS = frozenset({
    "body_weight",
    # blood_panel observations will be added here when the blood_panel loader
    # is implemented (see NOTE below).
})


def load_all(
    rawdata_root: Optional[Path] = None,
    since: Optional[str] = None,
) -> tuple[pd.DataFrame, list[Observation]]:
    """
    Load every source, validate, and return (df, episodic).

    Parameters
    ----------
    rawdata_root : Override for the rawdata directory (default: config.RAWDATA_ROOT).
    since        : ISO date string "YYYY-MM-DD". Time-series observations before
                   this date are excluded from df. Episodic observations are
                   always included regardless of this filter.

    Returns
    -------
    df       : pd.DataFrame of time-series observations (ts_utc >= since).
    episodic : list[Observation] of episodic observations (all dates).
    """
    root = rawdata_root or RAWDATA_ROOT

    since_utc: Optional[datetime] = None
    if since:
        since_utc = datetime.fromisoformat(since).replace(tzinfo=timezone.utc)

    all_obs:     list[Observation] = []
    all_rejects: list[dict]        = []

    # ── Amazfit ───────────────────────────────────────────────────────────────
    amazfit_root = root / "amazfit helio"

    sleep_csv        = _require_one(amazfit_root / "SLEEP",          "SLEEP_*.csv")
    sleep_minute_csv = _require_one(amazfit_root / "SLEEP_MINUTE",   "SLEEP_MINUTE_*.csv")
    hr_csv           = _require_one(amazfit_root / "HEARTRATE_AUTO", "HEARTRATE_AUTO_*.csv")
    body_csv         = _require_one(amazfit_root / "BODY",           "BODY_*.csv")
    activity_csv     = _require_one(amazfit_root / "ACTIVITY",       "ACTIVITY_*.csv")
    activity_min_csv = _require_one(amazfit_root / "ACTIVITY_MINUTE","ACTIVITY_MINUTE_*.csv")
    activity_stg_csv = _require_one(amazfit_root / "ACTIVITY_STAGE", "ACTIVITY_STAGE_*.csv")

    obs, rej = load_sleep(sleep_csv, sleep_minute_csv, rawdata_root=root)
    _collect(all_obs, all_rejects, obs, rej, "amazfit/sleep")

    obs, rej = load_hr(hr_csv, rawdata_root=root)
    _collect(all_obs, all_rejects, obs, rej, "amazfit/hr")

    obs, rej = load_body(body_csv, rawdata_root=root)
    _collect(all_obs, all_rejects, obs, rej, "amazfit/body")

    obs, rej = load_activity(activity_csv, activity_min_csv, activity_stg_csv,
                             rawdata_root=root)
    _collect(all_obs, all_rejects, obs, rej, "amazfit/activity")

    # ── Strava ────────────────────────────────────────────────────────────────
    strava_csv = root / "strava" / "activities.csv"
    obs, rej   = load_strava(strava_csv, rawdata_root=root)
    _collect(all_obs, all_rejects, obs, rej, "strava")

    # ── JeFit ─────────────────────────────────────────────────────────────────
    jefit_csv = _require_one(root, "bigApple*.csv")
    obs, rej  = load_jefit(jefit_csv, rawdata_root=root)
    _collect(all_obs, all_rejects, obs, rej, "jefit")

    # ── NOTE: blood_panel loader not yet implemented ───────────────────────────
    # rawdata/blood_panels/2025_food_poisoning_panel.md is a markdown file, not
    # CSV. It does not fit the DictReader pattern used by the other loaders.
    # A dedicated blood_panel_loader.py with a markdown parser (or a converted
    # CSV export) must be specced and implemented separately.
    # When ready, add here and include metric_kind="blood_panel_draw" /
    # "blood_panel_analyte" in _EPISODIC_METRIC_KINDS.

    # ── split episodic vs time-series ─────────────────────────────────────────
    episodic:    list[Observation] = []
    timeseries:  list[Observation] = []

    for o in all_obs:
        if o.metric_kind in _EPISODIC_METRIC_KINDS:
            episodic.append(o)
        else:
            timeseries.append(o)

    # ── apply --since filter ──────────────────────────────────────────────────
    if since_utc is not None:
        timeseries = [o for o in timeseries if o.ts_utc >= since_utc]

    # ── surface rejects ───────────────────────────────────────────────────────
    if all_rejects:
        print(
            f"\n[load_all] {len(all_rejects)} row(s) rejected across all sources:",
            file=sys.stderr,
        )
        for r in all_rejects:
            print(
                f"  [{r['loader']}] source_row_id={r['source_row_id']!r} "
                f"reasons={r['reasons']}",
                file=sys.stderr,
            )

    # ── build DataFrame ───────────────────────────────────────────────────────
    df = _to_dataframe(timeseries)

    return df, episodic


# ── helpers ───────────────────────────────────────────────────────────────────

def _require_one(directory: Path, pattern: str) -> Path:
    """
    Glob for exactly one file matching pattern in directory.
    Raises FileNotFoundError if zero or more than one match.
    """
    matches = list(directory.glob(pattern))
    if len(matches) == 0:
        raise FileNotFoundError(
            f"No file matching {pattern!r} in {directory}. "
            "Check that the rawdata directory is populated."
        )
    if len(matches) > 1:
        raise FileNotFoundError(
            f"Multiple files matching {pattern!r} in {directory}: "
            f"{[m.name for m in matches]}. Expected exactly one."
        )
    return matches[0]


def _collect(
    all_obs: list[Observation],
    all_rejects: list[dict],
    obs: list[Observation],
    rej,
    loader_name: str,
) -> None:
    """Append observations and rejects; tag each reject with its loader name."""
    all_obs.extend(obs)
    for r in rej:
        all_rejects.append({
            "loader":        loader_name,
            "source_row_id": r.source_row_id,
            "reasons":       r.reasons,
            "source_file":   r.source_file,
        })


def _to_dataframe(observations: list[Observation]) -> pd.DataFrame:
    """Convert list[Observation] to pd.DataFrame."""
    if not observations:
        return pd.DataFrame()

    rows = []
    for o in observations:
        rows.append({
            "observation_id":    o.observation_id,
            "parent_event_id":   o.parent_event_id,
            "source":            o.source,
            "source_file":       o.source_file,
            "source_section":    o.source_section,
            "source_row_id":     o.source_row_id,
            "cadence_kind":      o.cadence_kind,
            "metric_kind":       o.metric_kind,
            "ts_utc":            o.ts_utc,
            "ts_end_utc":        o.ts_end_utc,
            "tz_original":       o.tz_original,
            "ts_original":       o.ts_original,
            "value_numeric":     o.value_numeric,
            "value_unit":        o.value_unit,
            "value_text":        o.value_text,
            "source_confidence": o.source_confidence,
            "quality_flags":     o.quality_flags,
            "payload":           o.payload,
            "ingested_at_utc":   o.ingested_at_utc,
        })

    df = pd.DataFrame(rows)
    # Ensure ts_utc is UTC-aware (it should already be, but belt-and-suspenders)
    if not df.empty and pd.api.types.is_datetime64_any_dtype(df["ts_utc"]):
        if df["ts_utc"].dt.tz is None:
            df["ts_utc"] = df["ts_utc"].dt.tz_localize("UTC")
    return df


# ── CLI ───────────────────────────────────────────────────────────────────────

def _cli() -> None:
    parser = argparse.ArgumentParser(
        description="Load all health data sources into a unified DataFrame."
    )
    parser.add_argument(
        "--since",
        metavar="YYYY-MM-DD",
        default=None,
        help="Only include time-series observations on or after this date "
             "(episodic observations are always included).",
    )
    parser.add_argument(
        "--rawdata-root",
        metavar="PATH",
        default=None,
        help="Override the rawdata root directory (default: config.RAWDATA_ROOT).",
    )
    args = parser.parse_args()

    rawdata_root = Path(args.rawdata_root) if args.rawdata_root else None

    print(f"Loading all sources (since={args.since or 'all'}) …", file=sys.stderr)
    df, episodic = load_all(rawdata_root=rawdata_root, since=args.since)

    print(f"\n── Time-series DataFrame ──────────────────────────")
    print(f"  Rows:    {len(df)}")
    if not df.empty:
        print(f"  Sources: {sorted(df['source'].unique().tolist())}")
        print(f"  Metrics: {sorted(df['metric_kind'].unique().tolist())}")
        ts_min = df["ts_utc"].min()
        ts_max = df["ts_utc"].max()
        print(f"  Range:   {ts_min} → {ts_max}")

    print(f"\n── Episodic Observations ──────────────────────────")
    print(f"  Count:   {len(episodic)}")
    if episodic:
        kinds = sorted({o.metric_kind for o in episodic})
        print(f"  Kinds:   {kinds}")

    print("\nDone.", file=sys.stderr)


if __name__ == "__main__":
    _cli()

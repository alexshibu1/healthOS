"""
Strava steady-cardio pace stability → aerobic decoupling z-score (demo scorer).

Interprets slower-than-baseline easy pace as aerobic inefficiency / drift consistent
with coach-facing Pa:HR narratives. Uses only observed workout_avg_pace rows for
Run sessions (see ``src/ingest/strava/loader.py``).
"""

from __future__ import annotations

import argparse
import math
import os
import sys
from datetime import date, timedelta
from pathlib import Path
from typing import Optional

import pandas as pd

from src.context.flags import get_active_flags
from src.ingest.load_all import load_all
from src.score.paths import scores_dir as _scores_dir_fn


_WINDOW_DAYS = 30
_MIN_SAMPLES = 8


def _scores_dir() -> Path:
    return _scores_dir_fn()


def _run_parent_ids(df: pd.DataFrame) -> set[str]:
    m = (df["metric_kind"] == "workout_session") & (
        df["value_text"].fillna("").str.lower().isin({"run", "trail run", "virtual run"})
    )
    return set(df.loc[m, "observation_id"].astype(str))


def _daily_run_pace_s_per_km(df: pd.DataFrame) -> dict[date, float]:
    parents = _run_parent_ids(df)
    pace = df[
        (df["metric_kind"] == "workout_avg_pace")
        & (df["parent_event_id"].astype(str).isin(parents))
        & df["value_numeric"].notna()
    ].copy()
    if pace.empty:
        return {}
    pace["_d"] = pd.to_datetime(pace["ts_utc"], utc=True).dt.date
    return pace.groupby("_d")["value_numeric"].median().to_dict()


def _rolling_z(history: dict[date, float], scoring_date: date) -> tuple[float, int]:
    """Population stdev of daily median pace in trailing window; z vs historical mean."""
    days = sorted(history.keys())
    if not days:
        return float("nan"), 0
    tail = [d for d in days if scoring_date - timedelta(days=_WINDOW_DAYS - 1) <= d <= scoring_date]
    past = [d for d in days if d < scoring_date - timedelta(days=_WINDOW_DAYS - 1)]
    if len(tail) < 3 or len(past) < _MIN_SAMPLES:
        return float("nan"), len(tail)

    vals_tail = [history[d] for d in tail if d in history]
    vals_past = [history[d] for d in past if d in history]
    if len(vals_tail) < 3:
        return float("nan"), len(vals_tail)

    mu = sum(vals_past) / len(vals_past)
    var = sum((x - mu) ** 2 for x in vals_past) / max(len(vals_past), 1)
    sigma = math.sqrt(var) if var > 0 else 0.0
    today_p = history.get(scoring_date)
    if today_p is None or sigma <= 1e-6:
        return float("nan"), len(vals_tail)

    z = (today_p - mu) / sigma
    return z, len(vals_tail)


def _ui_tier_and_composite(z: float) -> tuple[str, str]:
    """Return (visual tier for snapshot, composite decoupling_band)."""
    if z != z:
        return "unknown", "unknown"
    if z >= 1.0:
        return "fraying", "high"
    if z >= 0.35:
        return "drift", "moderate"
    return "adapted", "good"


def score_day_ado(
    scoring_date: date,
    history: dict[date, float],
) -> dict[str, object]:
    z, n = _rolling_z(history, scoring_date)
    ui_tier, composite_band = _ui_tier_and_composite(z)
    if ui_tier == "unknown":
        return {
            "zscore": float("nan"),
            "tier": "unknown",
            "composite_band": "unknown",
            "confidence": 0.35,
            "reasoning": (
                f"Aerobic decoupling z unavailable — need ≥3 paced runs in-window AND "
                f"{_MIN_SAMPLES} historical paced days (have tail={n})."
            ),
            "window_days": _WINDOW_DAYS,
        }

    return {
        "zscore": round(float(z), 4),
        "tier": ui_tier,
        "composite_band": composite_band,
        "confidence": 0.78,
        "reasoning": (
            f"30d rolling z of Run pace (s/km) vs prior baseline; z={z:+.2f}σ maps to `{ui_tier}` tier."
        ),
        "window_days": _WINDOW_DAYS,
    }


def score_range(
    start_date: date,
    end_date: date,
    df: pd.DataFrame,
    *,
    context_flags_path: Optional[Path] = None,
    output_path: Optional[Path] = None,
) -> pd.DataFrame:
    hist = _daily_run_pace_s_per_km(df)
    rows = []
    cur = start_date
    while cur <= end_date:
        _ = get_active_flags(cur, path=context_flags_path)
        r = score_day_ado(cur, hist)
        rows.append({"date": cur, **r})
        cur += timedelta(days=1)

    out = pd.DataFrame(rows)
    outp = output_path or (_scores_dir() / "aerobic_decoupling.parquet")
    outp.parent.mkdir(parents=True, exist_ok=True)
    out.to_parquet(outp, index=False)
    return out


def _cli_rawdata_root(cli_val: str | None) -> Path | None:
    if cli_val:
        return Path(cli_val)
    env = os.environ.get("RAWDATA_ROOT")
    return Path(env) if env else None


def _cli_context_flags(cli_val: str | None) -> Path | None:
    if cli_val:
        return Path(cli_val)
    for key in ("HEALTHOS_CONTEXT_FLAGS", "CONTEXT_FLAGS"):
        env = os.environ.get(key)
        if env:
            return Path(env)
    return None


def _main() -> None:
    ap = argparse.ArgumentParser(description="Aerobic decoupling parquet writer.")
    ap.add_argument("--since", required=True)
    ap.add_argument("--until", default=None)
    ap.add_argument("--rawdata-root", default=None)
    ap.add_argument("--context-flags", default=None)
    args = ap.parse_args()

    root = _cli_rawdata_root(args.rawdata_root)
    df, _ep = load_all(rawdata_root=root, since=args.since)
    start_d = date.fromisoformat(args.since)
    if args.until:
        end_d = date.fromisoformat(args.until)
    elif not df.empty:
        end_d = pd.Timestamp(df["ts_utc"].max()).date()
    else:
        end_d = start_d

    ctx = _cli_context_flags(args.context_flags)
    score_range(start_d, end_d, df, context_flags_path=ctx)
    print(f"Wrote {_scores_dir() / 'aerobic_decoupling.parquet'}", file=sys.stderr)


if __name__ == "__main__":
    _main()

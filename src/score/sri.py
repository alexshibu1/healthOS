"""
Rolling Sleep Regularity Index (SRI) proxy from ingest sleep summaries.

Uses sleep-onset variance over a 14-day window as a practical stand-in for the
full Phillips epoch matcher when only daily summaries are guaranteed (see
``src/score/specs/sri-spec.md`` secondary proxy). Emits parquet consumed by
``composite.score_range_from_parquets`` and the web snapshot builder.
"""

from __future__ import annotations

import argparse
import os
import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from statistics import pstdev
from typing import Optional
from zoneinfo import ZoneInfo

import pandas as pd

from src.ingest.config import USER_TZ
from src.ingest.load_all import load_all
from src.score.paths import scores_dir as _scores_dir_fn


_WINDOW_DAYS = 14
_MIN_VALID_DAYS = 7


def _scores_dir() -> Path:
    return _scores_dir_fn()


def _onset_minutes_local(ts_utc: datetime, tz_name: str) -> float:
    z = ZoneInfo(tz_name)
    loc = ts_utc.astimezone(z)
    return loc.hour * 60.0 + loc.minute + loc.second / 60.0


def _sleep_onset_by_date(df: pd.DataFrame) -> dict[date, float]:
    """Main sleep onset (minutes from local midnight) per calendar day."""
    sub = df[df["metric_kind"] == "sleep_summary"].copy()
    if sub.empty:
        return {}
    out: dict[date, float] = {}
    for _, row in sub.iterrows():
        ts = row["ts_utc"]
        if pd.isna(ts):
            continue
        if isinstance(ts, pd.Timestamp):
            ts = ts.to_pydatetime()
        if ts.tzinfo is None:
            ts = ts.replace(tzinfo=timezone.utc)
        d = ts.astimezone(ZoneInfo("UTC")).date()
        onset = _onset_minutes_local(ts, USER_TZ)
        # Keep earliest onset per calendar day (main night).
        if d not in out or onset < out[d]:
            out[d] = onset
    return out


def _rolling_onset_std(onsets: dict[date, float], scoring_date: date) -> tuple[float, int]:
    """Std dev of onset minutes over last _WINDOW_DAYS days ending scoring_date; valid day count."""
    values: list[float] = []
    for i in range(_WINDOW_DAYS):
        d = scoring_date - timedelta(days=i)
        if d in onsets:
            values.append(onsets[d])
    if len(values) < _MIN_VALID_DAYS:
        return float("nan"), len(values)
    return pstdev(values), len(values)


def _std_to_sri_proxy(onset_std_min: float) -> float:
    """Map onset SD (minutes) to a 0–100 score (lower variance → higher)."""
    if onset_std_min != onset_std_min:
        return float("nan")
    raw = 100.0 - min(100.0, onset_std_min * 1.35)
    return max(0.0, min(100.0, raw))


def _tier_from_score(sri: float) -> str:
    if sri != sri:
        return "unknown"
    if sri >= 80:
        return "high"
    if sri >= 70:
        return "moderate"
    return "irregular"


def score_day_sri(
    scoring_date: date,
    df: pd.DataFrame,
    *,
    onset_by_date: Optional[dict[date, float]] = None,
) -> dict[str, object]:
    onsets = onset_by_date if onset_by_date is not None else _sleep_onset_by_date(df)
    std_14, n_ok = _rolling_onset_std(onsets, scoring_date)
    sri = _std_to_sri_proxy(std_14)
    tier = _tier_from_score(sri)
    if n_ok < _MIN_VALID_DAYS:
        return {
            "score": float("nan"),
            "tier": "unknown",
            "confidence": 0.35,
            "reasoning": (
                f"SRI proxy skipped — only {n_ok} sleep-summary night(s) in {_WINDOW_DAYS}d window "
                f"(need {_MIN_VALID_DAYS})."
            ),
            "window_days": _WINDOW_DAYS,
        }

    return {
        "score": round(float(sri), 3),
        "tier": tier,
        "confidence": 0.82,
        "reasoning": (
            f"14d onset σ≈{std_14:.1f} min (local); mapped to SRI proxy≈{sri:.1f} "
            f"(secondary proxy per sri-spec §Practical Secondary)."
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
    onsets = _sleep_onset_by_date(df)
    rows = []
    cur = start_date
    while cur <= end_date:
        r = score_day_sri(cur, df, onset_by_date=onsets)
        rows.append({"date": cur, **r})
        cur += timedelta(days=1)

    out = pd.DataFrame(rows)
    outp = output_path or (_scores_dir() / "sri.parquet")
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
    ap = argparse.ArgumentParser(description="SRI proxy parquet writer.")
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
    print(f"Wrote {_scores_dir() / 'sri.parquet'}", file=sys.stderr)


if __name__ == "__main__":
    _main()

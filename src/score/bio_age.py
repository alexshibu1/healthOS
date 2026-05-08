"""
Bio-age proxy scorer (MVP).

Implements `src/score/specs/bio-age-spec.md` exactly:

    bio_age_proxy = chronological_age + Σ(contributor_pull_years)

with three contributors:

1) SRI pull (anchor interpolation)
2) HRV trend pull (linear on z-score, capped ±2y)
3) RHR baseline pull (+5 bpm sustained -> +0.5y)

This module intentionally uses transparent heuristics, not ML.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import List

import pandas as pd


@dataclass(frozen=True)
class ContributorPull:
    name: str
    years_pulled: float
    share_of_total: float
    rationale: str


@dataclass(frozen=True)
class BioAgeBreakdown:
    chronological_age: float
    proxy_age: float
    gap_years: float
    contributors: List[ContributorPull]


def compute_bio_age_breakdown(
    *,
    chronological_age: float,
    sri: float,
    hrv_trend_z: float,
    rhr_drift_bpm: float,
) -> BioAgeBreakdown:
    """
    Compute bio-age proxy breakdown from the three MVP contributors.

    Parameters
    ----------
    chronological_age:
        Chronological age in years.
    sri:
        Sleep Regularity Index (0-100 expected).
    hrv_trend_z:
        30-day HRV trend z-score vs personal 90-day baseline.
    rhr_drift_bpm:
        Sustained 30-day RHR drift (bpm) vs 60-day baseline.
    """
    chrono = float(chronological_age)
    sri_v = float(sri)
    hrv_z = float(hrv_trend_z)
    rhr_drift = float(rhr_drift_bpm)

    sri_pull = _sri_pull_years(sri_v)
    hrv_pull = _hrv_trend_pull_years(hrv_z)
    rhr_pull = _rhr_baseline_pull_years(rhr_drift)

    raw = [
        ("sri", sri_pull, _sri_rationale(sri_v, sri_pull)),
        ("hrv_trend", hrv_pull, _hrv_rationale(hrv_z, hrv_pull)),
        ("rhr_baseline", rhr_pull, _rhr_rationale(rhr_drift, rhr_pull)),
    ]

    total_abs = sum(abs(v) for _, v, _ in raw)
    contributors: List[ContributorPull] = []
    for name, years, rationale in raw:
        share = abs(years) / total_abs if total_abs > 0 else 0.0
        contributors.append(
            ContributorPull(
                name=name,
                years_pulled=years,
                share_of_total=share,
                rationale=rationale,
            )
        )

    total_pull = sum(c.years_pulled for c in contributors)
    proxy = chrono + total_pull
    gap = proxy - chrono
    return BioAgeBreakdown(
        chronological_age=chrono,
        proxy_age=proxy,
        gap_years=gap,
        contributors=contributors,
    )


def _sri_pull_years(sri: float) -> float:
    """
    Anchor map:
      SRI 80 -> 0y
      SRI 70 -> +1y
      SRI 60 -> +2y
      SRI 50 -> +3y
    Piecewise linear interpolation with clamping to [0, +3].
    """
    if sri >= 80:
        return 0.0
    if sri <= 50:
        return 3.0
    # All segments have slope -0.1 y per SRI point:
    # pull = (80 - sri) / 10
    return (80.0 - sri) / 10.0


def _hrv_trend_pull_years(hrv_trend_z: float) -> float:
    """
    +1σ -> -0.5y
    -1σ -> +0.5y
    => raw = -0.5 * z
    capped to ±2y
    """
    raw = -0.5 * hrv_trend_z
    return _clamp(raw, -2.0, 2.0)


def _rhr_baseline_pull_years(rhr_drift_bpm: float) -> float:
    """
    Sustained +5 bpm for 30d -> +0.5y.
    Conservative MVP rule: only positive drift adds age pull.
    """
    positive = max(0.0, rhr_drift_bpm)
    return positive * (0.5 / 5.0)


def _sri_rationale(sri: float, pull: float) -> str:
    return (
        f"SRI={sri:.1f}; anchor interpolation "
        f"(80→0y, 70→+1y, 60→+2y, 50→+3y) gives {pull:+.2f}y."
    )


def _hrv_rationale(hrv_z: float, pull: float) -> str:
    return (
        f"HRV trend z={hrv_z:+.2f}; linear map +1σ→-0.5y, -1σ→+0.5y "
        f"with ±2y cap gives {pull:+.2f}y."
    )


def _rhr_rationale(rhr_drift_bpm: float, pull: float) -> str:
    return (
        f"RHR drift={rhr_drift_bpm:+.2f} bpm; +5 bpm sustained for 30d→+0.5y "
        f"(positive-only MVP rule) gives {pull:+.2f}y."
    )


def _clamp(x: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, x))


def score_timeseries_to_parquet(
    *,
    input_csv: str | Path,
    chronological_age: float,
    output_parquet: str | Path = Path("data/scores/bio_age.parquet"),
) -> pd.DataFrame:
    """
    Score a daily time series and write bio-age outputs to parquet.

    Output schema:
      - date
      - proxy_age
      - gap_years
      - contributors_json

    Notes
    -----
    - HRV trend z-score is computed as:
        z = (rolling_mean_30d - rolling_mean_90d) / rolling_std_90d
      using available history with `min_periods=1`, and z=0 when std=0.
    - RHR drift is computed as:
        rolling_mean_30d - rolling_mean_60d
      using available history with `min_periods=1`.
    """
    in_path = Path(input_csv)
    out_path = Path(output_parquet)

    df = pd.read_csv(in_path)
    required = {"date", "sri_score", "wake_hrv_ms", "wake_rhr_bpm"}
    missing = required - set(df.columns)
    if missing:
        raise ValueError(
            f"input missing required column(s): {', '.join(sorted(missing))}"
        )

    work = df.copy()
    work["date"] = pd.to_datetime(work["date"], errors="raise").dt.date
    work["wake_hrv_ms"] = pd.to_numeric(work["wake_hrv_ms"], errors="raise")
    work["wake_rhr_bpm"] = pd.to_numeric(work["wake_rhr_bpm"], errors="raise")
    work["sri_score"] = pd.to_numeric(work["sri_score"], errors="raise")
    work = work.sort_values("date").reset_index(drop=True)

    hrv_30 = work["wake_hrv_ms"].rolling(window=30, min_periods=1).mean()
    hrv_90 = work["wake_hrv_ms"].rolling(window=90, min_periods=1).mean()
    hrv_90_std = (
        work["wake_hrv_ms"]
        .rolling(window=90, min_periods=2)
        .std(ddof=0)
        .fillna(0.0)
    )
    hrv_trend_z = pd.Series(0.0, index=work.index)
    valid_std = hrv_90_std > 0
    hrv_trend_z.loc[valid_std] = (
        (hrv_30.loc[valid_std] - hrv_90.loc[valid_std]) / hrv_90_std.loc[valid_std]
    )

    rhr_30 = work["wake_rhr_bpm"].rolling(window=30, min_periods=1).mean()
    rhr_60 = work["wake_rhr_bpm"].rolling(window=60, min_periods=1).mean()
    rhr_drift = rhr_30 - rhr_60

    proxies: list[float] = []
    gaps: list[float] = []
    contributors_json: list[str] = []

    for i, row in work.iterrows():
        breakdown = compute_bio_age_breakdown(
            chronological_age=float(chronological_age),
            sri=float(row["sri_score"]),
            hrv_trend_z=float(hrv_trend_z.iloc[i]),
            rhr_drift_bpm=float(rhr_drift.iloc[i]),
        )
        proxies.append(breakdown.proxy_age)
        gaps.append(breakdown.gap_years)
        contributors_json.append(
            json.dumps(
                [
                    {
                        "name": c.name,
                        "years_pulled": c.years_pulled,
                        "share_of_total": c.share_of_total,
                        "rationale": c.rationale,
                    }
                    for c in breakdown.contributors
                ],
                separators=(",", ":"),
            )
        )

    out = pd.DataFrame(
        {
            "date": work["date"],
            "proxy_age": proxies,
            "gap_years": gaps,
            "contributors_json": contributors_json,
        }
    )

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out.to_parquet(out_path, index=False)
    return out


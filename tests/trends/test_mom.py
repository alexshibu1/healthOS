"""Tests for month-over-month trends."""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from src.trends.mom import (
    build_trends_from_daily_csv,
    compute_month_trends,
    observations_daily_means,
    observations_from_daily_csv,
    scores_wide_from_daily_csv,
)


def _write_csv(df: pd.DataFrame, tmp_path: Path) -> Path:
    p = tmp_path / "daily.csv"
    df.to_csv(p, index=False)
    return p


def test_ranked_sorted_by_abs_cohens_d(tmp_path: Path):
    rows = []
    # March — lower HRV / readiness vs April — separated means; enough intra-month
    # variance avoids scipy moment warnings from near-duplicate samples.
    for d in range(1, 21):
        rows.append(
            {
                "date": f"2026-03-{d:02d}",
                "wake_hrv_ms": 38 + d * 0.35 + (d % 4),
                "wake_rhr_bpm": 56 + (d % 3),
                "readiness_score": 52 + (d % 7),
                "sri_score": 68 + (d % 5),
                "strava_cardio_strain": 36 + d * 0.4 + (d % 5),
            }
        )
    for d in range(1, 21):
        rows.append(
            {
                "date": f"2026-04-{d:02d}",
                "wake_hrv_ms": 52 + d * 0.35 + (d % 4),
                "wake_rhr_bpm": 58 + (d % 3),
                "readiness_score": 64 + (d % 7),
                "sri_score": 76 + (d % 5),
                "strava_cardio_strain": 44 + d * 0.4 + (d % 5),
            }
        )
    csv_path = _write_csv(pd.DataFrame(rows), tmp_path)
    payload, _ = build_trends_from_daily_csv(csv_path, month_yyyy_mm="2026-04", out_dir=tmp_path)

    ranked = payload["trends_ranked_by_effect_size"]
    ds = [abs(r["cohens_d"] or 0.0) for r in ranked]
    assert ds == sorted(ds, reverse=True)


def test_hrv_non_normal_series_cohens_d_sign_positive_when_curr_above_prev(tmp_path: Path):
    rows = []
    # Tiny jitter so pooled SD > 0 (constant series yield d=0 by design).
    for d in range(10, 21):
        rows.append({"date": f"2026-03-{d:02d}", "wake_hrv_ms": 40.0 + (d % 4) * 0.25})
    for d in range(1, 16):
        rows.append({"date": f"2026-04-{d:02d}", "wake_hrv_ms": 55.0 + (d % 5) * 0.2})
    csv_path = _write_csv(pd.DataFrame(rows), tmp_path)
    obs = observations_daily_means(observations_from_daily_csv(csv_path))
    scores = scores_wide_from_daily_csv(csv_path)
    out = compute_month_trends(
        obs_daily=obs,
        scores_daily=scores,
        month_yyyy_mm="2026-04",
    )
    hrv_block = out["metrics"]["hrv"]
    assert hrv_block["test"] == "mannwhitney"
    assert hrv_block["mean_curr"] > hrv_block["mean_prev"]
    assert hrv_block["cohens_d"] is not None and hrv_block["cohens_d"] > 2.0

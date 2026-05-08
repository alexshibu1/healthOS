"""Tests for bio-age scorer and parquet writer."""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from src.score.bio_age import compute_bio_age_breakdown, score_timeseries_to_parquet


def _contrib_map(breakdown):
    return {c.name: c for c in breakdown.contributors}


def test_perfect_sri_neutral_hrv_baseline_rhr_gap_zero():
    """
    Perfect SRI 80, neutral HRV trend, baseline RHR drift -> gap = 0.
    """
    b = compute_bio_age_breakdown(
        chronological_age=21,
        sri=80,
        hrv_trend_z=0,
        rhr_drift_bpm=0,
    )
    assert b.gap_years == 0.0
    assert b.proxy_age == 21.0
    for c in b.contributors:
        assert c.years_pulled == 0.0
        assert c.share_of_total == 0.0


def test_sri_60_neutral_baseline_gap_two_sri_sole():
    """
    SRI 60, neutral HRV, baseline RHR -> gap = +2y, SRI sole contributor.
    """
    b = compute_bio_age_breakdown(
        chronological_age=21,
        sri=60,
        hrv_trend_z=0,
        rhr_drift_bpm=0,
    )
    cm = _contrib_map(b)
    assert b.gap_years == 2.0
    assert cm["sri"].years_pulled == 2.0
    assert cm["sri"].share_of_total == 1.0
    assert cm["hrv_trend"].years_pulled == 0.0
    assert cm["hrv_trend"].share_of_total == 0.0
    assert cm["rhr_baseline"].years_pulled == 0.0
    assert cm["rhr_baseline"].share_of_total == 0.0


def test_sri_70_hrv_plus_1sigma_rhr_plus_5_gap_about_one_all_contribute():
    """
    Spec-consistent composite case:
      SRI 70 -> +1.0y
      HRV +1σ -> -0.5y
      RHR +5bpm -> +0.5y
      net gap ~ +1.0y, with all three non-zero contributors.
    """
    b = compute_bio_age_breakdown(
        chronological_age=21,
        sri=70,
        hrv_trend_z=1.0,
        rhr_drift_bpm=5.0,
    )
    cm = _contrib_map(b)
    assert b.gap_years == 1.0
    assert cm["sri"].years_pulled == 1.0
    assert cm["hrv_trend"].years_pulled == -0.5
    assert cm["rhr_baseline"].years_pulled == 0.5
    assert abs(sum(c.share_of_total for c in b.contributors) - 1.0) < 1e-12


def test_real_data_last_week_outputs_parquet_and_shares_sum_to_100ish(tmp_path: Path):
    """
    Use the user's real mock dataset, score to parquet, then validate:
      - output rows include last week
      - a number is produced
      - all three contributors exist
      - share_of_total sums to ~100% (via share*100)
    """
    input_csv = Path("data/examples/systemic_daily_mock.csv")
    out_parquet = tmp_path / "bio_age.parquet"
    out_df = score_timeseries_to_parquet(
        input_csv=input_csv,
        chronological_age=21,
        output_parquet=out_parquet,
    )
    assert out_parquet.exists()
    assert set(out_df.columns) == {
        "date",
        "proxy_age",
        "gap_years",
        "contributors_json",
    }
    assert len(out_df) >= 7

    # Read back parquet to verify IO contract.
    read_df = pd.read_parquet(out_parquet)
    assert len(read_df) == len(out_df)

    last_week = read_df.tail(7)
    assert last_week["proxy_age"].notna().all()
    assert last_week["gap_years"].notna().all()

    for payload in last_week["contributors_json"]:
        contribs = json.loads(payload)
        names = {c["name"] for c in contribs}
        assert names == {"sri", "hrv_trend", "rhr_baseline"}
        pct_sum = sum(float(c["share_of_total"]) for c in contribs) * 100.0
        # floating arithmetic: tolerate small epsilon around 100%
        assert abs(pct_sum - 100.0) < 1e-6 or pct_sum == 0.0


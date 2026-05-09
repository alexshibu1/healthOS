"""
Month-over-month deltas for unified observations + four headline scores.

Spec: src/trends/spec.md
"""

from __future__ import annotations

import json
from collections import defaultdict
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Mapping

import numpy as np
import pandas as pd

from src.trends.significance import (
    TestKind,
    cohens_d_independent,
    is_significant,
    p_value_two_sample,
)

# Non-normal daily streams → Mann–Whitney (spec)
_NONNORMAL_METRIC_KINDS = frozenset({"hrv", "rhr", "resting_hr"})
_NONNORMAL_PREFIXES = ("hrv_",)


def _metric_test_kind(metric_kind: str) -> TestKind:
    if metric_kind in _NONNORMAL_METRIC_KINDS:
        return "mannwhitney"
    if any(metric_kind.startswith(p) for p in _NONNORMAL_PREFIXES):
        return "mannwhitney"
    return "welch_t"


def observations_daily_means(obs_df: pd.DataFrame) -> pd.DataFrame:
    """
    Collapse observations to one row per (calendar date UTC, metric_kind).

    Required columns: ts_utc, metric_kind, value_numeric
    """
    required = {"ts_utc", "metric_kind", "value_numeric"}
    missing = required - set(obs_df.columns)
    if missing:
        raise ValueError(f"obs_df missing columns: {sorted(missing)}")
    df = obs_df.copy()
    df["value_numeric"] = pd.to_numeric(df["value_numeric"], errors="coerce")
    df = df.dropna(subset=["value_numeric"])
    if df.empty:
        return pd.DataFrame(columns=["date", "metric_kind", "value"])

    ts = pd.to_datetime(df["ts_utc"], utc=True, errors="coerce")
    df["date"] = ts.dt.date
    df = df.dropna(subset=["date"])
    g = (
        df.groupby(["date", "metric_kind"], as_index=False)["value_numeric"]
        .mean()
        .rename(columns={"value_numeric": "value"})
    )
    return g


def observations_from_daily_csv(path: str | Path) -> pd.DataFrame:
    """
    Bridge: wide systemic CSV → observation-shaped rows for trending.

    Maps columns to canonical metric_kind names aligned with ingest vocabulary.
    """
    p = Path(path)
    raw = pd.read_csv(p)
    raw["date"] = pd.to_datetime(raw["date"]).dt.date
    rows: list[dict[str, Any]] = []

    def add(metric_kind: str, dt: date, val: float) -> None:
        if val is None or (isinstance(val, float) and not np.isfinite(val)):
            return
        rows.append(
            {
                "ts_utc": datetime(dt.year, dt.month, dt.day, 12, 0, 0, tzinfo=timezone.utc),
                "metric_kind": metric_kind,
                "value_numeric": float(val),
            }
        )

    col_map = {
        "wake_hrv_ms": "hrv",
        "wake_rhr_bpm": "rhr",
        "sleep_duration_h": "sleep_duration_h",
        "jefit_volume_kg": "jefit_volume_kg",
        "strava_cardio_strain": "strava_cardio_strain",
        "subjective_energy_1_10": "subjective_energy_1_10",
        "neutrophils_pct": "neutrophils_pct",
        "lymphocytes_pct": "lymphocytes_pct",
        "nlr": "nlr",
    }
    for _, r in raw.iterrows():
        dt = r["date"]
        for csv_col, mk in col_map.items():
            if csv_col in raw.columns and pd.notna(r.get(csv_col)):
                add(mk, dt, float(r[csv_col]))
    return pd.DataFrame(rows)


def scores_wide_from_daily_csv(path: str | Path) -> pd.DataFrame:
    """
    Extract daily series for the four headline scores from a wide CSV.

    - composite: readiness_score
    - nlr_hrv: nlr_hrv_readiness if column exists else readiness_score (alias)
    - sri: sri_score
    - decoupling: aerobic_decoupling_z if present else rolling z of strava_cardio_strain
    """
    p = Path(path)
    df = pd.read_csv(p)
    df["date"] = pd.to_datetime(df["date"]).dt.date
    out = pd.DataFrame({"date": df["date"]})

    if "readiness_score" in df.columns:
        out["composite"] = pd.to_numeric(df["readiness_score"], errors="coerce")
    else:
        out["composite"] = np.nan

    if "nlr_hrv_readiness" in df.columns:
        out["nlr_hrv"] = pd.to_numeric(df["nlr_hrv_readiness"], errors="coerce")
    else:
        out["nlr_hrv"] = out["composite"]

    if "sri_score" in df.columns:
        out["sri"] = pd.to_numeric(df["sri_score"], errors="coerce")
    else:
        out["sri"] = np.nan

    if "aerobic_decoupling_z" in df.columns:
        out["decoupling"] = pd.to_numeric(df["aerobic_decoupling_z"], errors="coerce")
    elif "strava_cardio_strain" in df.columns:
        strain = pd.to_numeric(df["strava_cardio_strain"], errors="coerce")
        roll = strain.rolling(window=30, min_periods=3).mean()
        std = strain.rolling(window=30, min_periods=3).std(ddof=0)
        out["decoupling"] = (strain - roll) / std.replace(0, np.nan)
    else:
        out["decoupling"] = np.nan

    return out


def _month_dates(year: int, month: int) -> tuple[date, date]:
    """First and last calendar date of month."""
    start = date(year, month, 1)
    if month == 12:
        next_first = date(year + 1, 1, 1)
    else:
        next_first = date(year, month + 1, 1)
    last = next_first - timedelta(days=1)
    return start, last


def _prev_month(year: int, month: int) -> tuple[int, int]:
    if month == 1:
        return year - 1, 12
    return year, month - 1


def _values_for_month(
    daily: pd.DataFrame,
    month_start: date,
    month_end: date,
    key_col: str,
    key_val: str | None = None,
) -> np.ndarray:
    """Daily rows: columns date, key_col or metric_kind, value."""
    if key_col == "metric_kind":
        sub = daily[(daily["date"] >= month_start) & (daily["date"] <= month_end)]
        sub = sub[sub["metric_kind"] == key_val]
    else:
        sub = daily[(daily["date"] >= month_start) & (daily["date"] <= month_end)]
    vals = pd.to_numeric(sub["value"], errors="coerce").dropna().to_numpy(dtype=float)
    return vals


def _mom_block(
    curr: np.ndarray,
    prev: np.ndarray,
    test_kind: TestKind,
) -> dict[str, Any]:
    if curr.size < 2 or prev.size < 2:
        return {
            "n_curr": int(curr.size),
            "n_prev": int(prev.size),
            "mean_curr": float(np.mean(curr)) if curr.size else None,
            "mean_prev": float(np.mean(prev)) if prev.size else None,
            "delta_mean": None,
            "cohens_d": None,
            "p_value": None,
            "significant": False,
            "test": test_kind,
            "reason": "insufficient_days",
        }
    d = cohens_d_independent(curr, prev)
    p = p_value_two_sample(curr, prev, test_kind)
    sig = is_significant(d, p)
    return {
        "n_curr": int(curr.size),
        "n_prev": int(prev.size),
        "mean_curr": float(np.mean(curr)),
        "mean_prev": float(np.mean(prev)),
        "delta_mean": float(np.mean(curr) - np.mean(prev)),
        "cohens_d": float(d) if np.isfinite(d) else None,
        "p_value": float(p) if np.isfinite(p) else None,
        "significant": sig,
        "test": test_kind,
        "reason": None,
    }


def compute_month_trends(
    *,
    obs_daily: pd.DataFrame,
    scores_daily: pd.DataFrame | None = None,
    month_yyyy_mm: str,
) -> dict[str, Any]:
    """
    Build MoM JSON-ready dict for `month_yyyy_mm`.

    Parameters
    ----------
    obs_daily:
        Output of observations_daily_means — columns date, metric_kind, value.
    scores_daily:
        Optional wide frame from scores_wide_from_daily_csv — columns date,
        composite, nlr_hrv, sri, decoupling.
    """
    year, month = map(int, month_yyyy_mm.split("-"))
    py, pm = _prev_month(year, month)
    curr_start, curr_end = _month_dates(year, month)
    prev_start, prev_end = _month_dates(py, pm)

    metrics_out: dict[str, Any] = {}
    ranked: list[dict[str, Any]] = []

    # Unified metrics (excluding score pseudo-keys we inject separately)
    if not obs_daily.empty:
        for mk in sorted(obs_daily["metric_kind"].unique()):
            curr = _values_for_month(obs_daily, curr_start, curr_end, "metric_kind", mk)
            prev = _values_for_month(obs_daily, prev_start, prev_end, "metric_kind", mk)
            tk = _metric_test_kind(str(mk))
            block = _mom_block(curr, prev, tk)
            metrics_out[str(mk)] = block
            if block.get("cohens_d") is not None:
                ranked.append(
                    {
                        "key": str(mk),
                        "kind": "metric",
                        "cohens_d": block["cohens_d"],
                        "significant": block["significant"],
                        "p_value": block["p_value"],
                        "delta_mean": block["delta_mean"],
                    }
                )

    scores_out: dict[str, Any] = {}
    score_keys = ("composite", "nlr_hrv", "sri", "decoupling")
    if scores_daily is not None and not scores_daily.empty:
        sd = scores_daily.copy()
        sd["date"] = pd.to_datetime(sd["date"]).dt.date
        for sk in score_keys:
            if sk not in sd.columns:
                scores_out[sk] = {"reason": "missing_input"}
                continue
            curr = (
                sd.loc[(sd["date"] >= curr_start) & (sd["date"] <= curr_end), sk]
                .dropna()
                .to_numpy(dtype=float)
            )
            prev = (
                sd.loc[(sd["date"] >= prev_start) & (sd["date"] <= prev_end), sk]
                .dropna()
                .to_numpy(dtype=float)
            )
            block = _mom_block(curr, prev, "welch_t")
            scores_out[sk] = block
            if block.get("cohens_d") is not None:
                ranked.append(
                    {
                        "key": sk,
                        "kind": "score",
                        "cohens_d": block["cohens_d"],
                        "significant": block["significant"],
                        "p_value": block["p_value"],
                        "delta_mean": block["delta_mean"],
                    }
                )
    else:
        for sk in score_keys:
            scores_out[sk] = {"reason": "missing_scores_table"}

    ranked.sort(key=lambda r: abs(r["cohens_d"] or 0.0), reverse=True)

    prev_label = f"{py:04d}-{pm:02d}"
    return {
        "month": month_yyyy_mm,
        "previous_month": prev_label,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "metrics": metrics_out,
        "scores": scores_out,
        "trends_ranked_by_effect_size": ranked,
    }


def write_trends_json(
    payload: Mapping[str, Any],
    *,
    out_dir: str | Path | None = None,
) -> Path:
    """Write ``data/trends/<month>.json``."""
    month = str(payload["month"])
    root = Path(__file__).resolve().parents[2]
    d = Path(out_dir) if out_dir is not None else root / "data" / "trends"
    d.mkdir(parents=True, exist_ok=True)
    fp = d / f"{month}.json"
    fp.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return fp


def build_trends_from_daily_csv(
    csv_path: str | Path,
    *,
    month_yyyy_mm: str,
    out_dir: str | Path | None = None,
) -> tuple[dict[str, Any], Path]:
    """
    Convenience: systemic-style CSV → observations + scores → JSON file.
    """
    obs = observations_from_daily_csv(csv_path)
    obs_daily = observations_daily_means(obs)
    scores_daily = scores_wide_from_daily_csv(csv_path)
    payload = compute_month_trends(
        obs_daily=obs_daily,
        scores_daily=scores_daily,
        month_yyyy_mm=month_yyyy_mm,
    )
    path = write_trends_json(payload, out_dir=out_dir)
    return payload, path

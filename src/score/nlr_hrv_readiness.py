"""
src/score/nlr_hrv_readiness.py

NLR × HRV Training-Readiness Score.

Spec: src/score/specs/nlr-hrv-readiness-spec.md
Physiology: skills/health-reasoning.md §1

Formula (spec §1):
    readiness_score = (NLR / NLR_THRESHOLD) × (HRV_baseline_7d / HRV_current_effective)

Higher score = worse readiness.

Design rules (CLAUDE.md):
- Transparent weighted formulas. Each component in its own function.
- Docstrings quote the spec section they implement.
- No ML. Statistical methods only.
- Never invent data — either compute with downweighted confidence or refuse.
"""

from __future__ import annotations

import argparse
import json
import math
import os
import sys
from datetime import date, timedelta
from pathlib import Path
from statistics import mean, median, stdev
from typing import Optional

import pandas as pd

from src.context.flags import get_active_flags
from src.ingest.load_all import load_all
from src.ingest.schema import Observation
from src.score.paths import scores_dir as _scores_dir_fn

# ── constants ──────────────────────────────────────────────────────────────────

_NLR_THRESHOLD           = 3.0    # spec §3.1
_DELOAD_THRESHOLD        = 1.5    # spec §2
_DELOAD_THRESHOLD_ILL    = 1.3    # v1 context adjustment (user instruction)
_CAUTION_THRESHOLD       = 1.0    # spec §2
_BASELINE_WINDOW         = 7      # spec §1 / §3.2
_MIN_BASELINE_DAYS       = 7      # spec §4.4
_ANOMALY_SIGMA           = 2.0    # spec §4.2
_MONOCYTES_HIGH          = 0.8    # 10^9/L, spec §4.3

_STALE_AGING_DAYS        = 30     # spec §4.1 first tier
_STALE_STALE_DAYS        = 60     # spec §4.1 second tier

# HRV confidence multipliers (spec §4.2, §4.4)
_MULT_HRV_ANOMALY        = 0.9    # spec §4.2
_MULT_HRV_IMPUTED        = 0.85   # spec §4.4

def _scores_dir() -> Path:
    return _scores_dir_fn()

# Metric kind to look for in the unified DataFrame for HRV
HRV_METRIC_KIND = "hrv"


# ── formula components ─────────────────────────────────────────────────────────

def nlr_term(nlr: float, threshold: float = _NLR_THRESHOLD) -> float:
    """
    Spec §1: first term of the readiness score.

    §3.1: "produces score 1.0 exactly at the boundary of clinical concern
    (NLR = 3.0). Higher NLR → score > 1.0 from this term alone."
    """
    return nlr / threshold


def hrv_term(hrv_baseline_7d: float, hrv_current_effective: float) -> float:
    """
    Spec §1: second term of the readiness score.

    §3.2: "baseline in the numerator … produces a ratio > 1.0 when HRV drops
    below baseline — same direction as the NLR term. Both terms agree on
    direction: higher = worse."
    """
    if hrv_current_effective <= 0:
        raise ValueError(
            f"hrv_current_effective must be > 0, got {hrv_current_effective}"
        )
    return hrv_baseline_7d / hrv_current_effective


def compute_readiness_score(
    nlr: float,
    hrv_baseline_7d: float,
    hrv_current_effective: float,
) -> float:
    """
    Spec §1 formula:
        readiness_score = (NLR / NLR_THRESHOLD) × (HRV_baseline_7d / HRV_current_effective)

    §3.3: "Multiplicative form: amplifies agreement (both terms in same
    direction), dampens single-system divergences without canceling them."
    """
    return nlr_term(nlr) * hrv_term(hrv_baseline_7d, hrv_current_effective)


def classify_tier(score: float, illness_flag: bool = False) -> str:
    """
    Spec §2 tier thresholds:
        score ≥ 1.5 → deload
        1.0 ≤ score < 1.5 → caution
        score < 1.0 → green

    V1 context adjustment (user instruction; not in spec §2):
    When illness_flag is True the deload boundary shifts from 1.5 → 1.3.
    Rationale: during active illness the NLR denominator is still 3.0 but
    even moderate elevation warrants a deload.
    """
    deload_thresh = _DELOAD_THRESHOLD_ILL if illness_flag else _DELOAD_THRESHOLD
    if score >= deload_thresh:
        return "deload"
    if score >= _CAUTION_THRESHOLD:
        return "caution"
    return "green"


def stale_multiplier(cbc_age_days: int) -> tuple[float, Optional[str]]:
    """
    Spec §4.1: confidence multiplier for CBC age.

    ≤ 30d → (1.0, None)
    30–60d → (0.85, 'cbc_aging')
    > 60d → (0.70, 'cbc_stale')
    """
    if cbc_age_days <= _STALE_AGING_DAYS:
        return 1.0, None
    if cbc_age_days <= _STALE_STALE_DAYS:
        return 0.85, "cbc_aging"
    return 0.70, "cbc_stale"


def geomean(values: list[float]) -> float:
    """
    Spec §4.5: source_confidence_aggregate = geomean(all confidence inputs used).

    §4.5: "Geometric mean is the natural aggregator for ratio-scaled quantities
    and penalizes any single low-confidence input proportionally to its order
    of magnitude."
    """
    if not values:
        return 0.0
    log_sum = sum(math.log(max(v, 1e-9)) for v in values)
    return math.exp(log_sum / len(values))


def detect_hrv_anomaly(
    today_hrv: float,
    baseline_7d: float,
    stddev_7d: float,
) -> bool:
    """
    Spec §4.2: today_hrv is anomalous when:
        |today_hrv − HRV_baseline_7d| > 2 × HRV_stddev_7d
    AND stddev_7d is plausible (> 0).
    """
    if stddev_7d <= 0:
        return False
    return abs(today_hrv - baseline_7d) > _ANOMALY_SIGMA * stddev_7d


# ── private helpers ────────────────────────────────────────────────────────────

def _get_cbc_anchor(
    episodic: list[Observation],
    as_of_date: date,
) -> Optional[dict]:
    """
    Return the most recent blood_panel_draw on or before as_of_date, with
    absolute_neutrophils and absolute_lymphocytes resolved.

    Returns a dict with keys:
        nlr, abs_neutrophils, abs_lymphocytes, abs_monocytes (may be None),
        draw_date, cbc_age_days, source_confidence, quality_flags,
        draw_observation_id.

    Returns None if no usable draw is found.
    """
    draws = [
        o for o in episodic
        if o.metric_kind == "blood_panel_draw"
        and o.ts_utc.date() <= as_of_date
    ]
    if not draws:
        return None

    draw = max(draws, key=lambda o: o.ts_utc)

    # Collect analyte observations for this draw
    analytes: dict[str, Observation] = {}
    for o in episodic:
        if (
            o.metric_kind == "blood_panel_analyte"
            and o.parent_event_id == draw.observation_id
        ):
            slug = o.payload.get("analyte_slug", "")
            if slug:
                analytes[slug] = o

    neut = analytes.get("absolute_neutrophils")
    lymp = analytes.get("absolute_lymphocytes")
    mono = analytes.get("absolute_monocytes")

    if neut is None or lymp is None:
        return None
    if neut.value_numeric is None or lymp.value_numeric is None:
        return None
    if lymp.value_numeric == 0:
        return None

    return {
        "nlr":               neut.value_numeric / lymp.value_numeric,
        "abs_neutrophils":   neut.value_numeric,
        "abs_lymphocytes":   lymp.value_numeric,
        "abs_monocytes":     mono.value_numeric if mono else None,
        "draw_date":         draw.ts_utc.date(),
        "cbc_age_days":      (as_of_date - draw.ts_utc.date()).days,
        "source_confidence": draw.source_confidence,
        "quality_flags":     list(draw.quality_flags),
        "draw_observation_id": draw.observation_id,
    }


def _get_hrv_daily(
    df: pd.DataFrame,
    hrv_metric_kind: str = HRV_METRIC_KIND,
) -> dict[date, tuple[float, float]]:
    """
    Extract per-day HRV from the unified DataFrame.

    Returns dict mapping date → (mean_daily_hrv_ms, mean_daily_source_confidence).
    Only days with at least one valid (non-null, > 0) HRV reading are included.
    """
    if df.empty or "metric_kind" not in df.columns:
        return {}

    hrv = df[df["metric_kind"] == hrv_metric_kind].copy()
    if hrv.empty:
        return {}

    hrv = hrv[hrv["value_numeric"].notna() & (hrv["value_numeric"] > 0)]
    if hrv.empty:
        return {}

    # UTC date for grouping
    hrv["_date"] = pd.to_datetime(hrv["ts_utc"], utc=True).dt.date

    result: dict[date, tuple[float, float]] = {}
    for d, group in hrv.groupby("_date"):
        result[d] = (
            float(group["value_numeric"].mean()),
            float(group["source_confidence"].mean()),
        )
    return result


def _compute_3day_median(
    hrv_daily: dict[date, tuple[float, float]],
    scoring_date: date,
) -> Optional[float]:
    """
    Spec §4.2: "Replace HRV_current_effective with the median of the most
    recent 3 valid daily HRV values (today, today−1, today−2)."

    §4.2: "Why median, not mean: robust to a single outlier."
    """
    recent = sorted(
        [d for d in hrv_daily if d <= scoring_date],
        reverse=True,
    )[:3]
    if not recent:
        return None
    values = [hrv_daily[d][0] for d in recent]
    return float(median(values))


def _build_reasoning(
    score: float,
    tier: str,
    cbc: dict,
    hrv_baseline_7d: float,
    hrv_current_effective: float,
    quality_flags: list[str],
    illness_flag: bool,
    stale_flag: Optional[str],
) -> str:
    """
    Spec §7 reasoning field — deterministic template, same inputs → same string.

    Required fragments in order (spec §7):
    1. Computation
    2. Tier
    3. Dominant driver
    4. Active flags in plain language
    5. Warnings from §4.2/§4.3 when triggered
    """
    parts: list[str] = []

    # 1. Computation
    nlr_rounded   = round(cbc["nlr"], 2)
    base_rounded  = round(hrv_baseline_7d, 1)
    curr_rounded  = round(hrv_current_effective, 1)
    score_rounded = round(score, 2)
    parts.append(
        f"Score {score_rounded} = "
        f"({nlr_rounded}/{_NLR_THRESHOLD}) × ({base_rounded}/{curr_rounded})."
    )

    # 2. Tier (note illness adjustment if active)
    if illness_flag:
        parts.append(
            f"Tier: {tier} (illness flag active; deload threshold {_DELOAD_THRESHOLD_ILL})."
        )
    else:
        parts.append(f"Tier: {tier}.")

    # 3. Dominant driver — whichever term is further from 1.0
    nlr_t = cbc["nlr"] / _NLR_THRESHOLD
    hrv_t = hrv_baseline_7d / hrv_current_effective if hrv_current_effective > 0 else 1.0
    if abs(nlr_t - 1.0) >= abs(hrv_t - 1.0):
        parts.append(
            f"NLR elevated: abs neutrophils {cbc['abs_neutrophils']}, "
            f"abs lymphocytes {cbc['abs_lymphocytes']}."
        )
    else:
        parts.append(
            f"HRV depressed: today {curr_rounded} ms vs 7d baseline {base_rounded} ms."
        )

    # 4. Active flags
    flag_parts: list[str] = []
    if stale_flag == "cbc_aging":
        flag_parts.append(
            f"CBC age: {cbc['cbc_age_days']}d (aging multiplier 0.85)."
        )
    elif stale_flag == "cbc_stale":
        flag_parts.append(
            f"CBC age: {cbc['cbc_age_days']}d (stale multiplier 0.70)."
        )
    if "hrv_anomaly_smoothed" in quality_flags:
        flag_parts.append("HRV anomaly detected: 3-day median substituted (spec §4.2).")
    if "hrv_today_imputed" in quality_flags:
        flag_parts.append("HRV today missing: 3-day median substituted (spec §4.4).")
    if flag_parts:
        parts.append(" ".join(flag_parts))

    # 5. Post-illness warning (v1: from context flag only, no monocyte auto-detect)
    if illness_flag:
        parts.append(
            "Illness window active: inflammatory resolution lag — "
            "autonomic recovery may lead blood-marker normalization (skills/health-reasoning.md §1.2)."
        )

    return " ".join(parts)


# ── public API ─────────────────────────────────────────────────────────────────

def score_day(
    scoring_date: date,
    df: pd.DataFrame,
    episodic: list[Observation],
    context_flags: Optional[dict[str, bool]] = None,
    hrv_metric_kind: str = HRV_METRIC_KIND,
    *,
    context_flags_path: Optional[Path] = None,
) -> dict:
    """
    Compute the NLR × HRV readiness score for one calendar day.

    Spec §7 output schema:
        {
            "score":         float | None,
            "tier":          "deload" | "caution" | "green" | "unknown",
            "confidence":    float,        # ∈ [0.0, 1.0]; 0.0 when score is None
            "reasoning":     str,          # deterministic template, spec §7
            "quality_flags": list[str],    # cbc_stale, hrv_anomaly_smoothed, etc.
        }

    Refusal conditions (spec §4.4):
    - No CBC at all → tier "unknown", cbc_required in reasoning.
    - < 7 valid HRV days for baseline → tier "unknown", hrv_baseline_insufficient.
    - Today's HRV missing AND no 3-day median possible → same refusal.

    Parameters
    ----------
    scoring_date       : Calendar date to score.
    df                 : Unified time-series DataFrame from load_all().
    episodic           : Episodic list from load_all() (must include blood panel obs).
    context_flags      : Pre-loaded flags dict; if None, loaded from YAML.
    hrv_metric_kind    : metric_kind used for HRV rows in df (default: "hrv").
    context_flags_path : Override path for context_flags.yaml.
    """

    # ── resolve context flags ──────────────────────────────────────────────────
    if context_flags is None:
        context_flags = get_active_flags(scoring_date, path=context_flags_path)
    illness_flag = bool(context_flags.get("illness", False))

    quality_flags: list[str] = []
    conf_multipliers: list[float] = []

    # ── CBC anchor ─────────────────────────────────────────────────────────────
    # Spec §4.4: "no CBC at all → refuse"
    cbc = _get_cbc_anchor(episodic, scoring_date)
    if cbc is None:
        return {
            "score":         None,
            "tier":          "unknown",
            "confidence":    0.0,
            "reasoning":     "No CBC data available. Spec §4.4: cbc_required.",
            "quality_flags": [],
        }

    # Stale multiplier (spec §4.1)
    stale_mult, stale_flag = stale_multiplier(cbc["cbc_age_days"])
    if stale_flag:
        quality_flags.append(stale_flag)
    conf_multipliers.append(stale_mult)

    # ── HRV baseline (spec §1: last 7 valid days, excluding today) ─────────────
    hrv_daily = _get_hrv_daily(df, hrv_metric_kind)

    baseline_dates = sorted(
        [d for d in hrv_daily if d < scoring_date],
        reverse=True,
    )[:_BASELINE_WINDOW]

    # Spec §4.4: "< 7 valid HRV days → refuse"
    if len(baseline_dates) < _MIN_BASELINE_DAYS:
        return {
            "score":      None,
            "tier":       "unknown",
            "confidence": 0.0,
            "reasoning":  (
                f"Insufficient HRV baseline: {len(baseline_dates)} valid day(s) "
                f"(need {_MIN_BASELINE_DAYS}). Spec §4.4: hrv_baseline_insufficient."
            ),
            "quality_flags": [],
            "meta": {
                "cbc_age_days": int(cbc["cbc_age_days"]),
            },
        }

    baseline_vals = [hrv_daily[d][0] for d in baseline_dates]
    baseline_conf = [hrv_daily[d][1] for d in baseline_dates]

    hrv_baseline_7d = mean(baseline_vals)
    hrv_stddev_7d   = stdev(baseline_vals) if len(baseline_vals) > 1 else 0.0

    # ── HRV current (spec §1 / §4.2 / §4.4) ──────────────────────────────────
    hrv_current_conf_list: list[float]

    if scoring_date in hrv_daily:
        today_hrv, today_hrv_conf = hrv_daily[scoring_date]

        if detect_hrv_anomaly(today_hrv, hrv_baseline_7d, hrv_stddev_7d):
            # Spec §4.2: replace with 3-day median; confidence multiplier 0.9
            median_3d = _compute_3day_median(hrv_daily, scoring_date)
            if median_3d is not None:
                hrv_current_effective = median_3d
                quality_flags.append("hrv_anomaly_smoothed")
                conf_multipliers.append(_MULT_HRV_ANOMALY)
                # Confidence list: the 3 days used for median
                recent_3 = sorted(
                    [d for d in hrv_daily if d <= scoring_date], reverse=True
                )[:3]
                hrv_current_conf_list = [hrv_daily[d][1] for d in recent_3]
            else:
                hrv_current_effective = today_hrv
                hrv_current_conf_list = [today_hrv_conf]
        else:
            hrv_current_effective = today_hrv
            hrv_current_conf_list = [today_hrv_conf]

    else:
        # Spec §4.4: "today's HRV missing → substitute 3-day median"
        median_3d = _compute_3day_median(hrv_daily, scoring_date)
        if median_3d is None:
            return {
                "score":      None,
                "tier":       "unknown",
                "confidence": 0.0,
                "reasoning":  (
                    "Today's HRV missing and no recent values available for median "
                    "substitution. Spec §4.4: hrv_today_imputed."
                ),
                "quality_flags": quality_flags,
            }
        hrv_current_effective = median_3d
        quality_flags.append("hrv_today_imputed")
        conf_multipliers.append(_MULT_HRV_IMPUTED)
        recent_3 = sorted(
            [d for d in hrv_daily if d < scoring_date], reverse=True
        )[:3]
        hrv_current_conf_list = [hrv_daily[d][1] for d in recent_3]

    # ── compute score and tier ─────────────────────────────────────────────────
    score = compute_readiness_score(
        cbc["nlr"], hrv_baseline_7d, hrv_current_effective
    )
    tier = classify_tier(score, illness_flag)

    # ── confidence (spec §4.5 / §4.6) ─────────────────────────────────────────
    # source_confidence_aggregate = geomean(cbc_conf + baseline_conf + today_conf)
    all_conf = [cbc["source_confidence"]] + baseline_conf + hrv_current_conf_list
    source_conf_agg = geomean(all_conf)

    confidence = source_conf_agg
    for m in conf_multipliers:
        confidence *= m
    confidence = max(0.0, min(1.0, confidence))

    # ── reasoning ─────────────────────────────────────────────────────────────
    reasoning = _build_reasoning(
        score=score,
        tier=tier,
        cbc=cbc,
        hrv_baseline_7d=hrv_baseline_7d,
        hrv_current_effective=hrv_current_effective,
        quality_flags=quality_flags,
        illness_flag=illness_flag,
        stale_flag=stale_flag,
    )

    # ── meta (for composite scorer — not in spec §7 but required by composite-spec §2) ─
    _nlr_t = nlr_term(cbc["nlr"])
    _hrv_t = hrv_term(hrv_baseline_7d, hrv_current_effective)

    return {
        "score":         round(score, 4),
        "tier":          tier,
        "confidence":    round(confidence, 4),
        "reasoning":     reasoning,
        "quality_flags": quality_flags,
        # Composite-facing sub-components; not part of the public spec §7 contract.
        # composite-spec §2: nlr_term > 1.0 → nlr_elevated; hrv_term < 1.0 → hrv_improving
        "meta": {
            "nlr_term":              round(_nlr_t, 4),
            "hrv_term":              round(_hrv_t, 4),
            "nlr":                   round(cbc["nlr"], 4),
            "hrv_baseline_7d":       round(hrv_baseline_7d, 4),
            "hrv_current_effective": round(hrv_current_effective, 4),
            "cbc_age_days":          int(cbc["cbc_age_days"]),
        },
    }


def score_range(
    start_date: date,
    end_date: date,
    df: pd.DataFrame,
    episodic: list[Observation],
    context_flags_path: Optional[Path] = None,
    hrv_metric_kind: str = HRV_METRIC_KIND,
    output_path: Optional[Path] = None,
) -> pd.DataFrame:
    """
    Score every calendar day in [start_date, end_date] and write to parquet.

    Output schema (spec §7): date, score, tier, confidence, reasoning.
    Written to data/scores/nlr_hrv.parquet (or output_path if given).
    """
    rows = []
    current = start_date
    while current <= end_date:
        ctx = get_active_flags(current, path=context_flags_path)
        result = score_day(
            scoring_date=current,
            df=df,
            episodic=episodic,
            context_flags=ctx,
            hrv_metric_kind=hrv_metric_kind,
        )
        rows.append({
            "date":       current,
            "score":      result["score"],
            "tier":       result["tier"],
            "confidence": result["confidence"],
            "reasoning":  result["reasoning"],
            "meta_json": json.dumps(result.get("meta") or {}, separators=(",", ":")),
            "quality_flags_json": json.dumps(result.get("quality_flags") or [], separators=(",", ":")),
        })
        current += timedelta(days=1)

    out_df = pd.DataFrame(rows)

    out_path = output_path or (_scores_dir() / "nlr_hrv.parquet")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_df.to_parquet(out_path, index=False)

    return out_df


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


def _score_range_cli() -> None:
    ap = argparse.ArgumentParser(description="NLR×HRV parquet writer.")
    ap.add_argument("--since", required=True, help="Inclusive ISO date YYYY-MM-DD (timeseries filter).")
    ap.add_argument(
        "--until",
        default=None,
        help="Inclusive end date (default: latest observation date in ingest).",
    )
    ap.add_argument("--rawdata-root", default=None, help="Override RAWDATA_ROOT.")
    ap.add_argument(
        "--context-flags",
        default=None,
        help="Path to context_flags.yaml (or use CONTEXT_FLAGS / HEALTHOS_CONTEXT_FLAGS env).",
    )
    args = ap.parse_args()

    root = _cli_rawdata_root(args.rawdata_root)
    df, episodic = load_all(rawdata_root=root, since=args.since)

    start_d = date.fromisoformat(args.since)
    if args.until:
        end_d = date.fromisoformat(args.until)
    elif not df.empty:
        end_d = pd.Timestamp(df["ts_utc"].max()).date()
    else:
        end_d = start_d

    if end_d < start_d:
        print("nlr_hrv_readiness: empty range — extending end to start date.", file=sys.stderr)
        end_d = start_d

    ctx = _cli_context_flags(args.context_flags)
    score_range(
        start_d,
        end_d,
        df,
        episodic,
        context_flags_path=ctx,
    )
    print(f"Wrote {_scores_dir() / 'nlr_hrv.parquet'}", file=sys.stderr)


if __name__ == "__main__":
    _score_range_cli()

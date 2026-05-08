# Bio-age Proxy Spec (MVP)

## Status

Spec first, implementation second. Transparent weighted heuristics only.

## Purpose

Provide a defendable, inspectable bio-age proxy from three behavioral/physiological contributors:

1. Sleep regularity (SRI)
2. HRV trend (30d trend z-score vs personal 90d baseline)
3. RHR drift (30d sustained drift vs 60d baseline)

This is not a medical age estimate and not a population-norm model. It is a tunable personal heuristic intended to be calibrated over time.

## Explicit Guardrail

**Reject ML approaches for this MVP.**

> "Anchors are heuristic, not validated. They are designed to be defendable and incrementally tunable, not predictive."

## 1. Core Formula

```
bio_age_proxy = chronological_age + Σ(contributor_pull_years)
```

Where each contributor returns:

- `years_pulled: float`
- `share_of_total: float`
- `rationale: str`

and:

```
gap_years = bio_age_proxy - chronological_age
```

## 2. Contributor Definitions

### 2.1 SRI Pull (sleep regularity)

Anchor points (years pulled):

- `SRI = 80` -> `0.0y`
- `SRI = 70` -> `+1.0y`
- `SRI = 60` -> `+2.0y`
- `SRI = 50` -> `+3.0y`

Computation:

- Piecewise linear interpolation between anchor points.
- Clamp high side: `SRI >= 80` returns `0.0y` (no negative pull from SRI in MVP).
- Clamp low side: `SRI <= 50` returns `+3.0y`.

Interpretation:

- Lower SRI increases proxy age.
- This is intentionally simple and monotonic for explainability.

### 2.2 HRV Trend Pull

Input:

- `hrv_trend_z`: 30-day HRV trend z-score vs **personal** 90-day baseline.

Anchors:

- `+1σ` -> `-0.5y`
- `-1σ` -> `+0.5y`

Computation:

```
raw_pull = -0.5 * hrv_trend_z
pull = clamp(raw_pull, -2.0, +2.0)
```

Interpretation:

- Positive HRV trend reduces proxy age.
- Negative HRV trend increases proxy age.
- Cap prevents one term from dominating.

### 2.3 RHR Baseline Pull

Input:

- `rhr_drift_bpm`: sustained 30-day drift (bpm) from 60-day baseline.

Anchor:

- `+5 bpm` sustained for 30 days -> `+0.5y`

MVP computation:

```
pull = max(0.0, rhr_drift_bpm) * (0.5 / 5.0)
```

Interpretation:

- Positive sustained RHR drift increases proxy age.
- Negative drift does **not** reduce proxy age in this MVP (conservative rule).
- No additional cap in MVP; can be added after calibration.

## 3. Shares of Total

Each contributor includes `share_of_total` using absolute contributions:

```
total_abs = Σ(abs(years_pulled_i))
share_of_total_i = abs(years_pulled_i) / total_abs    (if total_abs > 0)
share_of_total_i = 0.0                                 (if total_abs == 0)
```

Why absolute:

- Shares should reflect contribution magnitude regardless of sign.

## 4. Output Contract

`BioAgeBreakdown` dataclass:

- `chronological_age: float`
- `proxy_age: float`
- `gap_years: float`
- `contributors: list[ContributorPull]`

`ContributorPull` dataclass:

- `name: str` (`"sri" | "hrv_trend" | "rhr_baseline"`)
- `years_pulled: float`
- `share_of_total: float`
- `rationale: str`

## 5. Inputs

Required inputs to scorer:

- `chronological_age` (years)
- `sri` (0-100)
- `hrv_trend_z` (z-score)
- `rhr_drift_bpm` (bpm)

No dependence on population norms in MVP.

## 6. Non-goals (MVP)

- No ML regressors/classifiers.
- No population age normalization tables.
- No uncertainty intervals.
- No personalized coefficient fitting.
- No additional contributors beyond the 3 listed above.

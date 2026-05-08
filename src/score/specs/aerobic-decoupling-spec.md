# Aerobic Decoupling (Pa:HR) Trend Spec

## Purpose
Track aerobic durability and running-economy drift by quantifying pace-to-heart-rate efficiency decay within steady aerobic sessions and across time.

## Core Session Formulas
1. **Efficiency Factor (EF)**
   - `EF = normalized_graded_pace / avg_hr`
   - (Cycling variant may use power analogs if present)

2. **Aerobic Decoupling (Pa:HR %)**
   - `decoupling_pct = ((EF_first_half - EF_second_half) / EF_first_half) * 100`

## Thresholds (Per Session)
- `< 5%` -> **Well adapted aerobic base**
- `5% to < 10%` -> **Moderate drift / caution**
- `>= 10%` -> **High drift** (intensity too high or recovery/hydration/stress issue)

## Trend Layer
For comparable Zone 2 efforts:
- `ef_zscore = (today_ef - rolling_30d_ef_mean) / rolling_30d_ef_sd`

Interpretation rule:
- Sustained `ef_zscore < -1.0` for 5 days -> likely accumulating fatigue, illness onset, or dehydration stress

Cross-signal interpretation (with HRV):
- `EF down + HRV down` -> central fatigue/illness likelihood higher
- `EF down + HRV up` -> peripheral limitation likelihood higher (legs, hydration, local muscle stress)

## Inputs
- Session data (Strava or equivalent):
  - Timestamped pace or speed samples
  - Timestamped heart-rate samples
  - Session duration
  - Elevation profile (for graded pace normalization if available)
- Label or filter for comparable aerobic (Z2-like) sessions
- HRV trend signal for cross-interpretation (optional but recommended)

## Data Conditioning Rules
- Minimum session duration for valid decoupling (recommended >=30 minutes steady aerobic)
- Split session into equal first and second halves after warm-up exclusion (implementation-defined)
- Exclude sessions with severe data dropout or implausible HR/pace artifacts

## Edge Cases
1. **Heat/dehydration confounding**
   - Condition: elevated ambient heat or dehydration indicators present
   - Action: keep computation but add confounder warning to interpretation

2. **Illness/recovery confounding**
   - Condition: concurrent illness flags or post-illness period
   - Action: degrade confidence in fitness-inference interpretation

3. **Route non-comparability**
   - Condition: high variability in terrain/surface/wind versus baseline
   - Action: exclude from EF z-score trend set, allow session-level reporting only

4. **Insufficient baseline for z-score**
   - Condition: not enough valid sessions in rolling 30-day window
   - Action: compute session decoupling only; skip trend z-score

## Output Contract (Suggested)
- Session-level:
  - `ef`
  - `decoupling_pct`
  - `decoupling_band` (`good | moderate | high`)
- Trend-level:
  - `ef_zscore` (nullable)
  - `negative_ef_streak_days`
- `flags`:
  - `confounded_heat_dehydration` (bool)
  - `confounded_illness` (bool)
  - `route_non_comparable` (bool)
  - `insufficient_baseline` (bool)
- `warnings` (string[])
- `confidence` (0.0-1.0)

## Reference
- `skills/health-reasoning.md` section 3

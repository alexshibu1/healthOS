# NLR x HRV Training-Readiness Score Spec

## Purpose
Provide a transparent, computable readiness signal by combining inflammatory status (`NLR`) with autonomic recovery (`HRV`), so short-term training load can be adjusted safely.

## Formula
`readiness_score = (NLR / 3.0) * (rolling_7d_hrv_baseline / current_hrv_effective)`

Where:
- `NLR = absolute_neutrophils / absolute_lymphocytes` (from most recent CBC differential)
- `rolling_7d_hrv_baseline` = mean HRV over the most recent 7 days before today
- `current_hrv_effective` = today's HRV, unless anomaly rule triggers (then use 3-day median)

## Thresholds
- `>= 1.5` -> **Deload**
- `1.0 to < 1.5` -> **Caution** (cap intensity at Zone 2)
- `< 1.0` -> **Green**

## Inputs
- Most recent CBC differential:
  - `absolute_neutrophils`
  - `absolute_lymphocytes`
  - `monocytes` (for post-illness window detection)
  - `cbc_timestamp`
- HRV time series:
  - Daily HRV values for at least prior 7 days
  - `today_hrv`
  - HRV timestamps

## Edge Cases
1. **CBC stale (>60 days old)**
   - Condition: `today - cbc_timestamp > 60 days`
   - Action: still compute score, but set:
     - `staleness_flag = true`
     - `confidence_multiplier < 1.0` (implementation-defined; default recommendation: 0.7)

2. **Single-day HRV anomaly**
   - Condition: today's HRV is an outlier vs local window (implementation-defined anomaly test)
   - Action: replace point value in formula:
     - `current_hrv_effective = median(HRV[today-2], HRV[today-1], HRV[today])`

3. **Post-illness inflammatory resolution lag**
   - Condition: within 14 days of elevated monocytes event
   - Action: append explicit warning:
     - `"inflammatory resolution lag: autonomic recovery may lead blood marker normalization"`

## Output Contract (Suggested)
- `readiness_score` (float)
- `zone` (`deload | caution | green`)
- `flags`:
  - `cbc_stale` (bool)
  - `hrv_anomaly_adjusted` (bool)
  - `post_illness_window` (bool)
- `warnings` (string[])
- `confidence` (0.0-1.0)

## Reference
- `skills/health-reasoning.md` section 1

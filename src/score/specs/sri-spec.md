# Sleep Regularity Index (SRI) Spec

## Purpose
Quantify circadian regularity using a validated day-to-day sleep/wake consistency metric derived from timestamped sleep state data.

## Canonical Formula (Phillips)
`SRI = (200 / (M * (N - 1))) * sum_{i=1..N-1} sum_{j=1..M} delta(s[i,j], s[i+1,j]) - 100`

Where:
- `N` = number of days in the window
- `M` = number of epochs per day (e.g., 1440 for 1-minute epochs)
- `s[i,j]` = sleep/wake state at epoch `j` on day `i`
- `delta(a,b) = 1` if states match, else `0`
- Result range: `0` to `100`

## Primary Computation Window
- Rolling 14-day window (`N = 14`)
- Preferred epoch size: 1 minute (or 30-second if available consistently)

## Practical Secondary Proxy
Compute sleep-onset standard deviation over same 14-day window:
- `onset_sd_minutes = stddev(sleep_onset_clock_time over 14 days)`

Use as backup interpretability metric, not replacement for canonical SRI when full state data exists.

## Thresholds
- `SRI < 70` -> **Irregular / elevated risk bucket**
- `70 <= SRI < 80` -> **Moderate regularity**
- `>= 80` -> **High regularity**

## Inputs
- Minute-level (or epoch-level) sleep/wake state by timestamp for at least 14 days
- Daily sleep onset timestamps for at least 14 days
- Timezone-aware timestamps (must be normalized before scoring)

## Edge Cases
1. **Insufficient days**
   - Condition: `< 7` valid days
   - Action: do not compute canonical SRI; return `insufficient_data`

2. **Partial day gaps / missing epochs**
   - Condition: missing state coverage in one or more days
   - Action: impute only if missingness <= implementation limit (recommended <=10% per day), else mark day invalid

3. **Timezone shifts / travel**
   - Condition: timezone change within window
   - Action: normalize all epochs to a consistent reference timezone before matching states

4. **Shift-work style schedule block**
   - Condition: sustained non-24h-consistent timing pattern
   - Action: keep score valid, but add interpretive warning that low SRI may be schedule-constrained rather than behavior-noise

## Output Contract (Suggested)
- `sri` (float 0-100)
- `regularity_band` (`irregular | moderate | high`)
- `onset_sd_minutes` (float)
- `valid_days` (int)
- `flags`:
  - `insufficient_data` (bool)
  - `timezone_adjusted` (bool)
  - `imputed_epochs_used` (bool)
- `warnings` (string[])

## Reference
- `skills/health-reasoning.md` section 2

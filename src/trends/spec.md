# Month-over-month trends — Spec (v1)

## Purpose

Compute **calendar month vs previous calendar month** deltas for:

1. **Every numeric metric** present in the unified observation stream (`metric_kind` + `value_numeric`), after collapsing to **one value per calendar day per metric** (daily mean when multiple rows exist).
2. **Four headline scores** (always emitted as `scores` block):
   - `composite` — daily composite readiness (0–100 scale).
   - `nlr_hrv` — NLR×HRV readiness score (same formula family as `src/score/specs/nlr-hrv-readiness-spec.md`; until a dedicated score parquet exists, may be supplied as an explicit daily column).
   - `sri` — Sleep Regularity Index (0–100).
   - `decoupling` — aerobic decoupling / economy trend layer (unitless z-score); may be supplied as an explicit daily column or omitted / null when not available.

Output is **descriptive + inferential**, not ML: transparent tests and effect sizes only.

## Explicit non-goals (v1)

- No machine learning, clustering, or forecasting.
- No **intervention ranking via projected composite delta** — too speculative; interventions use the flat lookup table (`src/interventions/`) instead.
- No automated anomaly → question triggers.

## Inputs

### A) Unified observations (`DataFrame`)

Required columns:

| column | type | notes |
|--------|------|--------|
| `ts_utc` | tz-aware datetime | bucket to calendar date in UTC |
| `metric_kind` | string | grouping key |
| `value_numeric` | float | rows with null numeric are skipped |

Daily collapse: for each `(date_utc, metric_kind)`, `value_daily = mean(value_numeric)`.

### B) Daily scores table (optional merge)

Wide CSV or DataFrame indexed by **calendar date** with columns used for the four scores (names configurable in code; defaults below).

If a score column is missing, that score’s MoM entry is `null` with `reason: "missing_input"`.

### C) Month label

Target month as `"YYYY-MM"` (the **current** month in the comparison). Previous month is computed by calendar arithmetic.

## Month-over-month delta

For each metric or score series:

- `values_prev` = list of daily values in previous month (non-null).
- `values_curr` = list of daily values in current month (non-null).

Report:

- `n_prev`, `n_curr`
- `mean_prev`, `mean_curr`
- `delta_mean` = `mean_curr - mean_prev`

If either month has **fewer than 2** usable days, skip significance testing (set `significant: false`, `p_value: null`, `cohens_d: null`, `reason: insufficient_days`).

## Significance rule (both required)

For every comparison:

1. **Effect size:** Cohen’s \(d\) for two independent samples (pooled SD), computed on the **raw daily values** in each month.

   \[
   d = \frac{\bar{x}_{curr} - \bar{x}_{prev}}{s_{pooled}}, \quad
   s_{pooled} = \sqrt{\frac{(n_{curr}-1)s_{curr}^2 + (n_{prev}-1)s_{prev}^2}{n_{curr}+n_{prev}-2}}
   \]

2. **Statistical test** — choice depends on **metric class** (not trainable):

| Class | Test | Typical metrics |
|-------|------|------------------|
| **Non-normal stream** | Mann–Whitney U (two-sided) | HRV (`metric_kind` matches `hrv` prefix or equals `hrv`), resting HR daily series (`rhr`, `resting_hr`, or `wake_rhr` daily bridge) |
| **Normalized / bounded scores** | Welch’s \(t\)-test (unequal variance) | `composite`, `nlr_hrv`, `sri`, `decoupling`, and **all other** `metric_kind` series |

**Significant** iff:

\[
|d| > 0.3 \quad\text{and}\quad p < 0.05
\]

Direction is informational: positive \(d\) means current month **higher** than previous.

## Ranking (“surface trends”)

After computing all metrics + scores:

- Build a list of `{ "key", "kind", "cohens_d", "significant", "p_value", "delta_mean", ... }`.
- Sort by **descending \(|d|\)** (effect size), regardless of significance — significance remains a boolean flag on each row.

Do **not** use projected composite deltas for ranking.

## Output file

Path: `data/trends/<YYYY-MM>.json`

Top-level keys:

| key | meaning |
|-----|---------|
| `month` | target month |
| `previous_month` | prior calendar month |
| `generated_at_utc` | ISO timestamp |
| `metrics` | map `metric_kind` → MoM stats + test metadata |
| `scores` | map `composite` \| `nlr_hrv` \| `sri` \| `decoupling` → same shape |
| `trends_ranked_by_effect_size` | sorted list as above |

## Implementation notes

- **Unified schema only**: unknown `metric_kind` values still appear if present in the observations frame.
- **Bridge CSV**: `observations_from_daily_csv()` may synthesize observation-shaped rows for demos when raw parquet is absent; document bridge column → `metric_kind` mapping in code docstrings.

# Composite Readiness Score — Spec

## Status
Spec v1. Implementation: `src/score/composite.py`.

## 1. Design principle: state first, score second

A weighted sum of three lens outputs loses the information that makes this
platform novel. When all three lenses agree, the sum works. When they disagree,
the disagreement is the signal (`skills/health-reasoning.md` §4 divergence matrix).

The output structure therefore leads with a **state label** — a human-readable
classification of what the current physiology pattern *means* — and follows with
a score normalized *within* that state. You cannot collapse "deload because NLR
is elevated while HRV is recovering" and "deload because everything is degraded"
into the same number without destroying the interpretation.

## 2. Inputs

Three lens outputs (each as a typed dict) + profile + active context flags.

### C1 — NLR × HRV (src/score/nlr_hrv_readiness.py)

| field | type | description |
|---|---|---|
| `tier` | str | "deload" \| "caution" \| "green" \| "unknown" |
| `score` | float \| None | raw readiness score |
| `confidence` | float | ∈ [0, 1] |
| `quality_flags` | list[str] | e.g. cbc_stale, hrv_anomaly_smoothed |
| `meta.nlr_term` | float | NLR / 3.0; > 1.0 → NLR elevated |
| `meta.hrv_term` | float | HRV_baseline / HRV_current; < 1.0 → HRV improving |

Derived booleans (composite computes these):
- `nlr_elevated = meta.nlr_term > 1.0`
- `hrv_improving = meta.hrv_term < 1.0` (today's HRV above 7d baseline)
- `hrv_declining = meta.hrv_term > 1.05` (threshold to filter noise)

### C2 — Sleep Regularity Index (src/score/sri.py — future)

| field | type | description |
|---|---|---|
| `regularity_band` | str | "irregular" \| "moderate" \| "high" \| "unknown" |
| `sri` | float \| None | 0–100 |
| `confidence` | float | ∈ [0, 1] |
| `quality_flags` | list[str] | |

### C3 — Aerobic Decoupling / EF (src/score/aerobic_decoupling.py — future)

| field | type | description |
|---|---|---|
| `decoupling_band` | str | "high" \| "moderate" \| "good" \| "unknown" |
| `ef_zscore` | float \| None | rolling 30d z-score |
| `negative_ef_streak_days` | int | consecutive days with ef_zscore < −1.0 |
| `hrv_direction` | str | "up" \| "down" \| "stable" \| "unknown" |
| `confidence` | float | ∈ [0, 1] |
| `quality_flags` | list[str] | |

`hrv_direction` is populated by the caller from C1's `meta.hrv_term` (up if < 0.95,
down if > 1.05, stable otherwise). It enables the Pa:HR ↓ + HRV ↑ vs ↓ split
in the divergence matrix.

## 3. Output schema

```python
{
    "state":            str,         # one of 7 states (§4)
    "score":            int,         # 0–100, normalized within state band (§5)
    "primary_signal":   str,         # "nlr_hrv" | "sri" | "ef" | "convergent" | "context"
    "divergence_flags": list[str],   # patterns from skills/health-reasoning.md §4
    "reasoning":        str,         # deterministic template, same inputs → same string
    "confidence":       float,       # ∈ [0, 1] (§7)
}
```

## 4. States

Seven states, ordered from most to least training-restricting:

| state | meaning | primary action implication |
|---|---|---|
| `illness-risk` | Active illness context + systemic strain | Stop training; investigate illness |
| `deload` | Multiple systems degraded or C1 in deload (convergent) | Cap volume; no high-intensity |
| `accumulating-fatigue` | Trending toward deload; one or two systems moderate | Reduce load; monitor for 3–5 days |
| `peripheral-strain` | EF decoupling without systemic signal; peripheral cause | Confound-check (heat, hydration, legs); don't deload reflexively |
| `autonomic-recovery-leading` | NLR elevated, HRV recovering (§1.2 post-illness divergence) | Hold reload; wearable leads, blood lags |
| `cleared` | Recently exited illness/injury; all systems normalizing | Resume carefully; monitor first CBC confirmation |
| `recovered` | All systems nominal; no recent concern | Unrestricted training |

### 4.1 State decision rules (checked in priority order)

**Rule 1 — illness-risk:**
```
illness_flag=True AND C1.tier ∈ {deload, caution}
primary_signal = "context"
```

**Rule 2 — autonomic-recovery-leading:**
```
C1.tier ∈ {deload, caution}
AND nlr_elevated = True   (NLR > 3.0)
AND hrv_improving = True  (today HRV > 7d baseline)
AND C3.decoupling_band ∈ {good, unknown}
primary_signal = "nlr_hrv"
Note: checked BEFORE general deload — this is a specific diagnostic subtype
```

**Rule 3 — deload:**
```
C1.tier == "deload"   (after rule 2 excluded)
primary_signal = "nlr_hrv"
```

**Rule 4 — peripheral-strain:**
```
C1.tier ∈ {green, caution, unknown}
AND C3.decoupling_band ∈ {high, moderate}
AND C3.hrv_direction ∈ {up, stable, unknown}  ← not central
primary_signal = "ef"
Skill §3.2: "EF ↓ + HRV ↑ → peripheral/environmental"
```

**Rule 5 — accumulating-fatigue:**
```
C3.negative_ef_streak_days ≥ 5
OR (C1.tier == "caution" AND C2.regularity_band ∈ {irregular, moderate})
primary_signal = "ef" (streak) | "convergent" (dual moderate)
Skill §3.2: "sustained ef_zscore < −1.0 for 5 days → accumulating fatigue"
```

**Rule 6 — cleared:**
```
recent_illness = True   (illness/injury window ended within last 14 days)
AND C1.tier == "green"
AND C2.regularity_band ∈ {high, moderate, unknown}
AND C3.decoupling_band ∈ {good, unknown}
primary_signal = "context"
```

**Rule 7 — recovered (default for all-green):**
```
C1.tier ∈ {green, unknown}
AND C2.regularity_band ∈ {high, moderate, unknown}
AND C3.decoupling_band ∈ {good, unknown}
primary_signal = "nlr_hrv"  (or "convergent" if both C1 and C2 explicitly high)
```

**Default (no rule matched):**
```
→ accumulating-fatigue
primary_signal = "convergent"
```

## 5. Score bands and within-state normalization

Score ∈ [0, 100]. Higher always means more training-ready.

| state | band | lo | hi |
|---|---|---|---|
| illness-risk | 10–29 | 10 | 29 |
| deload | 50–69 | 50 | 69 |
| accumulating-fatigue | 30–49 | 30 | 49 |
| peripheral-strain | 55–69 | 55 | 69 |
| autonomic-recovery-leading | 65–79 | 65 | 79 |
| cleared | 75–89 | 75 | 89 |
| recovered | 80–100 | 80 | 100 |

Note: bands overlap by design. State is the primary output; score describes
intensity within that state. Scores from different states are not comparable
numerically — "deload score 65" and "cleared score 65" do not mean the same thing.

### 5.1 Within-state score computation

For each state, compute a `severity ∈ [0.0, 1.0]` where 0 = best within state,
1 = worst within state. Map to band:

```
score = hi − round(severity × (hi − lo))
```

**Severity inputs by state:**

`c1_raw` = C1 readiness score (or 0.7 if None)
`c2_sev` = {irregular: 1.0, moderate: 0.5, high: 0.0, unknown: 0.3}[C2.regularity_band]
`c3_sev` = {high: 1.0, moderate: 0.5, good: 0.0, unknown: 0.3}[C3.decoupling_band]

| state | severity formula |
|---|---|
| illness-risk | `0.7 × clamp((c1_raw − 1.0) / 2.0) + 0.2 × c2_sev + 0.1 × c3_sev` |
| deload | `0.7 × clamp((c1_raw − 1.5) / 1.5) + 0.15 × c2_sev + 0.15 × c3_sev` |
| accumulating-fatigue | `0.5 × clamp(c1_raw / 1.5) + 0.3 × c2_sev + 0.2 × c3_sev` |
| peripheral-strain | `0.2 × clamp(c1_raw / 1.0) + 0.1 × c2_sev + 0.7 × c3_sev` |
| autonomic-recovery-leading | `0.6 × clamp((c1_raw − 1.0) / 1.0) + 0.2 × (1 − C1.meta.hrv_term) + 0.2 × c2_sev` |
| cleared | `0.6 × clamp(c1_raw / 1.0) + 0.2 × c2_sev + 0.2 × c3_sev` |
| recovered | `0.6 × clamp(c1_raw / 1.0) + 0.2 × c2_sev + 0.2 × c3_sev` |

`clamp(x) = max(0.0, min(1.0, x))`

## 6. Divergence flags

Detected from the cross-lens patterns in `skills/health-reasoning.md §4`.
Multiple flags may fire simultaneously.

| flag | detection condition | skill §4 row |
|---|---|---|
| `autonomic_leading_nlr_elevated` | nlr_elevated AND hrv_improving | Row 1 |
| `convergent_stress` | nlr_elevated AND hrv_declining AND C1.tier ∈ {deload,caution} | Row 2 |
| `autonomic_stress_no_inflammation` | NOT nlr_elevated AND hrv_declining | Row 4 |
| `lifestyle_driven_systemic_stress` | C1.tier ∈ {deload,caution} AND C2.band == irregular | Row 5 |
| `acute_noncircadian_stressor` | C1.tier ∈ {deload,caution} AND C2.band == high | Row 6 |
| `circadian_early_warning` | C2.band == irregular AND C1.tier == green | Row 7 |
| `central_fatigue_or_illness` | C3.band ∈ {high,moderate} AND C3.hrv_direction == down | Row 8 |
| `peripheral_environmental` | C3.band ∈ {high,moderate} AND C3.hrv_direction ∈ {up,stable} | Row 9 |
| `recovery_debt_ef_decay` | C3.band ∈ {high,moderate} AND C2.band == irregular | Row 10 |
| `pure_peripheral` | C3.band ∈ {high,moderate} AND C1.tier == green | Row 11 |
| `convergent_reload_risk` | C1.tier==deload AND C2.band==irregular AND C3.band==high | Row 12 |

## 7. Confidence

Base: `geomean(c1.confidence, c2.confidence, c3.confidence)`.

Modifier per divergence flag (multiplicative, compound, capped to [0, 1]):

| flag | modifier |
|---|---|
| `convergent_reload_risk` | × 1.2 |
| `lifestyle_driven_systemic_stress` | × 1.1 |
| `convergent_stress` | × 1.0 |
| `recovery_debt_ef_decay` | × 1.0 |
| `central_fatigue_or_illness` | × 1.0 |
| `acute_noncircadian_stressor` | × 0.9 |
| `peripheral_environmental` | × 0.9 |
| `autonomic_stress_no_inflammation` | × 0.8 |
| `circadian_early_warning` | × 0.8 |
| `autonomic_leading_nlr_elevated` | × 0.7 |
| `pure_peripheral` | × 0.7 |

Missing/unknown inputs count as confidence 0.5 for the geomean.

## 8. Reasoning template

Fragments joined in order:
1. State declaration: `"State: {state} (score {score}/100)."`
2. Primary driver: which lens and its values.
3. Divergence patterns in plain language (one sentence each, from §4).
4. Confidence and confidence-modifier explanation.
5. Action implication from §4 / CLAUDE.md scoring philosophy.

Deterministic: same inputs → same string.

## 9. Parquet output schema

`data/scores/composite.parquet`

| column | type | notes |
|---|---|---|
| date | date | scoring date |
| state | str | one of 7 states |
| score | int | 0–100 |
| primary_signal | str | nlr_hrv \| sri \| ef \| convergent \| context |
| divergence_flags | str | JSON array |
| reasoning | str | deterministic template |
| confidence | float | ∈ [0, 1] |

## 10. Open questions

1. **HRV source.** Until wrist-HRV data is available (HEARTRATE_AUTO carries HR,
   not RMSSD), C1 returns `tier=unknown` and the composite defaults to
   C2/C3-driven states with low confidence.
2. **SRI scorer.** C2 not yet implemented; composite handles `unknown` gracefully.
3. **EF scorer.** C3 not yet implemented. Strava activities.csv provides
   per-session distance and HR averages but not per-minute samples needed for
   within-session split. Blocked on fit_loader.py.
4. **Cleared vs recovered boundary.** Currently uses `recent_illness` boolean
   derived from context_flags illness windows. Needs state-transition tracking
   (deload → cleared → recovered) once a stateful session table exists.
5. **Threshold tuning.** All bands and thresholds are provisional v1 values.
   Revisit after 30 paired data-days vs. daily check-in labels in `evals/`.

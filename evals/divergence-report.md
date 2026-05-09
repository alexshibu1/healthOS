# Divergence report

Generated from `evals/labeled-days.md` using the ingest pipeline (`load_all`) for **NLR×HRV**, `data/scores/sri.parquet` and `data/scores/aerobic_decoupling.parquet` for **C2/C3** (same ``_sri_row_to_input`` / ``_ado_row_to_input`` as production parquet join), then `src.score.composite.score_day`.

## Scaling (read this first)

Felt recovery (1–10 from labeled-days.md) is scaled to 0–100 as `felt_0_100 = felt_1_10 × 10` for Pearson, Spearman, and MAE vs composite score.

## Summary

- **Prior eval (C2/C3 forced to default `unknown`):** Pearson / Spearman **undefined** (σ(predicted)=0, MAE **72.6667** on the same labels) — see git history or pre-2026-05-09 `run_eval.py`.
- **This run:** C2/C3 rows from `data/scores/sri.parquet` and `data/scores/aerobic_decoupling.parquet` via the **same** ``_sri_row_to_input`` / ``_ado_row_to_input`` helpers as production ``score_range_from_parquets``.

- Labeled days: **15** (2026-04-24 → 2026-05-08)
- Ingest `since`: `2026-03-10` (buffer **45** d before first label)
- Scores dir: `/Users/alexshibu/Documents/AlexwebDevBootcamp/healthOS/data/scores`
- Pearson r (predicted composite vs felt×10): **-0.6680**
- Spearman ρ: **-0.6786**
- MAE (on 0–100 scale): **54.9333**
- σ(predicted): **18.9577**, σ(felt×10): **5.7349**

## All days (divergence = predicted − felt×10)

| date | felt 1–10 | felt×10 | predicted | divergence | state |
|------|------------|---------|-----------|------------|-------|
| 2026-04-24 | 6 | 60 | 38 | -22.0 | accumulating-fatigue |
| 2026-04-25 | 7 | 70 | 38 | -32.0 | accumulating-fatigue |
| 2026-04-26 | 7 | 70 | 38 | -32.0 | accumulating-fatigue |
| 2026-04-27 | 7 | 70 | 38 | -32.0 | accumulating-fatigue |
| 2026-04-28 | 7 | 70 | 38 | -32.0 | accumulating-fatigue |
| 2026-04-29 | 7 | 70 | 38 | -32.0 | accumulating-fatigue |
| 2026-04-30 | 7 | 70 | 38 | -32.0 | accumulating-fatigue |
| 2026-05-01 | 7 | 70 | 0 | -70.0 | insufficient_data |
| 2026-05-02 | 7 | 70 | 0 | -70.0 | insufficient_data |
| 2026-05-03 | 7 | 70 | 0 | -70.0 | insufficient_data |
| 2026-05-04 | 8 | 80 | 0 | -80.0 | insufficient_data |
| 2026-05-05 | 8 | 80 | 0 | -80.0 | insufficient_data |
| 2026-05-06 | 8 | 80 | 0 | -80.0 | insufficient_data |
| 2026-05-07 | 8 | 80 | 0 | -80.0 | insufficient_data |
| 2026-05-08 | 8 | 80 | 0 | -80.0 | insufficient_data |

## Top 5 divergences (by |divergence|)

### 1. 2026-05-04 — divergence **-80.0**

- **Felt (1–10):** 8 → felt×10 = 80
- **Predicted composite:** 0 (state `insufficient_data`, confidence 0.3000, primary `convergent`)
- **Divergence flags:** `[]`

#### Inputs (NLR×HRV, SRI, decoupling, context)

```json
{
  "scoring_date": "2026-05-04",
  "nlr_hrv": {
    "tier": "unknown",
    "readiness_score": null,
    "confidence": 0.0,
    "quality_flags": [],
    "meta": {
      "cbc_age_days": 323
    },
    "reasoning_excerpt": "Insufficient HRV baseline: 0 valid day(s) (need 7). Spec §4.4: hrv_baseline_insufficient."
  },
  "sri": {
    "regularity_band": "unknown",
    "sri": null,
    "confidence": 0.5,
    "quality_flags": [],
    "note": "C2 from data/scores/sri.parquet via _sri_row_to_input (same as composite parquet join)."
  },
  "decoupling": {
    "decoupling_band": "unknown",
    "ef_zscore": null,
    "negative_ef_streak_days": 0,
    "hrv_direction": "unknown",
    "confidence": 0.5,
    "quality_flags": [],
    "note": "C3 from data/scores/aerobic_decoupling.parquet via _ado_row_to_input."
  },
  "context_flags": {
    "illness": false,
    "travel": false,
    "injury": false
  }
}
```

#### Composite reasoning

Insufficient data to compute composite. 3 of 3 flagship lenses returned unknown. Most common cause: stale CBC (323d) or insufficient HRV baseline window.

---

### 2. 2026-05-05 — divergence **-80.0**

- **Felt (1–10):** 8 → felt×10 = 80
- **Predicted composite:** 0 (state `insufficient_data`, confidence 0.3000, primary `convergent`)
- **Divergence flags:** `[]`

#### Inputs (NLR×HRV, SRI, decoupling, context)

```json
{
  "scoring_date": "2026-05-05",
  "nlr_hrv": {
    "tier": "unknown",
    "readiness_score": null,
    "confidence": 0.0,
    "quality_flags": [],
    "meta": {
      "cbc_age_days": 324
    },
    "reasoning_excerpt": "Insufficient HRV baseline: 0 valid day(s) (need 7). Spec §4.4: hrv_baseline_insufficient."
  },
  "sri": {
    "regularity_band": "unknown",
    "sri": null,
    "confidence": 0.5,
    "quality_flags": [],
    "note": "C2 from data/scores/sri.parquet via _sri_row_to_input (same as composite parquet join)."
  },
  "decoupling": {
    "decoupling_band": "unknown",
    "ef_zscore": null,
    "negative_ef_streak_days": 0,
    "hrv_direction": "unknown",
    "confidence": 0.5,
    "quality_flags": [],
    "note": "C3 from data/scores/aerobic_decoupling.parquet via _ado_row_to_input."
  },
  "context_flags": {
    "illness": false,
    "travel": false,
    "injury": false
  }
}
```

#### Composite reasoning

Insufficient data to compute composite. 3 of 3 flagship lenses returned unknown. Most common cause: stale CBC (324d) or insufficient HRV baseline window.

---

### 3. 2026-05-06 — divergence **-80.0**

- **Felt (1–10):** 8 → felt×10 = 80
- **Predicted composite:** 0 (state `insufficient_data`, confidence 0.3000, primary `convergent`)
- **Divergence flags:** `[]`

#### Inputs (NLR×HRV, SRI, decoupling, context)

```json
{
  "scoring_date": "2026-05-06",
  "nlr_hrv": {
    "tier": "unknown",
    "readiness_score": null,
    "confidence": 0.0,
    "quality_flags": [],
    "meta": {
      "cbc_age_days": 325
    },
    "reasoning_excerpt": "Insufficient HRV baseline: 0 valid day(s) (need 7). Spec §4.4: hrv_baseline_insufficient."
  },
  "sri": {
    "regularity_band": "unknown",
    "sri": null,
    "confidence": 0.5,
    "quality_flags": [],
    "note": "C2 from data/scores/sri.parquet via _sri_row_to_input (same as composite parquet join)."
  },
  "decoupling": {
    "decoupling_band": "unknown",
    "ef_zscore": null,
    "negative_ef_streak_days": 0,
    "hrv_direction": "unknown",
    "confidence": 0.5,
    "quality_flags": [],
    "note": "C3 from data/scores/aerobic_decoupling.parquet via _ado_row_to_input."
  },
  "context_flags": {
    "illness": false,
    "travel": false,
    "injury": false
  }
}
```

#### Composite reasoning

Insufficient data to compute composite. 3 of 3 flagship lenses returned unknown. Most common cause: stale CBC (325d) or insufficient HRV baseline window.

---

### 4. 2026-05-07 — divergence **-80.0**

- **Felt (1–10):** 8 → felt×10 = 80
- **Predicted composite:** 0 (state `insufficient_data`, confidence 0.3000, primary `convergent`)
- **Divergence flags:** `[]`

#### Inputs (NLR×HRV, SRI, decoupling, context)

```json
{
  "scoring_date": "2026-05-07",
  "nlr_hrv": {
    "tier": "unknown",
    "readiness_score": null,
    "confidence": 0.0,
    "quality_flags": [],
    "meta": {
      "cbc_age_days": 326
    },
    "reasoning_excerpt": "Insufficient HRV baseline: 0 valid day(s) (need 7). Spec §4.4: hrv_baseline_insufficient."
  },
  "sri": {
    "regularity_band": "unknown",
    "sri": null,
    "confidence": 0.5,
    "quality_flags": [],
    "note": "C2 from data/scores/sri.parquet via _sri_row_to_input (same as composite parquet join)."
  },
  "decoupling": {
    "decoupling_band": "unknown",
    "ef_zscore": null,
    "negative_ef_streak_days": 0,
    "hrv_direction": "unknown",
    "confidence": 0.5,
    "quality_flags": [],
    "note": "C3 from data/scores/aerobic_decoupling.parquet via _ado_row_to_input."
  },
  "context_flags": {
    "illness": false,
    "travel": false,
    "injury": false
  }
}
```

#### Composite reasoning

Insufficient data to compute composite. 3 of 3 flagship lenses returned unknown. Most common cause: stale CBC (326d) or insufficient HRV baseline window.

---

### 5. 2026-05-08 — divergence **-80.0**

- **Felt (1–10):** 8 → felt×10 = 80
- **Predicted composite:** 0 (state `insufficient_data`, confidence 0.3000, primary `convergent`)
- **Divergence flags:** `[]`

#### Inputs (NLR×HRV, SRI, decoupling, context)

```json
{
  "scoring_date": "2026-05-08",
  "nlr_hrv": {
    "tier": "unknown",
    "readiness_score": null,
    "confidence": 0.0,
    "quality_flags": [],
    "meta": {
      "cbc_age_days": 327
    },
    "reasoning_excerpt": "Insufficient HRV baseline: 0 valid day(s) (need 7). Spec §4.4: hrv_baseline_insufficient."
  },
  "sri": {
    "regularity_band": "unknown",
    "sri": null,
    "confidence": 0.5,
    "quality_flags": [],
    "note": "C2 from data/scores/sri.parquet via _sri_row_to_input (same as composite parquet join)."
  },
  "decoupling": {
    "decoupling_band": "unknown",
    "ef_zscore": null,
    "negative_ef_streak_days": 0,
    "hrv_direction": "unknown",
    "confidence": 0.5,
    "quality_flags": [],
    "note": "C3 from data/scores/aerobic_decoupling.parquet via _ado_row_to_input."
  },
  "context_flags": {
    "illness": false,
    "travel": false,
    "injury": false
  }
}
```

#### Composite reasoning

Insufficient data to compute composite. 3 of 3 flagship lenses returned unknown. Most common cause: stale CBC (327d) or insufficient HRV baseline window.

---

_No thresholds were auto-tuned. C2/C3 come from disk parquets when the labeled date exists there; otherwise those lenses fall back to unknown like a missing join row in production._
---
draw_date: 2025-06-15
draw_date_confidence: estimated_within_2_weeks
lab: unknown
episode: 2025_food_poisoning
quality_flags:
  - drawn_during_illness
  - date_unconfirmed
  - lab_unknown
  - non_baseline
---

# Blood Panel — 2025 Food Poisoning Episode

## Metadata

| field | value |
|---|---|
| `draw_date` | **2025-??-?? — UNCONFIRMED, needs user input** |
| `episode_context` | drawn during active illness following food poisoning |
| `is_baseline` | false |
| `lab` | unknown |
| `panel_type` | CBC + WBC differential + absolute counts + kidney/metabolic + electrolytes |
| `source_format` | user-provided structured markdown tables |
| `quality_flags` | `drawn_during_illness`, `date_unconfirmed`, `lab_unknown` |
| `scoring_intent` | indicator only; not baseline; downweight per `nlr-hrv-readiness-spec.md` staleness rule |

**Loader note.** Until `draw_date` is confirmed, this file fails the `ts_utc not null` validation contract in `src/ingest/schema.md` and will be sent to `rejects/` rather than the observation table.

## Complete Blood Count (CBC)

| Marker | Value | Reference Range | Status |
|---|---|---|---|
| Leukocytes (WBC) | 14.0 x10⁹/L | 4.0 – 11.0 | High |
| Erythrocytes (RBC) | 5.2 x10¹²/L | 4.5 – 5.5 | Normal |
| Hemoglobin | 154 g/L | 127 – 168 | Normal |
| Hematocrit | 0.45 L/L | 0.42 – 0.54 | Normal |
| MCV | 87 fL | 80 – 100 | Normal |
| MCH | 29.6 pg | 25 – 31 | Normal |
| MCHC | 340 g/L | 320 – 360 | Normal |
| RDW | 13.6 % | 10 – 16 | Normal |
| Platelets | 293 x10⁹/L | 150 – 400 | Normal |
| MPV | 7.1 fL | 7.4 – 9.4 | Low |

## White Blood Cell Differential (relative)

| Marker | Value | Reference Range | Status |
|---|---|---|---|
| Relative Neutrophils | 0.73 | 0.40 – 0.75 | High-normal |
| Relative Lymphocytes | 0.13 | 0.20 – 0.45 | Low |
| Relative Monocytes | 0.08 | 0.02 – 0.10 | Normal |
| Relative Eosinophils | 0.05 | 0.01 – 0.06 | Normal |
| Relative Basophils | 0.01 | 0.00 – 0.01 | High-normal |

## Absolute Cell Counts

| Marker | Value | Reference Range | Status |
|---|---|---|---|
| Absolute Neutrophils | 10.2 x10⁹/L | 2.0 – 7.5 | High |
| Absolute Lymphocytes | 1.9 x10⁹/L | 1.5 – 4.0 | Normal |
| Absolute Monocytes | 1.2 x10⁹/L | 0.2 – 0.8 | High |
| Absolute Eosinophils | 0.6 x10⁹/L | 0.0 – 0.4 | High |
| Absolute Basophils | 0.1 x10⁹/L | 0.0 – 0.1 | Upper normal |
| Nucleated RBC | 0 | 0 | Normal |

## Kidney & Metabolic Panel

| Marker | Value | Reference Range | Status |
|---|---|---|---|
| Urea | 4.2 mmol/L | 2.6 – 7.2 | Normal |
| Creatinine | 92 µmol/L | 61 – 115 | Normal |
| eGFR | >90 (estimated) | ≥90 | Normal kidney function |
| Random Glucose | 5.4 mmol/L | 4.0 – 7.8 | Normal |

## Electrolytes

| Marker | Value | Reference Range | Status |
|---|---|---|---|
| Sodium | 135 mmol/L | 136 – 145 | Slightly Low |
| Potassium | 3.8 mmol/L | 3.5 – 5.1 | Normal |
| Chloride | 99 mmol/L | 101 – 111 | Slightly Low |
| CO₂ (Bicarbonate) | 25 mmol/L | 22 – 32 | Normal |
| Anion Gap | ~11 | 4 – 12 | Normal |

## Derived markers (computed at scoring time, not stored)

These are *not* persisted. They are computed by `src/score/` from the values above. Listed here only so the file is self-documenting.

- `NLR = abs_neutrophils / abs_lymphocytes = 10.2 / 1.9 = 5.37`
- `PLR = platelets / abs_lymphocytes = 293 / 1.9 = 154.2`
- `SII = (platelets * abs_neutrophils) / abs_lymphocytes = (293 * 10.2) / 1.9 = 1572.9`

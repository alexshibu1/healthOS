---
draw_date: 2026-03-28
draw_date_confidence: user_confirmed
lab: demo_synthetic
episode: demo_illness_spring_2026
quality_flags:
  - drawn_during_illness
  - non_baseline
  - lab_unknown
---

# Blood Panel — Synthetic Demo (Not Real Human Data)

> **This file is intentionally fake** for the public `alex_demo` dataset. It is
> shaped to exercise NLR, monocyte burden, and illness windows in the scoring
> layer without publishing real laboratory results.

## Complete Blood Count (CBC)

| Marker | Value | Reference Range | Status |
|---|---|---|---|
| Leukocytes (WBC) | 9.2 x10⁹/L | 4.0 – 11.0 | Normal high |
| Erythrocytes (RBC) | 5.1 x10¹²/L | 4.5 – 5.5 | Normal |
| Hemoglobin | 152 g/L | 127 – 168 | Normal |
| Hematocrit | 0.44 L/L | 0.42 – 0.54 | Normal |
| MCV | 88 fL | 80 – 100 | Normal |
| Platelets | 265 x10⁹/L | 150 – 400 | Normal |

## White Blood Cell Differential (relative)

| Marker | Value | Reference Range | Status |
|---|---|---|---|
| Relative Neutrophils | 0.62 | 0.40 – 0.75 | Mid |
| Relative Lymphocytes | 0.22 | 0.20 – 0.45 | Low-normal |
| Relative Monocytes | 0.12 | 0.02 – 0.10 | High |

## Absolute Cell Counts

| Marker | Value | Reference Range | Status |
|---|---|---|---|
| Absolute Neutrophils | 7.20 x10⁹/L | 2.0 – 7.5 | High-normal |
| Absolute Lymphocytes | 1.80 x10⁹/L | 1.5 – 4.0 | Normal |
| Absolute Monocytes | 0.95 x10⁹/L | 0.2 – 0.8 | High |

## Derived (computed for audit trail)

- **NLR** = abs_neutrophils / abs_lymphocytes ≈ 7.20 / 1.80 = **4.0**

# Divergence analysis — maintenance note + current behavior

## Generated report

**Step 1 — refresh numbers:** `evals/divergence-report.md` is **overwritten** each time you run:

```bash
python evals/run_eval.py
```

Read that file for Pearson / Spearman / MAE and the per-day table. This document is **not** auto-generated; update it when methodology or composite rules change materially.

## Eval harness (current)

- **`evals/run_eval.py`** loads labels from `evals/labeled-days.md`, runs **`load_all`** for NLR×HRV, reads **`data/scores/sri.parquet`** and **`data/scores/aerobic_decoupling.parquet`** for C2/C3 (same row mapping as production `composite.score_range_from_parquets`), then **`composite.score_day`**. The three flagship parquets **must exist** before the eval runs.

## Composite headline (current)

- If **NLR×HRV (C1) tier is `unknown`**, composite is **`insufficient_data`** (score **0**, confidence floor **0.3**) — **even when SRI and aerobic decoupling have bands**. The wedge cannot be fused without C1; see `src/score/specs/composite-spec.md` Rule 0.

- Eval correlations vs subjective felt scores are **descriptive only** (small **n**, protocol in `labeled-days.md`). Use `divergence-report.md` for the latest metrics after each run.

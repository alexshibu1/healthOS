# Ship report — verification pass

## Verification commands (this run)

| Step | Result |
|------|--------|
| `make demo-pipeline` | **Exit 0** when run with full host permissions; writes `web/src/data/snapshot.json` and `web/src/data/llm_prompt.txt`. |
| `snapshot.json` / `llm_prompt.txt` | **Present and non-empty** (`snapshot.json` ~10 KB, `llm_prompt.txt` ~2.6 KB after pipeline). |
| `cd web && npm run build` | **Exit 0** (`tsc -b && vite build` succeeded). |
| `pytest -q` | **Exit 0**, **102 passed**. |

### Failure observed (not patched)

- **Cursor sandbox / restricted run:** `make demo-pipeline` **failed** (`exit 2`, **Segmentation fault: 11** on the first `python -m src.ingest.load_all` step). Re-running the **same** Make target **outside** the sandbox completed **cleanly (exit 0)**. Treat constrained-agent environments as **unsafe for NumPy/pandas-heavy ingest** unless verified.

## First ~500 characters of `web/src/data/llm_prompt.txt` (structure check)

After the latest pipeline run, the file opens with the intended section order:

```
## Health Intelligence Report — Recommendation Request

## Your role

You are a sports physician and decision-theory analyst reviewing a personal
health intelligence report. The user wants the top 3 highest-impact
interventions for the next 14 days, ranked by impact-per-effort.

## The user

Age 24, sex male. Training modality: running. Primary goal: longevity.

## Today's reading (2026-04-30)

Composite state: insufficient_data (0/100, confidence 0.30)
Reasoning: NLR×HRV absent — Insufficient wake HRV history for baseline window. Headline composite requires NLR×HRV (wedge); SRI / aerobic readouts below are supportive only — do not infer a 0–100 training readiness from partial lenses alone. Composite scorer confidence `0.30`. Do not extrapolate readiness from headline numbers yet.

## Three flagship lenses

NLR×HRV (inflammatory + autonomic): 0.0, tier unknown, data age 330d
Sleep Regularity Index (circadian): 65, tier irregular, window 14d
Aerobic Decoupling (exercise economy): —σ, tier unknown, window 30d
```

## What shipped (one line per fix)

- **README:** Quickstart + “What this is” / wedge narrative reorder; “Run on your own data” template line; notes that `make demo` regenerates `snapshot.json` and `llm_prompt.txt`.
- **`src/report/llm_prompt.py`:** Deterministic prompt builder + CLI; framework excerpt from `skills/health-reasoning.md` §4 (matrix stripped).
- **`src/report/snapshot_builder.py`:** After writing `snapshot.json`, regenerates `web/src/data/llm_prompt.txt` when profile + skill paths resolve.
- **`web/src/components/LLMHandoff.tsx` + `App.tsx`:** Chapter V handoff with copy + preview; roman numeral aligns with divergence visibility.
- **`tests/report/test_llm_prompt.py`:** Markers + `insufficient_data` coverage.
- **Repo hygiene:** `.gitignore` extended (`__pycache__`, `.pytest_cache`, `.DS_Store`, etc.); tracked `__pycache__` bytecode removed from index; leaked `data/scores/bio_age.parquet` removed from index (directory remains ignored).
- **`src/ingest/__init__.py`:** One-line module docstring.

## Cleanup / drift noted but not addressed (bounded scope)

- **TODO/FIXME/XXX:** None found via repo search at ship time (no action taken).
- **`AUDIT_REPORT.md` / `CLONE_AUDIT.md`:** Not refreshed as part of this ship checklist (historical audit text may still mention older composite behavior).
- **Pyenv / OpenSSL `hashlib`:** Every Python process logs `unsupported hash type blake2b` / `blake2s` to stderr; builds still complete — root fix is environment (Python/OpenSSL build), not repo code.

## Test failures or warnings

- **Failures:** None (`pytest`: **102 passed**).
- **`pytest`:** `RuntimeWarning` in `tests/trends/test_mom.py::test_ranked_sorted_by_abs_cohens_d` — SciPy moment calculation with nearly identical data (“catastrophic cancellation”).
- **`npm run build`:** Rollup **chunk size > 500 kB** informational warning (bundle size / code-splitting suggestion only).

## Final state

**Shippable: Yes.** — Demo pipeline, web production build, and full test suite succeed on the host environment used for this pass; web artifacts exist and the LLM prompt structure matches the intended headings and sections.

**Caveat:** Run ingest/scoring **outside** Cursor’s sandbox (or verify your runner does not SIGSEGV) before trusting CI or agent-only verification.

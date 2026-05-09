# Monthly snapshot JSON — specification

Implementations: `src/report/snapshot_builder.py` builds `SnapshotData` (see `web/src/types.ts`).

Outputs a single JSON object with **every** `SnapshotData` field present — optional TS fields (`?`) still appear (`null`, empty array `[]`, or omission only where TS allows strict undefined; Python builder emits explicit `null` for optional omissions when omitted from JSON breaks consumers — **`todayReasoning`**: string or omit if empty; serde: include `todayScoreDisplay`, `todayReasoning` only when meaningful).

CLI: `python -m src.report.snapshot_builder --date YYYY-MM-DD --out path/to/snapshot.json`

## §1 Required inputs (blocking)

`snapshot_builder` refuses to run if **any** of these files are missing.

| Path | Columns (minimum) | Regenerate hint |
|---|---|---|
| `data/scores/composite.parquet` | `date`, `state`, `score`, `primary_signal`, `divergence_flags`, `reasoning`, `confidence` | Run composite `score_range` over your ingest window via your pipeline (bundled CLI pending). Rows must cover the snapshot calendar month and six prior months plus one day earlier for deltas. |
| `data/scores/nlr_hrv.parquet` | `date`, `score`, `tier`, `confidence`, `reasoning` | `nlr_hrv_readiness.score_range` after `load_all`, or nightly job. |
| `data/scores/sri.parquet` | `date`, `score`, `tier`, `window_days` (optional, default filled as 14) | Derived from Philips SRI once `src/score/sri.py` ships — until then export from analysis or systemic daily surrogate `sri_score` if policy allows (document provenance elsewhere). |
| `data/scores/aerobic_decoupling.parquet` | `date`, `tier`, `window_days`; **and** either `zscore` or `ef_zscore` | EF / Pa:HR scorer (pending). Prefer real session-level decoupling. |
| `data/scores/bio_age.parquet` | `date`, `proxy_age`, `gap_years`, `contributors_json` | `python -c "from pathlib import Path; from src.score.bio_age import score_timeseries_to_parquet; score_timeseries_to_parquet(input_csv=Path('…/daily.csv'), chronological_age=float(Path('data/profile.yaml').read_text()), output_parquet=Path('data/scores/bio_age.parquet'))"` — wire age from `data/profile.yaml` in practice |

Also required on disk:

- `data/context_flags.yaml`
- `data/profile.yaml`

## §2 Optional inputs (filled with derivations)

| Path | Snapshot fields |
|---|---|
| `data/trends/<YYYY-MM>.json` | `secondaryReadouts` (top four by `\|Cohen's d\|` from `trends_ranked_by_effect_size`), extra copy for `monthlyContext.readiness.reasoning`. |
| `data/interventions/<YYYY-MM-DD>.json` | `interventions`. If absent, deterministic rank from `src/interventions/rank.py::rank_interventions` using a synthesized snapshot envelope (see §5). |

## §3 `SnapshotData` field → builder source

All keys match `SnapshotData` in TypeScript unless noted.

| Field | Primary source | Derivation if missing secondary |
|---|---|---|
| `state` | `composite.parquet` row → map composite state strings to frontend `SnapshotState` (hyphen-preserving IDs) — includes `insufficient_data` and `accumulating-fatigue`. | See `_COMPOSITE_TO_SNAPSHOT_UI`. |
| `score` | Same row `score`; when `state` is insufficient confidence branch, numerical score is still `score` parquet (typically `0`). | — |
| `todayScoreDisplay` | When composite `state == insufficient_data`, set **`"—"`** so headline avoids a falsely confident numeric. Omit else. | Prefer omit for normal days. |
| `todayDelta` | Composite scores for date `d` and `d − 1` | `Delta.value = score(d) − score(d−1)`; `vs: "yesterday"`. Undefined prior day ⇒ `value: 0`. |
| `subline` | Composite `reasoning` + context | **Insufficient data**: template naming which flagship streams are missing (parses NLR/SRI/decoupling row tiers + parquet absence). Else one-line truncation of composite reasoning (first sentence). |
| `action` | Composite state | Fixed template map mirroring `_STATE_ACTIONS` in composite scorer + insufficient_data copy. |
| `todayReasoning` | Composite `reasoning` (full paragraph) when present | — |
| `monthlyContext.readiness.score` | **Mean composite `score`** for reporting month (calendar containing `d`) | — |
| `monthlyContext.readiness.vsLastMonth` | Mean current month − mean previous calendar month composite | Units: points vs month mean. |
| `monthlyContext.readiness.windowLabel` | Derived | `"April 2026 (calendar month)"` style. |
| `monthlyContext.readiness.meaning` | Derived | References month mean ± vs last month. |
| `monthlyContext.readiness.reasoning` | `trends` JSON excerpt if present else template | Trends top rank one-liner — else empty string. |
| `monthlyContext.bioAge.*` | `bio_age.parquet` row for `date == d`; `contributors_json` → breakdown | chronological years from profile `age` |
| `monthlyTrajectory` | `composite.parquet` all rows in reporting month ordered by date | `DailyTrajectoryEntry` per day length = month span; padded days without rows use `{ state: insufficient_data, score: 0 }`. `todayDayOfMonth` vs `null` if `d` not in month. |
| `monthlyHistory` | Last **6 calendar months ending** at reporting month; each point = monthly mean composite | Last entry MUST equal `monthlyContext.readiness.score` contract in TS (`assert` parity in builder tests). Oldest→newest. |
| `sevenDayState` | Last seven dates ending `d`, composite→UI state ordered oldest→newest | Mirrors deprecated Today strip. |
| `secondaryReadouts` | `trends` ranked top four | Fallback: synthesize ≤4 rows from bio-age contributors + today's composite confidence + one HRV-derived line placeholder from NLR parquet trend on last scores (documented fallback). |
| `streams` | Parquet freshness | Derived: infer “synced” staleness bands from newest `date` per parquet table vs scoring date (amazfit surrogate = nlr_hrv presence, …). Synthetic but numeric; template-only labels. |
| `flagship.nlrHrv` | `nlr_hrv.parquet` | Sparkline last 14 `score`; `dataAgeDays` from regex `CBC age: (\d+)d` else `reasoning` heuristics; **unknown tier** ⇒ `displayScore: "—"`, prose reason; numeric `score` filled as **0** to satisfy TS (UI prefers `displayScore`). |
| `flagship.sri` | `sri.parquet` | Same pattern unknown tier ⇒ display dash. |
| `flagship.decoupling` | `aerobic_decoupling.parquet` | Unknown ⇒ `displayZscore: "—"` (extended TS), z numeric 0. |
| `divergence` | `divergence_flags` JSON array + insufficient_data + YAML context | Builds `drivers` rows (NLR staleness strings, HR…). `DiagnosticQuestion` when insufficient_data — deterministic triage options. |
| `interventions` | Interventions JSON or `rank_interventions` | Map YAML rules to Intervention shape (defaults for category / projections templated). |

## §4 Parquet freshness → `DataStream`

**Rule**: map five logical sources to parquet max dates intersecting ingest reality — without raw sync logs:

- **whoop** → placeholder `"missing"` (no parquet column until branded stream exists)
- **amazfit** → if `nlr_hrv` row exists for `d`: `fresh`; else stale/missing thresholds by days since nearest `nlr_hrv.date ≤ d`.
- **strava** → from `decoupling` parquet last date (cardio surrogate)
- **jefit** → always `missing` until volume parquet exists (`missing`).
- **bloodwork** → NLR CBC age substring from flagship reasoning / `reasoning`.

Status buckets: `<3d` fresh, `<14d` stale, `<60d` old, else missing.

*(Inline in code for exact thresholds.)*

## §5 Intervention fallback snapshot envelope

Passed to `rank_interventions(snapshot)` keys:

| Key | Origin |
|---|---|
| `state` | Hyphen-less composite slug or UI mapping as needed |
| `readiness_score` | composite score |
| `sri_score` | flagship / sri parquet |
| `gap_years` | bio_age row |
| `nlr_value` | parsed from flagship reasoning or `score` × threshold proxy when tier known |
| `illness_active` | `true`/`false` from `get_active_flags` |
| Other keys | optional `target_time="22:30"`, `subjective_energy_1_10` from systemic stub if wired later |

## §6 TypeScript coupling

Whenever builder emits a composite state not historically in the SPA, **`web/src/types.ts::SnapshotState`**, **`stateColors.ts`**, and KPI/Flagship renders must acknowledge it (`insufficient_data`, `accumulating-fatigue`, flagship `tier: unknown`, optional headline `todayScoreDisplay`).

# Unified Ingest Schema

## Purpose

Normalize multi-source health data (Amazfit Helio, Strava, JeFit, blood panels, future sources) into a single observation model that:

- preserves source fidelity (no destructive flattening),
- supports both continuous streams and irregular events,
- carries per-row provenance and confidence,
- is queryable without re-parsing the original files.

This is a spec, not a schema migration. Loaders in `src/ingest/<source>/` are responsible for producing rows that conform; `src/score/` consumes them.

## Design principles

1. **One observation table, two cadence kinds.** Every row is an observation. The shape difference between a 1/min HR stream and a quarterly CBC draw is captured by a `cadence_kind` discriminator, not by two physical tables.
2. **Narrow typed columns + wide JSON payload.** Hot-path fields the scorer reads (`ts_utc`, `value_numeric`, `metric_kind`, `source_confidence`) are typed columns. Source-native fields are preserved verbatim in `payload`. The cost of adding a new source is zero schema migrations.
3. **Provenance is non-negotiable.** Every row knows which file it came from, which row of that file, which source, and how much we trust the source for that metric. If a number disagrees with felt experience, you can trace it back to bytes on disk.
4. **No flattening of inherently multi-part observations.** Per-minute sleep stages, lift sets in a session, analytes in a CBC draw — these are stored as multiple component rows linked to a parent event, not as one mega-row with 30 columns.
5. **Both UTC and original timezone, always.** UTC for math; original timezone for human-meaningful queries ("what time of day did I sleep?"). Never store one and discard the other.

## Two cadence kinds

| cadence_kind | meaning | examples | shape |
|---|---|---|---|
| `stream` | regular, high-frequency continuous samples | minute-level HR, minute-level sleep stage, minute-level steps | one row per sample |
| `event` | irregular, episodic, may be multi-component | CBC draw, lift session, Strava workout, body weigh-in, JeFit profile entry | parent row + zero or more component rows |

A loader decides cadence_kind per file, not per row. The amazfit `HEARTRATE_AUTO` file produces only `stream` rows. The amazfit `SLEEP` summary file produces only `event` rows. The amazfit `SLEEP_MINUTE` file produces `stream` rows (one per minute, metric_kind=`sleep_stage`).

## Core observation table

Logical schema (storage format — Parquet, DuckDB, SQLite — is a separate decision):

| column | type | nullable | description |
|---|---|---|---|
| `observation_id` | string (UUID or hash) | no | stable primary key; deterministic from `(source, source_file, source_row_id)` so re-ingest is idempotent |
| `parent_event_id` | string | yes | for component rows of a multi-part event (null for streams and standalone events) |
| `source` | enum string | no | `amazfit`, `strava`, `jefit`, `blood_panel`, `manual`, ... |
| `source_file` | string | no | original file path relative to `rawdata/` |
| `source_section` | string | yes | for sectioned exports (JeFit `PROFILE`, `WORKOUT SESSIONS`, etc.); null otherwise |
| `source_row_id` | string | yes | original row identifier when present (Strava `Activity ID`, JeFit `row_id`); else `f"{source_file}:{line_no}"` |
| `cadence_kind` | enum string | no | `stream` \| `event` |
| `metric_kind` | enum string | no | canonical metric name (see catalog below) |
| `ts_utc` | timestamp (UTC) | no | canonical instant; for intervals, this is the start |
| `ts_end_utc` | timestamp (UTC) | yes | end of interval observations (sleep window, workout session); null for point observations |
| `tz_original` | string | no | IANA tz name when known (`America/New_York`); else fixed offset (`-04:00`); else `UTC` |
| `ts_original` | string | no | timestamp string exactly as it appeared in source — for debug and round-trip verification |
| `value_numeric` | float64 | yes | single numeric measurement when applicable; null for categorical or composite observations |
| `value_unit` | string | yes | canonical unit (`bpm`, `ms`, `count`, `kg`, `m`, `s`, `mmol/L`, `10^9/L`, `pct`, `kcal`, ...); null when value_numeric is null |
| `value_text` | string | yes | for categorical observations (sleep stage `LIGHT`, activity type `Run`); null otherwise |
| `source_confidence` | float (0.0–1.0) | no | per-row trust level (see ladder below) |
| `quality_flags` | array<string> | yes | machine-readable issue tags (`off_wrist`, `imputed`, `edited_after_measurement`, `tz_assumed`, `sparse_minute`, `route_non_comparable`, ...) |
| `payload` | JSON | yes | source-native fields not promoted to typed columns; preserved verbatim |
| `ingested_at_utc` | timestamp (UTC) | no | when this row was loaded; allows re-ingest comparison |

### Canonical units rule

- HR → `bpm`
- HRV (RMSSD/SDNN) → `ms`
- distance → `m` (meters; convert from km/mi at load time)
- weight → `kg` (convert from lbs at load time)
- height → `cm`
- temperature → `°C`
- pace → `s_per_km` (seconds per km; lower = faster — store the rate, not the inverse)
- power → `W`
- blood concentrations → SI units (`mmol/L` for glucose, `10^9/L` for cell counts)

Convert at load time so the scoring layer never sees mixed units. The original units string lives in `payload.original_unit` for traceability.

### Identity rule

`observation_id` is deterministic so re-ingesting the same file produces the same IDs. Suggested formula:

```
observation_id = sha1(f"{source}|{source_file}|{source_section or ''}|{source_row_id}|{metric_kind}")[:16]
```

This makes ingestion idempotent and allows joining repeated exports (e.g., monthly Amazfit pulls) without duplicate rows.

## Source-specific payload pattern

`payload` is a JSON object holding source-native fields not promoted to typed columns. Two rules:

1. **Never alter the original values.** If JeFit stored weight in `lbs`, `payload.weight_lbs` keeps the original number; `value_numeric` carries the canonical kg conversion.
2. **Never invent fields.** If the source has no field, `payload` does not invent one. Missing data stays missing.

Example (Strava workout session, parent event row):

```json
{
  "activity_type": "Run",
  "elapsed_time_s": 6113,
  "moving_time_s": 6113,
  "distance_m_original": 0,
  "max_hr": 170,
  "avg_hr": 92,
  "weather": {"temperature_c": null, "humidity": null, "wind_speed": null},
  "perceived_exertion": null,
  "raw_columns_preserved": "see source_row_id"
}
```

Component rows for the same Strava session would carry `parent_event_id` pointing at the parent's `observation_id`, with `metric_kind` like `workout_avg_hr`, `workout_distance`, `workout_avg_pace`, `workout_elevation_gain`. This lets the scoring layer query "all `workout_avg_hr` for runs in May" as a single-table scan without re-parsing 100-column Strava rows.

## Source confidence ladder

Defaults; loaders may override with rationale documented in source-loader docstrings. Rule of thumb: numbers express how much the scoring layer should weight a single value, not how true the value is.

| source / metric | source_confidence | rationale |
|---|---|---|
| Chest-strap HRV (sleep-tracked) | 1.00 | gold standard; cited in `skills/health-reasoning.md` §1 |
| Garmin / Polar HRV (sleep-tracked) | 0.85 | continuous monitoring with good RR detection |
| Amazfit / Zepp HRV (wake-tracked) | 0.55 | per `CLAUDE.md`: "HRV logged at wake, not during sleep. Less reliable than chest strap." |
| Amazfit HR (continuous, minute-level) | 0.75 | optical, but continuous — trend signal stronger than point values |
| Amazfit sleep stage (4-class) | 0.65 | actigraphy-based stages, not EEG |
| Strava pace / power | 0.95 | per `CLAUDE.md`: trust pace/power over HR |
| Strava HR (zones) | 0.60 | per `CLAUDE.md`: zones often miscalibrated |
| Strava distance / elevation | 0.90 | GPS-derived, generally reliable |
| JeFit weight (self-entered) | 0.50 | self-report, infrequent, often-zero placeholder values |
| JeFit lift volume | 0.85 | user actively logs sets; high engagement = high reliability |
| Blood panel (CBC, lipid, etc.) | 1.00 | clinical lab |
| Manual subjective entry | 0.40 | introspection; low signal-to-noise |

A row whose confidence is below scoring's per-metric threshold is *kept* (never dropped) but flagged in `quality_flags` and downweighted at scoring time. The schema preserves; the scorer decides what to use.

## Timezone handling rule

Three cases observed in `rawdata/`:

| case | example | rule |
|---|---|---|
| explicit UTC offset present | Amazfit `BODY` `2025-06-04 19:17:00+0000`, Amazfit `SLEEP` `2026-01-06 05:00:00+0000` | parse offset; set `tz_original` to that offset; convert to UTC for `ts_utc` |
| no timezone, vendor uses local | Amazfit `HEARTRATE_AUTO` `2026-01-05 17:17` | assume local; `tz_original` = user's known local tz (anchored from JeFit `SETTING.zonedifference` or user profile); add `quality_flags = ["tz_assumed"]` |
| sectioned export with metadata | JeFit `SETTING.zonedifference,-4` | use the section value as the *default* for rows in the same export that have no inline timezone |

The user's local tz is configured once in `src/ingest/config.toml` (or equivalent); loaders read it. If the user travels, daylight savings boundaries crossed within a file are flagged via `quality_flags = ["dst_boundary"]`.

`ts_original` always preserves the source string verbatim, even after parsing. This is the audit trail: any UTC bug can be diagnosed by re-parsing the original.

## Sleep stage handling rule

Per `CLAUDE.md`: sleep stages are stored separately, not flattened.

Three independent observation streams come out of the Amazfit sleep export:

1. **Per-minute sleep stage stream.** From `SLEEP_MINUTE`. One row per minute. `cadence_kind=stream`, `metric_kind=sleep_stage`, `value_text` ∈ {`DEEP`, `LIGHT`, `REM`, `WAKE`}, `value_numeric=null`. Per-minute HR and respiratory rate live in `payload` (`{"hr": 60, "respiratory_rate": null}`) — they are *attributes* of the sleep-stage observation, not separate rows, because they share the exact timestamp and are meaningless apart from sleep state.
2. **Daily sleep summary event.** From `SLEEP`. One parent event row per night. `cadence_kind=event`, `metric_kind=sleep_summary`, `ts_utc=start`, `ts_end_utc=stop`, `value_numeric=null`, `payload={"deep_min": 88, "light_min": 235, "wake_min": 2, "rem_min": 128, "naps": null}`.
3. **Optional component rows for SRI computation convenience.** If the SRI scorer wants per-minute state matched to clock-of-day, it joins on `metric_kind=sleep_stage` directly. Daily summary is *not* a substitute for per-minute data — and per-minute data is *not* derivable from daily summary. Both are kept; neither shadows the other.

Rationale: the Phillips SRI formula (per `skills/health-reasoning.md` §2) requires per-epoch state. Collapsing the per-minute stream into a daily summary destroys SRI computability. The schema enforces this physically.

## Episodic vs time-series: CBC and other blood panels

`CLAUDE.md` rule: blood panels are episodic, not time-series; treat as context.

A CBC draw is one *event* with multiple analytes. Storage pattern:

- One **parent event row**: `metric_kind=blood_panel`, `cadence_kind=event`, `value_numeric=null`, `payload={"panel_name": "CBC differential", "lab": "...", "drawn_fasting": true}`.
- One **component row per analyte**: `parent_event_id=<parent.observation_id>`, `metric_kind` ∈ {`blood_neutrophils_abs`, `blood_lymphocytes_abs`, `blood_monocytes_abs`, `blood_platelets`, ...}, `value_numeric=10.2`, `value_unit="10^9/L"`.
- Derived metrics (e.g., NLR = neutrophils ÷ lymphocytes) are *not* stored as rows. They are computed by the scoring layer and are spec'd in `src/score/specs/nlr-hrv-readiness-spec.md`. Storing computed values invites stale derivations.

Same pattern applies to lipid panels, hormone panels, hsCRP, etc. New analytes need only a new `metric_kind` string — no schema change.

### Episodic-vs-stream join contract for the scorer

The scoring layer joins the two cadence kinds via a "last-known-anchor" rule, not by interpolation:

- For any day `D`, look up the most recent `blood_panel` event with `ts_utc ≤ D`.
- If the gap exceeds the spec's staleness threshold (e.g., 60 days for NLR per `nlr-hrv-readiness-spec.md`), set the score's confidence-multiplier accordingly and emit a flag.
- Never linearly interpolate between two CBC draws. Episodic anchors anchor; they do not interpolate.

## Validation contract (loader → schema)

Each loader in `src/ingest/<source>/` must guarantee, for every row it emits:

1. `observation_id` is unique and deterministic.
2. `ts_utc` is timezone-aware UTC; `tz_original` is non-empty.
3. `ts_original` is exactly the string from the source file (no formatting changes).
4. `value_numeric`, `value_unit`, and `value_text` are mutually consistent (numeric value implies unit; categorical value has no unit).
5. `source_confidence ∈ [0.0, 1.0]`.
6. `payload` is valid JSON (or null) and contains no fields already promoted to typed columns.
7. Component rows reference an existing `parent_event_id` within the same load.
8. Rows that fail validation go to a `rejects/` table with the failure reason; they are *not silently dropped*.

A `validate_schema.py` script (separate spec to be written when loaders begin) runs over a loaded dataset and asserts these invariants.

## What this schema deliberately does not do

- **No "canonical day" table.** Daily aggregations are computed by `src/score/` from observations. Storing a pre-aggregated daily table here would couple ingest to scoring.
- **No metric registry / enum enforcement at the column level.** `metric_kind` is a string, not a database enum. Adding a new metric is one loader change, no schema migration. A separate `metric_kind_catalog.md` will document known values once two loaders exist.
- **No deduplication across exports.** Re-ingesting the same Amazfit pull twice produces the same `observation_id`s, so a deterministic "insert or replace" handles overlaps. The schema does not try to merge two HR readings at the same instant from different sensors — it keeps both, distinguished by `source`. The scorer chooses.
- **No PII redaction.** That happens in a publishing layer outside ingest. Source files contain DOB, name, image URLs; the schema preserves these in `payload` only when the loader explicitly extracts them, and the ingest config decides whether to load them at all.

## Open questions (block before implementation)

These need explicit answers before the first loader is written:

1. **Storage format.** Parquet (column-oriented, fast scans, JSON in payload) or DuckDB (queryable, single file, also good with JSON)? Recommend DuckDB for development, Parquet for archival exports.
2. **`metric_kind` naming convention.** `snake_case_with_units` (`hr_bpm`, `hrv_rmssd_ms`) or `domain.kind` (`heart.hr`, `sleep.stage`)? Recommend `snake_case_no_units` (`hr`, `hrv_rmssd`, `sleep_stage`) — units belong in `value_unit`, not in the metric name.
3. **User local timezone source.** Hard-code in config or read from JeFit `SETTING.zonedifference`? Recommend config, with the JeFit value as a sanity-check assertion at load time.
4. **JeFit weight-zero handling.** Treat `0` as missing (likely correct) or as literal zero? Recommend missing, with `quality_flags=["sentinel_zero"]`. Verify against user's recollection.

## Cross-references

- `CLAUDE.md` — sources, quirks, guardrails (especially "do not generate synthetic data", "spec before code", "transparent weighted formulas over ML").
- `skills/health-reasoning.md` — physiology layer; explains *why* per-row confidence and per-minute sleep stages matter for the flagship metrics.
- `src/score/specs/nlr-hrv-readiness-spec.md` — defines the 60-day CBC staleness rule that the schema's episodic-anchor join must satisfy.
- `src/score/specs/sri-spec.md` — requires the per-minute sleep-stage stream this schema preserves.
- `src/score/specs/aerobic-decoupling-spec.md` — consumes Strava session components produced by the parent–component pattern above.

# Universal CSV loader — specification

Single-file ingest for `rawdata/universal.csv`: one row per calendar day (or blood-draw row keyed by `date`), wide columns, sparse blanks allowed.

## File location

- Path: `{RAWDATA_ROOT}/universal.csv`
- Encoding: UTF-8
- Format: RFC-style CSV with header row

## Column names (exact spellings)

Headers are matched **case-insensitively** after trimming ASCII whitespace; canonical names below.

| Column | Required | Blank handling | `metric_kind` / behavior |
|--------|----------|----------------|---------------------------|
| `date` | **yes** | empty → **Reject** row (`missing_date`) | Anchor for all observations from this row (ISO `YYYY-MM-DD` unless noted below). |
| `hrv_ms` | no | blank → skip | `hr`, `value_unit` = `ms`, `source_confidence` = **0.60** (per ladder: generic wearable RMSSD proxy mapped into HR channel). |
| `rhr_bpm` | no | blank → skip | `rhr`, `value_unit` = `bpm`, confidence **0.70**. |
| `sleep_onset` | no | blank → skip sleep block | Start of sleep interval (see §Sleep). |
| `sleep_offset` | no | blank → skip sleep block | End of sleep interval. |
| `sleep_hours` | no | blank → optional payload only | If numeric: stored in `sleep_summary.payload.sleep_hours`. |
| `steps` | no | blank → skip | `activity_steps`, `value_unit` = `count`, confidence **0.75**. |
| `weight_kg` | no | blank → skip | `body_weight`, `value_unit` = `kg`, confidence **0.70**, **episodic**. |
| `workout_type` | no | blank allowed | Parent `workout_session` `value_text`; if blank but other `workout_*` numbers exist, parent still emitted with `value_text=null`. |
| `workout_distance_m` | no | blank → skip component | `workout_distance`, `m`, confidence **0.90**. |
| `workout_moving_time_s` | no | blank → skip component | `workout_moving_time`, `s`, **0.95**. |
| `workout_avg_hr` | no | blank → skip component | `workout_avg_hr`, `bpm`, **0.60**. |
| `workout_avg_pace_s_per_km` | no | blank → skip component | `workout_avg_pace`, `s_per_km`, **0.85**. |
| `neutrophils_abs` | no | blank → skip CBC block | `blood_panel_analyte`, **episodic**, parent required. |
| `lymphocytes_abs` | no | blank → skip CBC block | same |
| `monocytes_abs` | no | blank → skip CBC block | same |
| `glucose_mmol` | no | blank → skip | `blood_glucose`, `mmol/L`, confidence **0.90**. |
| `notes` | no | blank → skip | **Not ingested.** Non-blank values are logged to stderr once per row (`[universal_csv] notes=…`). |

### Sleep (`sleep_summary`)

- Emitted only if **both** `sleep_onset` and `sleep_offset` parse successfully.
- `metric_kind` = `sleep_summary`, `cadence_kind` = `event`.
- `ts_utc` = onset instant (UTC); `ts_end_utc` = offset instant (UTC).
- Naive datetimes use `USER_TZ` from `src/ingest/config.py`.
- `source_confidence` = **0.65**.
- `payload` includes `sleep_hours` when that column parses as a positive float.

### Workout block

- **Parent** `workout_session` is emitted if `workout_type` is non-blank **or** any of `workout_distance_m`, `workout_moving_time_s`, `workout_avg_hr`, `workout_avg_pace_s_per_km` parses as numeric.
- Parent `ts_utc` = row date at **local noon** in `USER_TZ`, converted to UTC (stable anchor for same-day session envelope).
- Components reference `parent_event_id` = parent `observation_id`.
- Parent confidence **0.85**.

### Blood panel (CBC absolutes)

- A **`blood_panel_draw`** parent is emitted only when **all three** of `neutrophils_abs`, `lymphocytes_abs`, `monocytes_abs` are present and parse as positive floats (×10⁹/L).
- Three **`blood_panel_analyte`** rows follow, `parent_event_id` linked, `value_unit` = `10^9/L`, confidence **1.00**.
- **NLR is not stored.** Scorers derive neutrophils ÷ lymphocytes from analyte rows (expected ≈ 5.37 when inputs are 10.2 and 1.9).

### Derived NLR (documentation only)

\\[
\text{NLR} = \frac{\text{neutrophils\_abs}}{\text{lymphocytes\_abs}}
\\]

Not persisted as an observation.

## Source provenance

- `source` = `universal_csv`
- `source_file` = `universal.csv` (relative to `RAWDATA_ROOT`)

## Contract

- Returns `(list[Observation], list[Reject])` like all loaders.
- Blank cells never crash parsing; invalid numbers → skip that metric or Reject row for fatal issues (missing `date`).

## Interaction with `load_all`

- If `universal.csv` exists, it is loaded **in addition** to other sources when present.
- If **`amazfit helio/` is absent**, other device exports are optional: load universal-only when `universal.csv` exists; do not require Amazfit/Strava/JeFit files in that mode.

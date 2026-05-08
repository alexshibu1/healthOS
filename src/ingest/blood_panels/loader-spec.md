# Blood Panel Loader Spec

## Status

Spec only. No implementation. Per `CLAUDE.md`: "Spec before code for any component over ~30 lines."

## Purpose

Load one or more blood-panel markdown files from `rawdata/blood_panels/` into the unified observation model. Each file is one lab draw. The loader emits a parent event row per draw plus one component row per parsed analyte. Rejected files or analytes go to `rejects/`; nothing is silently dropped.

---

## 1. Inputs and outputs

**Input:** one `.md` file under `rawdata/blood_panels/`, with YAML frontmatter and pipe-table sections.

**Output:** `tuple[list[Observation], list[Reject]]`
- One parent `Observation` per draw: `metric_kind=blood_panel_draw`, `cadence_kind=event`
- N component `Observation` rows per draw: `metric_kind=blood_<analyte>`, `cadence_kind=event`, `parent_event_id=parent.observation_id`

**Public API** (mirrors existing loaders):
```python
def load(panel_md: Path, rawdata_root: Optional[Path] = None) -> tuple[list[Observation], list[Reject]]:
```

---

## 2. Frontmatter

### 2.1 Format

YAML block delimited by `---` at the top of the file. Must appear before any markdown content.

```yaml
---
draw_date: 2025-06-15
draw_date_confidence: confirmed          # confirmed | estimated_within_2_weeks | estimated_within_1_month | unknown
lab: LifeLabs
episode: 2025_food_poisoning             # optional; null if omitted
quality_flags: [drawn_during_illness, date_unconfirmed, lab_unknown, non_baseline]
---
```

All fields except `episode` are required. If frontmatter is missing or malformed, reject the entire file.

### 2.2 Required fields

| field | type | validation |
|---|---|---|
| `draw_date` | `YYYY-MM-DD` string | parseable by `datetime.date.fromisoformat`; required |
| `draw_date_confidence` | string | one of the four values above; required |
| `lab` | string | any non-empty string; `"unknown"` is valid |
| `quality_flags` | list of strings | may be empty `[]`; values are passed through verbatim |
| `episode` | string | optional; `null` if absent |

### 2.3 Reject trigger

If `draw_date` is absent, unparseable, or the file has no frontmatter block: emit one `Reject` with `source_row_id="frontmatter"` and `reasons=["draw_date missing or unparseable: <reason>"]`. Return immediately — do not attempt to parse sections.

### 2.4 Defensive flag injection

If `draw_date_confidence != "confirmed"` AND `"date_unconfirmed"` is not already in the frontmatter `quality_flags`, add `"date_unconfirmed"` to the flag set before constructing observations. This prevents a stale frontmatter from silently lacking the flag.

---

## 3. Date handling

Blood panels have a draw date but no draw time. Treat the date as midnight UTC.

| field | value |
|---|---|
| `ts_utc` | `datetime(year, month, day, 0, 0, 0, tzinfo=timezone.utc)` |
| `ts_end_utc` | `None` |
| `tz_original` | `"UTC"` |
| `ts_original` | frontmatter `draw_date` string verbatim (e.g. `"2025-06-15"`) |
| `quality_flags` (added by loader) | always add `"time_of_draw_unknown"` |

The combined quality_flags on every row = frontmatter flags + `["time_of_draw_unknown"]`.

---

## 4. Section detection

The loader reads the file line by line. On encountering a line that begins with `## `, it checks the stripped heading against the known set. Unrecognized headings (e.g., `## Metadata`, `## Derived markers`) are silently skipped; no observations or rejects are emitted for them.

| recognized heading | section slug | notes |
|---|---|---|
| `Complete Blood Count (CBC)` | `cbc` | title may also appear as bare `CBC` |
| `White Blood Cell Differential` | `wbc_diff` | matches if heading starts with this; `(relative)` suffix ignored |
| `Absolute Cell Counts` | `abs_counts` | exact |
| `Kidney & Metabolic Panel` | `kidney_metabolic` | exact |
| `Electrolytes` | `electrolytes` | exact |

Matching is **case-insensitive**, stripping the leading `## ` before comparison.

---

## 5. Table parsing

Within a recognized section, pipe-delimited lines are table rows. Parse as follows:

1. **Separator rows** — lines where every non-empty cell matches `/^-+$/` — are skipped.
2. **Header row** — first non-separator pipe row; extract column names. Expected: `Marker | Value | Reference Range | Status`. Column order is determined dynamically (do not hard-code indices).
3. **Data rows** — all subsequent pipe rows. Split on `|`, strip each cell. Map to header columns.

If the header row is missing or does not contain a `Marker` column, skip the section with a `Reject` for the whole section (`source_row_id=f"{draw_date}:{section_slug}:header"`, `reasons=["section table header missing or unrecognized"]`).

---

## 6. Value parsing

For each data row, `raw_value = row["Value"].strip()`.

| pattern | action |
|---|---|
| Empty string | skip row entirely (no observation, no reject) |
| Starts with `>` | `value_numeric=None`, `value_text=raw_value`, `value_unit=None`; add `"non_numeric_value"` to row flags |
| Starts with `~` | strip `~`, parse float, `value_numeric=float`, `value_unit` from lookup; add `"approx_value"` to row flags |
| Pure `0` or `0.0` | `value_numeric=0.0`, `value_unit` from lookup; **not** treated as sentinel zero |
| Otherwise | take first whitespace-delimited token, `float(token)`, `value_unit` from lookup; reject row if `ValueError` |

The canonical `value_unit` always comes from the analyte lookup table (§7), never parsed from the value string. Store the raw value string in `payload["original_value_str"]`.

---

## 7. Analyte lookup table

The lookup key is `(section_slug, normalized_marker)`. Normalized marker = `marker.lower().strip()`. Unrecognized markers: emit with `metric_kind=f"blood_{slug}"` (where `slug` is underscore-normalized marker text) and add `"unknown_analyte"` to row flags — do not reject.

### CBC (`cbc`)

| normalized marker | metric_kind | canonical_unit |
|---|---|---|
| `leukocytes (wbc)` | `blood_wbc` | `10^9/L` |
| `erythrocytes (rbc)` | `blood_rbc` | `10^12/L` |
| `hemoglobin` | `blood_hemoglobin` | `g/L` |
| `hematocrit` | `blood_hematocrit` | `ratio` |
| `mcv` | `blood_mcv` | `fL` |
| `mch` | `blood_mch` | `pg` |
| `mchc` | `blood_mchc` | `g/L` |
| `rdw` | `blood_rdw` | `pct` |
| `platelets` | `blood_platelets` | `10^9/L` |
| `mpv` | `blood_mpv` | `fL` |

### WBC differential (`wbc_diff`)

| normalized marker | metric_kind | canonical_unit |
|---|---|---|
| `relative neutrophils` | `blood_neutrophils_pct` | `ratio` |
| `relative lymphocytes` | `blood_lymphocytes_pct` | `ratio` |
| `relative monocytes` | `blood_monocytes_pct` | `ratio` |
| `relative eosinophils` | `blood_eosinophils_pct` | `ratio` |
| `relative basophils` | `blood_basophils_pct` | `ratio` |

`ratio` = dimensionless fraction in [0, 1].

### Absolute cell counts (`abs_counts`)

| normalized marker | metric_kind | canonical_unit |
|---|---|---|
| `absolute neutrophils` | `blood_neutrophils_abs` | `10^9/L` |
| `absolute lymphocytes` | `blood_lymphocytes_abs` | `10^9/L` |
| `absolute monocytes` | `blood_monocytes_abs` | `10^9/L` |
| `absolute eosinophils` | `blood_eosinophils_abs` | `10^9/L` |
| `absolute basophils` | `blood_basophils_abs` | `10^9/L` |
| `nucleated rbc` | `blood_nrbc_abs` | `10^9/L` |

### Kidney & metabolic (`kidney_metabolic`)

| normalized marker | metric_kind | canonical_unit |
|---|---|---|
| `urea` | `blood_urea` | `mmol/L` |
| `creatinine` | `blood_creatinine` | `umol/L` |
| `egfr` | `blood_egfr` | — (non-numeric; see §6) |
| `random glucose` | `blood_glucose` | `mmol/L` |

Note on eGFR: ">`90 (estimated)`" cannot be parsed as numeric. The loader emits it as `value_text`, `value_numeric=None`, `value_unit=None` with `"non_numeric_value"` flag. The canonical_unit cell is left blank in the lookup for this marker.

### Electrolytes (`electrolytes`)

| normalized marker | metric_kind | canonical_unit |
|---|---|---|
| `sodium` | `blood_sodium` | `mmol/L` |
| `potassium` | `blood_potassium` | `mmol/L` |
| `chloride` | `blood_chloride` | `mmol/L` |
| `co₂ (bicarbonate)` | `blood_bicarbonate` | `mmol/L` |
| `anion gap` | `blood_anion_gap` | `mmol/L` |

---

## 8. Parent event row

One per draw, regardless of how many sections parse successfully.

| field | value |
|---|---|
| `observation_id` | `make_observation_id("blood_panel", rel_path, None, source_row_id, "blood_panel_draw")` |
| `source` | `"blood_panel"` |
| `source_file` | path relative to `rawdata_root` |
| `source_section` | `None` |
| `source_row_id` | `f"{draw_date}:panel"` |
| `cadence_kind` | `"event"` |
| `metric_kind` | `"blood_panel_draw"` |
| `ts_utc` | midnight UTC on draw date |
| `ts_end_utc` | `None` |
| `tz_original` | `"UTC"` |
| `ts_original` | frontmatter `draw_date` string verbatim |
| `value_numeric` | `None` |
| `value_unit` | `None` |
| `value_text` | `None` |
| `source_confidence` | `1.00` (clinical lab; §source-confidence-ladder in schema.md) |
| `quality_flags` | frontmatter flags + `["time_of_draw_unknown"]` |
| `payload` | `{"episode": ..., "lab": ..., "draw_date_confidence": ..., "sections_present": [...slug list...]}` |

---

## 9. Component rows

One per parsed analyte, linked to the parent.

| field | value |
|---|---|
| `observation_id` | `make_observation_id("blood_panel", rel_path, section_slug, source_row_id, metric_kind)` |
| `parent_event_id` | parent `observation_id` |
| `source` | `"blood_panel"` |
| `source_file` | same as parent |
| `source_section` | section slug (e.g. `"cbc"`) |
| `source_row_id` | `f"{draw_date}:{section_slug}:{normalized_marker}"` |
| `cadence_kind` | `"event"` |
| `metric_kind` | from lookup table |
| `ts_utc` | same as parent |
| `tz_original` | `"UTC"` |
| `ts_original` | frontmatter `draw_date` string verbatim |
| `value_numeric` | parsed float or `None` |
| `value_unit` | canonical unit from lookup or `None` |
| `value_text` | non-numeric string or `None` |
| `source_confidence` | `1.00` |
| `quality_flags` | frontmatter flags + `["time_of_draw_unknown"]` + any row-level flags (`approx_value`, `non_numeric_value`, `unknown_analyte`) |
| `payload` | `{"marker_display_name": ..., "reference_range": ..., "status": ..., "original_value_str": ...}` |

---

## 10. Source confidence

`1.00` for all rows (parent and components). The clinical lab is the most trusted source in the schema. Quality flags carry the context (illness, date uncertainty, unknown lab). Downstream confidence multipliers live in the scorer (`nlr-hrv-readiness-spec.md §4`), not here.

---

## 11. Validation and rejects

Every `Observation` passes through `validate_observation()` before being added to the output list. Failures go to `Reject`; observations are never silently dropped.

Reject `source_row_id` conventions:
- Failed frontmatter: `"frontmatter"`
- Failed section header: `f"{draw_date}:{section_slug}:header"`
- Failed analyte row: `f"{draw_date}:{section_slug}:{normalized_marker}"`

---

## 12. Derived metrics

**Not stored.** NLR, PLR, SII, and any other ratios are computed by `src/score/` from component rows. The file's `## Derived markers` section is skipped entirely.

---

## 13. Not in scope

- Multi-file batch loading (handled by `load_all.py` calling this loader per file)
- Non-markdown formats (future spec if needed)
- Interpolation between draws (scorer responsibility per schema.md §episodic-anchor join)
- Unit conversion within the loader: canonical units are defined in the lookup; the values in the file are already in those units. If a future file uses different units (e.g., mg/dL for glucose), the lookup table must be extended with a converter — not handled generically here.

---

## 14. Cross-references

- `src/ingest/schema.py` and `schema.md` — observation model, validate_observation, make_observation_id, source confidence ladder
- `rawdata/blood_panels/2025_food_poisoning_panel.md` — the concrete file this loader targets
- `src/score/specs/nlr-hrv-readiness-spec.md` — consumes `blood_neutrophils_abs` and `blood_lymphocytes_abs` from component rows; the scorer owns the staleness multipliers
- `src/ingest/strava/loader.py` — reference implementation for parent + component pattern

# Blood Panel Markdown Loader Spec (One-Off Format)

## Status

Spec first, then code. This loader is intentionally specific to your blood-panel markdown format in `rawdata/blood_panels/`; it is not a generic markdown parser.

## Purpose

Parse one blood panel markdown file with:
- YAML frontmatter at top
- named `##` sections
- pipe-delimited analyte tables

Output:
- 1 parent event observation per draw
- N component analyte observations linked by `parent_event_id`

## File Shape (expected)

1) Frontmatter at file top between leading `---` delimiters  
2) Markdown body with section headers and pipe tables  
3) Optional narrative sections are ignored unless they match known section names

---

## 1) Frontmatter contract

### 1.1 Delimiters

Loader reads YAML frontmatter only if it is the first block in the file:

```text
---
<yaml>
---
```

If frontmatter is missing, malformed, or not at top: reject entire file.

### 1.2 Required fields

| field | type | required | rule |
|---|---|---|---|
| `draw_date` | string | yes | must be ISO date `YYYY-MM-DD` |
| `quality_flags` | list[string] | yes | may be empty list, but key must exist |

Additional fields are optional and preserved in parent payload.

### 1.3 Hard refusal rule

If either required field is missing (or `draw_date` not ISO date), loader refuses to load the file:
- emit a file-level `Reject`
- emit zero observations

---

## 2) Section detection contract

Loader recognizes only these sections for analyte extraction:

- `## CBC`
- `## White Blood Cell Differential`
- `## Absolute Cell Counts`
- `## Kidney & Metabolic Panel`
- `## Electrolytes`

Each parsed analyte row carries that section identity in `source_section` (canonical slug):
- `cbc`
- `white_blood_cell_differential`
- `absolute_cell_counts`
- `kidney_metabolic_panel`
- `electrolytes`

### Compatibility aliasing (same meaning)

Because your current file uses slight variants, loader treats the following as aliases:
- `## Complete Blood Count (CBC)` -> `cbc`
- `## White Blood Cell Differential (relative)` -> `white_blood_cell_differential`

Unrecognized sections are skipped.

---

## 3) Per-section table parsing

Within each recognized section, parse markdown pipe tables:

1. First pipe row = header
2. Separator row (`---`) skipped
3. Remaining pipe rows = analytes

Expected columns:
- `Marker`
- `Value`
- `Reference Range`
- `Status`

Column order may vary; matching is by header name.

If a recognized section has no valid header row containing all expected columns:
- emit section-level `Reject`
- skip that section

---

## 4) Output structure contract

## 4.1 Parent row (one per file)

Create one event observation:
- `metric_kind = "blood_panel_draw"`
- `cadence_kind = "event"`
- `ts_utc = draw_date at 00:00:00 UTC`
- `source_confidence = 1.0`
- `source = "blood_panel"`
- `parent_event_id = null`

Recommended IDs:
- `source_row_id = "<draw_date>:panel"`
- `observation_id = make_observation_id(...)`

## 4.2 Component rows (one per analyte)

Create one event observation per parsed analyte:
- `metric_kind = "blood_panel_analyte"` (single kind for all components; distinguishes analytes via `payload` for stable `metric_kind`-based episodic grouping in `load_all`)
- `parent_event_id = <parent observation_id>`
- `source_confidence = 1.0`
- same `ts_utc` as parent
- `payload` includes `analyte_slug` (`snake_case` marker derived from **Marker**) and `marker_display_name` (verbatim marker text)

Identifiers remain unique per analytes because `observation_id` / `source_row_id` include `section_slug` and `analyte_slug`.

---

## 5) Value parsing and unit normalization

Input source is `Value` column, e.g.:
- `10.2 x10⁹/L`
- `154 g/L`
- `0.73`
- `>90 (estimated)`
- `~11`

### 5.1 Numeric extraction

Loader extracts first numeric token when present.  
If numeric exists: store in `value_numeric`.  
If numeric absent: store full value in `value_text`.

### 5.2 Unit handling

When a unit suffix exists in `Value`, preserve it in payload as `original_unit`.

Normalize unit text to ASCII for `value_unit`. Minimum required normalization:
- `x10⁹/L` -> `10^9/L`

Also normalize equivalent superscript forms (for robustness):
- `x10¹²/L` -> `10^12/L`
- `x10⁶/L` -> `10^6/L`

If no unit present, `value_unit = null` unless section-specific logic requires a fixed unit (not required for this one-off).

### 5.3 Payload preservation

Each component row payload must preserve:
- `original_unit` (raw unit suffix from `Value`, when present)
- `reference_range` (from `Reference Range`)
- `status_label` (from `Status`)

---

## 6) Quality flags propagation

Row quality flags are:

`frontmatter_quality_flags UNION row_level_quality_flags`

Where row-level flags include parser-detected conditions (example: `non_numeric_value`).

Important behavior:
- frontmatter flags (e.g., `date_unconfirmed`) propagate to parent and every component row

---

## 7) Derived/computed values policy

Do not persist derived metrics as observations:
- NLR
- PLR
- SII

These are scorer-derived from component analytes and must never be cached by the loader.

Practical effect:
- ignore any `## Derived markers` narrative/table content if present

---

## 8) API and returns

```python
def load(panel_md: Path, rawdata_root: Optional[Path] = None) -> tuple[list[Observation], list[Reject]]:
    ...

def raise_if_blood_panel_frontmatter_rejected(panel_md: Path, rejects: list[Reject]) -> None:
    ...
```

Returns:
- `observations`: parent + components that passed validation
- `rejects`: parse/validation failures (file-level, section-level, row-level)

No silent drops: parsing/validation failures become `Reject` entries.

### 8.1 `load_all` integration

Orchestration (`src/ingest/load_all.py`) discovers `rawdata/blood_panels/*.md`. Any `Reject` with `source_row_id == "frontmatter"` triggers `raise_if_blood_panel_frontmatter_rejected` → **`ValueError`**, because missing / invalid YAML is a programmer/data contract violation, not a row-level ingest nuisance.

---

## 9) Why this one-off design

- **Determinism over flexibility:** fixed section names and fixed table shape reduce ambiguity and debugging time.
- **Schema fidelity:** parent/component model matches episodic lab draws in `src/ingest/schema.md`.
- **Auditability:** preserving raw unit/reference/status in payload keeps source traceability without polluting typed columns.
- **Separation of concerns:** loader stores measured components only; scorer owns derived biomarkers.

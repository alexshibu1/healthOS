# Intervention lookup — Spec (v1)

## Purpose

Deterministic **top-3 interventions** from a **flat YAML lookup** keyed by simple trigger expressions over a **snapshot** dict (strings, numbers, booleans). No ML, no projected outcome deltas.

## Input: `snapshot`

Plain `dict` produced by the reporting layer (example keys):

| key | example | notes |
|-----|---------|--------|
| `state` | `"deload"` | readiness / outlook state slug |
| `illness_active` | `true` | from `get_active_flags(as_of_date)["illness"]` or equivalent |
| `sri_score` | `74` | latest or month-mean — caller decides |
| `nlr_value` | `5.37` | last-known |
| `gap_years` | `3.1` | bio-age gap |
| `target_time` | `"23:00"` | optional template filler |

Unknown keys in triggers evaluate false / fail comparison safely.

## File: `src/interventions/lookup.yaml`

Top-level key `rules`: list of objects:

| field | required | type |
|-------|----------|------|
| `trigger` | yes | string — see grammar below |
| `action` | yes | string |
| `skill_ref` | yes | string |
| `effort` | yes | int 1–5 |
| `impact` | yes | `HIGH` \| `MED` \| `LOW` |
| `why_template` | yes | string with `{placeholder}` |

Order in file is **not** ranking order — ranking is by impact then effort at runtime.

### Trigger grammar (v1)

- Clauses joined by ` AND ` (case-insensitive), whitespace-insensitive around operators.
- Each clause is either:
  - **Comparison:** `field op value`
    - `op` ∈ `=`, `<`, `>`, `<=`, `>=`
    - `value` parses as: boolean (`true`/`false`), int, float, or bare word string (no spaces).
  - **Presence / truthy:** bare `field` — satisfied iff `snapshot[field]` is truthy.

Examples:

- `state=deload AND illness_active`
- `sri_score<70`

## Ranking: `rank_interventions(snapshot, *, lookup_path=None)`

1. Load YAML.
2. Filter rules whose trigger matches `snapshot`.
3. Sort matched rules:
   - **Impact** descending: `HIGH` > `MED` > `LOW`
   - Then **effort** descending (higher effort first within same impact).
4. Take **first 3**.
5. Fill `why_template` with `.format(**snapshot)` — caller must ensure placeholders exist or provide defaults (missing keys raise `KeyError`; caller should pass a complete template context).

Output elements:

```json
{
  "action": "...",
  "skill_ref": "§1.2",
  "effort": 4,
  "impact": "HIGH",
  "why": "... filled template ..."
}
```

## Output file

Path: `data/interventions/<YYYY-MM-DD>.json` (calendar date string chosen by caller).

Array of up to 3 objects as above.

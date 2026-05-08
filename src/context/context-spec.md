# src/context/ — Spec

## Status

Spec only. No implementation. Per `CLAUDE.md`: "Spec before code for any component over ~30 lines."

## Overview

Three subsystems:

| module | file(s) | purpose |
|---|---|---|
| Profile | `data/profile.yaml` + `src/context/profile.py` | Static user baseline: age, sex, body, training modality, goal. Read by all scorers. |
| Episodic context | `src/context/episodic.py` | Trigger registry: maps anomaly patterns → question text + decay window. Stores answers in `data/context_answers.csv`. |
| Daily check-in | `src/context/checkin.py` | CLI: prompts 3 sliders + note; appends to `evals/daily-checkins.csv`. Becomes auto-labels for the eval harness. |

All three read their paths from `src/context/config.py` (mirrors the pattern in `src/ingest/config.py`).

---

## Module: `src/context/config.py`

```python
DATA_ROOT:  Path  # absolute path to healthOS/data/
EVALS_ROOT: Path  # absolute path to healthOS/evals/
```

Derived from `__file__` so the project is relocatable.  
No other module hard-codes paths.

---

## Subsystem 1 — Profile

### 1.1 File: `data/profile.yaml`

```yaml
age: 23                       # integer, years
sex: male                     # see §1.3 for valid values
weight_kg: 78.5               # float, kg; static baseline
height_cm: 178.0              # float, cm
training_modality:            # ordered by primary focus
  - running
  - strength
primary_goal: performance     # see §1.3 for valid values
```

All fields are required. Comments are allowed (YAML `#`).  
This file is edited directly by the user; no mutation API exists.

### 1.2 Module: `src/context/profile.py`

```python
@dataclass(frozen=True)
class Profile:
    age:               int
    sex:               str          # validated against enum
    weight_kg:         float
    height_cm:         float
    training_modality: list[str]    # first item = primary modality
    primary_goal:      str          # validated against enum

class ProfileValidationError(ValueError):
    """Raised when profile.yaml is present but invalid."""

def load_profile(data_dir: Optional[Path] = None) -> Profile:
    """
    Load and validate data/profile.yaml.

    Raises
    ------
    FileNotFoundError       if profile.yaml does not exist at data_dir.
    ProfileValidationError  if a required field is missing, wrong type,
                            or an enum field contains an unrecognized value.
    """
```

`frozen=True`: scorers treat profile as immutable; re-compute on each call.

### 1.3 Validation rules

| field | type | constraint | error on failure |
|---|---|---|---|
| `age` | int | > 0, ≤ 120 | `ProfileValidationError` |
| `sex` | str | one of `{male, female, other}` | `ProfileValidationError` |
| `weight_kg` | float | > 0, ≤ 500 | `ProfileValidationError` |
| `height_cm` | float | > 50, ≤ 250 | `ProfileValidationError` |
| `training_modality` | list[str] | non-empty; each item non-empty string | `ProfileValidationError` |
| `primary_goal` | str | one of proposed enum (§1.5) | `ProfileValidationError` |

Type coercion: if YAML produces `int` where `float` is expected (e.g. `weight_kg: 78`), coerce silently.

### 1.4 Consumption contract

Each scorer reads specific profile fields:

| scorer | profile fields consumed | how they modulate |
|---|---|---|
| NLR × HRV readiness | `sex` | sex-specific NLR reference range (if added); currently unused in v1 but reserved |
| SRI | `primary_goal` | if `longevity`, apply stricter threshold (< 70 rather than default) |
| Aerobic decoupling | `training_modality[0]` | running vs cycling have different EF norms |
| Bio-age proxy (future) | `age`, `sex`, `weight_kg`, `height_cm` | all four required as inputs |
| All scorers | `age` | can adjust confidence multipliers for edge ages (e.g., < 18 out of scope) |

No scorer mutates Profile. Profile is fetched once per report run and passed down.

### 1.5 Open questions — profile enums

These are proposed defaults. Confirm before implementation:

**`sex`:** `{male, female, other}` — used for reference range bifurcation in NLR and future hormone metrics. `other` → use population-average ranges.

**`primary_goal`:** `{performance, longevity, general_health, body_recomposition}`. Proposed threshold behavior:
- `performance` → tightest deload thresholds (don't miss training load signal)
- `longevity` → strictest SRI and NLR flags (err on the side of caution)
- `general_health` → spec defaults
- `body_recomposition` → weight trend metrics weighted higher in composite

**`training_modality` vocabulary:** `{running, strength, cycling, swimming, hiit}` are expected values but the field is free-form string list until the scorer that consumes it is implemented. Unknown modalities default to `running` norms in the decoupling scorer with a `unknown_modality_assumed_running` flag.

---

## Subsystem 2 — Episodic context

### 2.1 Separation-of-concerns boundary (explicit)

`episodic.py` owns the registry and the CSV. It does NOT:
- Detect anomalies in data (scorer's job)
- Decide when to prompt the user (report generator's job)
- Poll or schedule anything

When a scorer detects an anomaly with no active answer, it emits a `context_question_pending` quality flag in its output dict. The report generator (or the CLI entry point) sees that flag and calls `record_answer()` interactively. The scorer itself never does I/O.

### 2.2 Trigger registry

Five anomaly patterns. Each entry defines the question to ask and how long the answer stays valid.

| `AnomalyPattern` (enum) | question text | `decay_window_days` | rationale |
|---|---|---|---|
| `elevated_nlr_monocyte_spike` | "Have you had any illness or vaccination in the last 14 days? (describe, or type 'no')" | 14 | Matches post-illness monocyte resolution window in `nlr-hrv-readiness-spec.md §4.3` |
| `sustained_ef_decoupling_drift` | "Has your training environment changed recently — heat, altitude, or humidity? (describe, or type 'no')" | 30 | Environmental adaptations persist for weeks; 30d is a conservative upper bound |
| `single_day_hrv_crash` | "Did you have alcohol, a late or large meal, or an acute stress event last night? (describe, or type 'no')" | 1 | Acute confounders clear within 24 h |
| `sri_breakdown_7d` | "Have you traveled or shifted timezones in the last 7 days? (describe, or type 'no')" | 7 | Travel disruption typically clears ~1 week after return |
| `composite_state_flip_no_metric_movement` | "Any new injury, medication change, or major life stressor? (describe, or type 'no')" | 30 | Medication/injury effects may persist for weeks; 30d is a v1 default — flag as uncertain |

All decay windows are v1 defaults. Revisit after 60 days of live data.

### 2.3 Storage: `data/context_answers.csv`

```
ts_utc,anomaly_pattern,question_id,answer_text,decay_window_days,expires_at_utc
2026-05-08T14:23:00+00:00,elevated_nlr_monocyte_spike,elevated_nlr_monocyte_spike,food poisoning ~3 weeks ago,14,2026-05-22T14:23:00+00:00
```

| column | type | notes |
|---|---|---|
| `ts_utc` | ISO 8601 UTC string | `+00:00` suffix always; when the answer was recorded |
| `anomaly_pattern` | string | `AnomalyPattern` enum value |
| `question_id` | string | stable identifier for the question; equals `anomaly_pattern` in v1 (one question per pattern) |
| `answer_text` | string | free text; newlines replaced with ` ` before writing; empty if user skips |
| `decay_window_days` | int | copied from registry at write time |
| `expires_at_utc` | ISO 8601 UTC string | `ts_utc + timedelta(days=decay_window_days)` |

CSV format: UTF-8, `csv.QUOTE_MINIMAL`, header row required. Create with header if file absent. Never overwrite existing rows; always append.

### 2.4 Module: `src/context/episodic.py`

```python
class AnomalyPattern(str, Enum):
    elevated_nlr_monocyte_spike            = "elevated_nlr_monocyte_spike"
    sustained_ef_decoupling_drift          = "sustained_ef_decoupling_drift"
    single_day_hrv_crash                   = "single_day_hrv_crash"
    sri_breakdown_7d                       = "sri_breakdown_7d"
    composite_state_flip_no_metric_movement = "composite_state_flip_no_metric_movement"

@dataclass(frozen=True)
class TriggerDef:
    question_text:     str
    decay_window_days: int

TRIGGER_REGISTRY: dict[AnomalyPattern, TriggerDef]
# Populated from the table in §2.2. Read-only at runtime.

@dataclass
class ContextAnswer:
    ts_utc:            datetime        # UTC-aware
    anomaly_pattern:   AnomalyPattern
    question_id:       str
    answer_text:       str
    decay_window_days: int
    expires_at_utc:    datetime        # UTC-aware

def record_answer(
    pattern:     AnomalyPattern,
    answer_text: str,
    data_dir:    Optional[Path] = None,
) -> ContextAnswer:
    """
    Write one answer row to data/context_answers.csv.
    Creates the file with header if absent.
    answer_text newlines are replaced with ' ' before writing.
    Returns the constructed ContextAnswer.
    """

def get_active_context(
    as_of_utc: datetime,
    pattern:   Optional[AnomalyPattern] = None,
    data_dir:  Optional[Path] = None,
) -> list[ContextAnswer]:
    """
    Return non-expired answers as of as_of_utc.
    A row is active if expires_at_utc > as_of_utc.
    If pattern is given, filter to that pattern only.
    Returns [] if file absent or no active rows.
    """

def get_question(pattern: AnomalyPattern) -> str:
    """Convenience: return the question text for a pattern."""
```

### 2.5 CLI entry point

```
python -m src.context.episodic [--pattern <name>]
```

- With no arguments: iterates all five patterns, checks `get_active_context(now)`, and prompts only for patterns with no active answer.
- With `--pattern <name>`: prompts for that pattern regardless of active state (allows re-answering).
- Prints the question, reads a line of input, calls `record_answer()`, prints confirmation.
- Empty answer (Enter with no text) is accepted; `answer_text = ""`.

### 2.6 Open questions — episodic

- Decay windows are v1 defaults (§2.2). Should the scorer be able to override the decay window when it calls `record_answer()`? Or is the window always fixed per pattern? Recommend: fixed per pattern for v1; scorer-override can be added later.
- `question_id = anomaly_pattern` assumes one question per pattern forever. If multiple question variants per pattern are ever needed, promote `question_id` to a separate constant with its own text registry.

---

## Subsystem 3 — Daily check-in

### 3.1 Storage: `evals/daily-checkins.csv`

```
date,energy,mood,soreness,note
2026-05-08,4,3,2,legs still sore from Tuesday
```

| column | type | constraint | notes |
|---|---|---|---|
| `date` | `YYYY-MM-DD` | today's local date (system tz) | join key for eval harness |
| `energy` | int | 1–5 | 1=crashed, 2=low, 3=okay, 4=good, 5=peak |
| `mood` | int | 1–5 | 1=rough, 2=meh, 3=neutral, 4=good, 5=great |
| `soreness` | int | 1–5 | 1=none, 2=minor, 3=moderate, 4=significant, 5=severe |
| `note` | string | may be empty | free text; newlines replaced with ` ` before writing |

CSV format: UTF-8, `csv.QUOTE_MINIMAL`, header row required. Create with header if `evals/` or the file is absent.

### 3.2 CLI: `python -m src.context.checkin`

Prompt sequence:

```
Energy  (1=crashed  2=low  3=okay  4=good  5=peak)   → _
Mood    (1=rough    2=meh  3=neutral  4=good  5=great) → _
Soreness (1=none   2=minor  3=moderate  4=significant  5=severe) → _
Note (optional, Enter to skip) → _
```

Rules:
- Input validation: re-prompt (not crash) on non-integer, out-of-range, or empty input for the three sliders.
- `note`: Enter with no text → `""` in CSV; accepted silently.
- Duplicate date: if a row for today already exists, print `"Entry for <date> already exists (energy=X, mood=Y, soreness=Z). Overwrite? [y/N]"` and require explicit `y` to proceed. Default is no-overwrite.
- On overwrite: replace the existing row in-place (rewrite the file), not append.
- On success: print `"Saved: <date>  energy=X  mood=Y  soreness=Z"`.
- No other I/O. No confirmation for new entries (the success print is sufficient).

### 3.3 Consumption contract — eval harness

The eval harness joins check-ins to the daily observation DataFrame on `date`:

```python
checkins["date_parsed"] = pd.to_datetime(checkins["date"]).dt.date
df["date"]              = df["ts_utc"].dt.tz_convert("America/New_York").dt.date
merged = df.merge(checkins, on="date", how="left")
```

A same-day subjective entry is a label: if a scorer emits `tier=green` but check-in has `energy=1`, that divergence is an eval case. The harness surfaces these via a separate `evals/` analysis notebook (future spec). The check-in module does not reference the scorer or schema — it writes rows and exits.

### 3.4 Module: `src/context/checkin.py`

```python
@dataclass
class CheckIn:
    date:     str           # "YYYY-MM-DD"
    energy:   int           # 1–5
    mood:     int           # 1–5
    soreness: int           # 1–5
    note:     str           # may be empty

def write_checkin(
    entry:      CheckIn,
    evals_dir:  Optional[Path] = None,
    overwrite:  bool = False,
) -> None:
    """
    Append or replace entry in evals/daily-checkins.csv.
    If overwrite=False and date already exists, raise DuplicateCheckinError.
    Creates evals/ and the file with header if absent.
    """

class DuplicateCheckinError(ValueError):
    """Raised when a check-in for the date already exists and overwrite=False."""
```

The CLI (`__main__` block) handles interactive prompting, duplicate detection, and overwrite confirmation. `write_checkin` is a pure write function callable by tests without I/O.

---

## Not in scope (all three subsystems)

- Anomaly detection logic: lives in `src/score/`, not here
- Auto-prompting or scheduling: the report generator decides when to call the episodic CLI
- Profile mutation API: edit `data/profile.yaml` directly
- Derived / computed fields stored back to YAML or CSV
- Any UI (v1 is CLI only)
- Multi-user support
- Encryption or access control on the CSV files
- Profile version history (the file is Git-tracked; `git log` is the history)

---

## File layout produced by implementation

```
data/
    profile.yaml
    context_answers.csv      # created on first record_answer() call

evals/
    daily-checkins.csv       # created on first check-in

src/context/
    __init__.py
    config.py
    profile.py
    episodic.py
    checkin.py
```

---

## Cross-references

- `src/ingest/config.py` — pattern for DATA_ROOT / path constants
- `src/score/specs/nlr-hrv-readiness-spec.md §4.3` — monocyte threshold that drives the 14-day decay window
- `skills/health-reasoning.md §2.2` — SRI breakdown pattern that maps to `sri_breakdown_7d`
- `CLAUDE.md` — scoring philosophy, no ML, transparent formulas, spec before code

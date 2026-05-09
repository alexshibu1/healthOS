# Diagnostics — Spec (v1)

## Purpose

When the composite scorer produces an unexpected state or divergence flag, the user
needs a deterministic way to supply confounding-context (illness, travel, alcohol,
heat) without hand-editing `data/context_flags.yaml`.

`src/diagnostics/` owns:
- a YAML registry mapping divergence flags → clarifying questions
- a CSV log of dated answers with expiry
- three query functions that composite.py merges before threshold decisions

It does **not** detect anomalies. It does not auto-prompt. Scorers emit divergence
flags; this module maps flags → questions and questions → flag mutations.

---

## File: `data/diagnostic_questions.yaml`

Top-level key `questions`: list of objects.

### Schema per entry

| field | required | type | notes |
|-------|----------|------|-------|
| `id` | yes | str | snake_case, unique |
| `trigger` | yes | str | see grammar below |
| `question` | yes | str | human-readable prompt |
| `answer_type` | yes | `binary` \| `scale` | |
| `options` | yes | mapping str→str | machine key → display label |
| `shift_potential` | yes | float 0.0–1.0 | expected score delta fraction; used for ranking |
| `decay_days` | yes | int | answer expires after N days |
| `effects` | yes | mapping answer_key→dict | machine-parseable flag mutations per answer |
| `effect_template` | yes | str | human-readable narrative (not parsed) |

**`effects` mapping**: each value is a dict of flag key → bool (or empty dict `{}`
for "no effect"). Keys must align with the merged namespace below (see §composite
merge). A `yes` answer that sets `illness: true` will merge into the flags dict and
shift the composite to `illness-risk` if the lens inputs warrant it.

**"no" answers always map to `{}`** (conservative v1 choice: diagnostic "no" never
overrides a manually-entered illness window from `context_flags.yaml`).

### Trigger grammar (v1 — two forms only)

```
trigger ::= clause (AND clause)*
clause  ::= divergence_clause | confidence_clause
divergence_clause  ::= "divergence=" <flag_name>
confidence_clause  ::= "low_confidence_source=" <source_name>
```

- `divergence=<flag_name>`: fires when `flag_name` appears in the snapshot's
  `divergence_flags` list.
- `low_confidence_source=<source_name>`: fires when
  `snapshot.get(f"source_confidence_{source_name}", 1.0) < 0.7`.
- Multiple clauses joined by ` AND ` (case-insensitive). All must match.
- Unknown flag names and missing confidence keys → clause evaluates `False`.

This grammar is **not** shared with `src/interventions/rank.py`. Separate parsers,
separate semantics.

### Eight v1 questions

```yaml
questions:
  - id: recent_illness_check
    trigger: divergence=autonomic_leading_nlr_elevated
    question: "Did you have any illness symptoms (fever, sore throat, fatigue beyond training) in the past 7 days?"
    answer_type: binary
    options:
      yes_illness: "Yes — illness symptoms present"
      no: "No"
    shift_potential: 0.85
    decay_days: 7
    effects:
      yes_illness: {illness: true}
      no: {}
    effect_template: "Illness flagged: NLR elevation may reflect active immune response rather than training stress."

  - id: travel_timezone_check
    trigger: divergence=circadian_early_warning
    question: "Did you cross more than 2 time zones in the past 5 days?"
    answer_type: binary
    options:
      yes_travel: "Yes — significant time-zone shift"
      no: "No"
    shift_potential: 0.70
    decay_days: 5
    effects:
      yes_travel: {travel: true}
      no: {}
    effect_template: "Travel flagged: circadian disruption expected from time-zone crossing."

  - id: alcohol_night_before
    trigger: divergence=autonomic_stress_no_inflammation
    question: "Did you consume more than 2 standard drinks last night?"
    answer_type: binary
    options:
      yes_alcohol: "Yes"
      no: "No"
    shift_potential: 0.55
    decay_days: 1
    effects:
      yes_alcohol: {alcohol_confound: true}
      no: {}
    effect_template: "Alcohol confound flagged: acute HRV suppression without NLR elevation is consistent with alcohol ingestion."

  - id: heat_or_altitude
    trigger: divergence=peripheral_environmental
    question: "Were you exposed to significant heat (>35°C ambient) or gained >1000m altitude in the past 2 days?"
    answer_type: binary
    options:
      yes_heat: "Yes — heat or altitude exposure"
      no: "No"
    shift_potential: 0.50
    decay_days: 2
    effects:
      yes_heat: {heat_confound: true}
      no: {}
    effect_template: "Heat/altitude confound flagged: peripheral EF drift and HRV suppression can reflect thermal or hypoxic load."

  - id: injury_or_medication
    trigger: divergence=pure_peripheral
    question: "Do you have a local muscle/joint injury, or are you taking NSAIDs, corticosteroids, or antihistamines?"
    answer_type: binary
    options:
      yes_injury: "Yes — injury or medication"
      no: "No"
    shift_potential: 0.50
    decay_days: 7
    effects:
      yes_injury: {injury: true}
      no: {}
    effect_template: "Injury/medication flagged: localized inflammation or pharmacological HRV blunting may explain peripheral EF pattern."

  - id: sleep_environment_change
    trigger: divergence=recovery_debt_ef_decay
    question: "Did you sleep in an unfamiliar environment (hotel, different bed, partner travel) in the past 3 nights?"
    answer_type: binary
    options:
      yes_env: "Yes — unfamiliar sleep environment"
      no: "No"
    shift_potential: 0.40
    decay_days: 3
    effects:
      yes_env: {travel: true}
      no: {}
    effect_template: "Sleep environment change flagged: EF decay plus irregular SRI may reflect first-night effect rather than systemic recovery debt."

  - id: hard_workout_yesterday
    trigger: divergence=convergent_stress
    question: "Was yesterday a maximum-effort session (race, test set, or RPE ≥ 9)?"
    answer_type: binary
    options:
      yes_hard: "Yes — high-effort session"
      no: "No"
    shift_potential: 0.60
    decay_days: 2
    effects:
      yes_hard: {hard_workout_confound: true}
      no: {}
    effect_template: "Hard workout confound flagged: post-maximal-effort HRV crash and transient NLR elevation are expected; not a pathological signal."

  - id: life_stressor
    trigger: divergence=lifestyle_driven_systemic_stress
    question: "Are you under significant non-training psychological stress (exam, work deadline, relationship event) right now?"
    answer_type: binary
    options:
      yes_stress: "Yes — elevated life stress"
      no: "No"
    shift_potential: 0.45
    decay_days: 7
    effects:
      yes_stress: {lifestyle_stress_confound: true}
      no: {}
    effect_template: "Life stressor flagged: psychological stress elevates NLR and suppresses HRV via HPA-axis activation, indistinguishable from training stress in the metric space."
```

---

## File: `data/diagnostic_answers.csv`

Append-only. UTF-8. Header required (written once on first append).

Columns:

| column | type | notes |
|--------|------|-------|
| `question_id` | str | matches `id` in YAML |
| `answer_value` | str | matches an `options` key |
| `ts_utc` | ISO 8601 UTC string | `YYYY-MM-DDTHH:MM:SSZ` |
| `expires_at_utc` | ISO 8601 UTC string | `ts_utc + decay_days` |

No deduplication at write time. `active_diagnostic_flags()` reads all rows and
filters to non-expired ones; the most-recently-logged non-expired answer wins per
`question_id`.

---

## Module: `src/diagnostics/ask.py`

### Function: `get_priority_questions`

```python
def get_priority_questions(
    snapshot: dict[str, Any],
    *,
    questions_path: str | Path | None = None,
    limit: int = 3,
) -> list[dict[str, Any]]:
```

1. Load YAML from `data/diagnostic_questions.yaml` (or `questions_path`).
2. Filter to questions whose trigger matches `snapshot` (using the v1 grammar above).
3. Sort matched questions by `shift_potential` descending.
4. Return first `limit` as list of dicts:
   ```json
   {
     "id": "...",
     "question": "...",
     "options": {...},
     "shift_potential": 0.85,
     "decay_days": 7
   }
   ```

### Function: `log_answer`

```python
def log_answer(
    question_id: str,
    answer_value: str,
    ts: datetime | str,
    *,
    questions_path: str | Path | None = None,
    answers_path: str | Path | None = None,
) -> Path:
```

1. Load YAML. Validate `question_id` exists and `answer_value` is a valid option key.
   Raise `ValueError` for unknown question or answer.
2. Compute `expires_at_utc = ts_utc + timedelta(days=decay_days)`.
3. Append one row to `data/diagnostic_answers.csv`. Write header if file does not exist.
4. Return path to the CSV file.

`ts` accepts a `datetime` (must be timezone-aware UTC) or an ISO 8601 string with `Z`
suffix. Raise `ValueError` for naive datetimes.

### Function: `active_diagnostic_flags`

```python
def active_diagnostic_flags(
    as_of: date | str,
    *,
    questions_path: str | Path | None = None,
    answers_path: str | Path | None = None,
) -> dict[str, Any]:
```

1. Load `data/diagnostic_answers.csv`. Return `{}` if file does not exist.
2. Parse `expires_at_utc`. Discard rows where `expires_at_utc ≤ as_of` (expired).
3. For non-expired rows, load YAML. Find the `effects[answer_value]` dict for each row.
4. Merge effects: when multiple non-expired answers affect the same key, the
   **most-recently-logged** answer wins (sort by `ts_utc` descending, first value wins).
5. Return merged dict. Example: `{"illness": True, "alcohol_confound": True}`.

**Key namespace** (must match `get_active_flags()` for shared categories):

| key | shared with `get_active_flags()`? | set by |
|-----|-----------------------------------|--------|
| `illness` | yes | `recent_illness_check` yes answer |
| `travel` | yes | `travel_timezone_check`, `sleep_environment_change` yes answers |
| `injury` | yes | `injury_or_medication` yes answer |
| `alcohol_confound` | no — diagnostic-only | `alcohol_night_before` yes |
| `heat_confound` | no — diagnostic-only | `heat_or_altitude` yes |
| `hard_workout_confound` | no — diagnostic-only | `hard_workout_yesterday` yes |
| `lifestyle_stress_confound` | no — diagnostic-only | `life_stressor` yes |

---

## Composite.py merge change

### Signature change

```python
def score_day(
    scoring_date: date,
    c1: NlrHrvInput,
    c2: Optional[SriInput] = None,
    c3: Optional[EfInput]  = None,
    context_flags: Optional[dict[str, bool]] = None,
    *,
    diagnostic_flags: Optional[dict[str, Any]] = None,   # ← new
    recent_illness: Optional[bool] = None,
    context_flags_path: Optional[Path] = None,
) -> CompositeResult:
```

### Merge logic

After loading `context_flags` from YAML (if None), merge diagnostic flags:

```python
diagnostic_flags = diagnostic_flags or {}
illness_from_diagnostic = (
    diagnostic_flags.get("illness", False)
    and not context_flags.get("illness", False)
)
merged_flags = {**context_flags, **diagnostic_flags}
illness_flag = bool(merged_flags.get("illness", False))
```

Precedence: diagnostic answers **override** YAML context for shared keys (illness,
travel, injury). This is intentional — diagnostic answer is more temporally precise.

### Reasoning attribution

Pass `illness_from_diagnostic` to `_build_reasoning()`. When
`primary_signal == "context"` and `illness_from_diagnostic is True`, use:

```
"Primary signal: context (illness confirmed via diagnostic answer)."
```

instead of:

```
"Primary signal: context (illness window active)."
```

When both sources set illness (YAML window + diagnostic answer), attribution is
`illness window active` (YAML takes narrative precedence).

### `score_range()` update

`score_range()` calls `active_diagnostic_flags(current)` for each date and passes
the result as `diagnostic_flags` to `score_day()`.

---

## CLI: `python -m src.diagnostics.ask`

```
python -m src.diagnostics.ask --question-id <id> --answer <answer_key>
```

Steps:
1. Validate question ID and answer key against YAML.
2. Write answer to `data/diagnostic_answers.csv` with `ts_utc = datetime.now(UTC)`.
3. **Snapshot rebuild**: load the most recent row from `data/scores/composite.parquet`
   to recover the date last scored. Load the C1 inputs from that row (tier, score,
   confidence, nlr_term, hrv_term from the stored reasoning or a sidecar if available).
   Re-call `score_day()` with `diagnostic_flags=active_diagnostic_flags(today)`.
4. Print before/after diff:
   ```
   Before: state=deload score=58 confidence=0.71
   After:  state=illness-risk score=22 confidence=0.63
   Reasoning delta: Primary signal changed context. Illness confirmed via diagnostic answer.
   ```
5. If parquet does not exist, print "No prior composite score found; answer logged."
   Do not fail.

The rebuild is best-effort and read-only (does not write a new parquet row). It is
for immediate feedback only.

---

## Known v1 Limitations

Four of the eight questions trigger on divergence flags that require SRI or EF
scorers which are not yet implemented:

| question_id | trigger | blocker |
|-------------|---------|---------|
| `travel_timezone_check` | `divergence=circadian_early_warning` | requires SRI scorer |
| `sleep_environment_change` | `divergence=recovery_debt_ef_decay` | requires SRI + EF |
| `heat_or_altitude` | `divergence=peripheral_environmental` | requires EF scorer |
| `injury_or_medication` | `divergence=pure_peripheral` | requires EF scorer |

These questions will return no matches from `get_priority_questions()` until the
relevant scorers ship and populate divergence flags. The YAML entries should still
be present in v1 so they activate automatically when the scorers land.

---

## Test contract (4 tests)

**Test 1 — priority ranking**  
Given a snapshot with `divergence_flags=["autonomic_leading_nlr_elevated",
"convergent_stress"]`, `get_priority_questions()` returns questions sorted by
`shift_potential` descending. The question with highest `shift_potential` is first.

**Test 2 — answer logging with expiry**  
`log_answer("recent_illness_check", "yes_illness", ts)` writes one CSV row with
`expires_at_utc = ts + 7 days`. Re-reading the CSV confirms the row.

**Test 3 — expired flag filtering**  
Write a row with `expires_at_utc` in the past. `active_diagnostic_flags(today)`
returns `{}` — the expired answer has no effect.

**Test 4 — composite state shift after diagnostic answer**  
With a C1 input that would classify as `deload` absent illness context, call
`score_day()` with `diagnostic_flags={"illness": True}`. Confirm the returned
`state == "illness-risk"` and `reasoning` contains `"diagnostic answer"`.

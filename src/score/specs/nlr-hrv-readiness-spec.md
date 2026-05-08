# NLR × HRV Training-Readiness Score — Spec

## Status

Spec only. No implementation. Per `CLAUDE.md`: "Spec before code for any component over ~30 lines." This scorer will exceed that.

## Purpose

A single number that fuses inflammatory state (CBC differential, episodic) with autonomic recovery (HRV, continuous wearable) into a daily training-readiness signal. Designed to catch the post-illness "HRV-leads-NLR" pattern that no single-source consumer app can see. Physiology lives in `skills/health-reasoning.md` §1; this file is the computable contract.

## 1. Formula

```
readiness_score = (NLR / NLR_THRESHOLD) × (HRV_baseline_7d / HRV_current_effective)
```

### Inputs and units

| symbol | source | unit | computed from |
|---|---|---|---|
| `NLR` | most recent CBC differential | unitless ratio | `absolute_neutrophils / absolute_lymphocytes` |
| `NLR_THRESHOLD` | constant | unitless | `3.0` (rationale §3.1) |
| `HRV_baseline_7d` | wearable HRV stream | ms | mean of last 7 valid daily HRV values, **excluding today** |
| `HRV_current_effective` | wearable HRV stream | ms | today's HRV; or 3-day median if anomaly rule (§4.2) triggers |

### Output unit

The score is **unitless** — both terms are dimensionless ratios. A score of `1.0` means NLR sits at the threshold AND today's HRV equals the 7-day baseline. **Higher score = worse readiness.**

### Worked example (using the 2025 panel + hypothetical HRV)

```
NLR                       = 10.2 / 1.9   = 5.37
NLR / 3.0                                = 1.79
HRV_baseline_7d (hyp.)    = 58 ms
HRV_current_effective     = 62 ms
HRV_baseline / HRV_current = 58 / 62      = 0.94

readiness_score = 1.79 × 0.94 = 1.68  → DELOAD
```

This is the exact pattern called out in `skills/health-reasoning.md` §1.2: HRV improving while NLR still elevated. The score lands in `deload` *despite* the wearable trending positive — which is the entire reason the metric exists.

## 2. Tier thresholds

| range | tier | meaning |
|---|---|---|
| `score ≥ 1.5` | **deload** | significantly compromised; cap volume; no high-intensity |
| `1.0 ≤ score < 1.5` | **caution** | cap intensity at Z2; full volume permitted |
| `score < 1.0` | **green** | unrestricted training |

Thresholds are tunable parameters of the spec, not magic constants. The `1.5` boundary corresponds to a doubled multiplicative deviation from neutral in either term (e.g., NLR at 4.5 with HRV neutral, or NLR at 3.0 with HRV 50% below baseline).

## 3. Why each term is weighted as it is

### 3.1 Term 1: `NLR / 3.0`

**Why this term.** NLR is the inflammation × autonomic-stress fusion: neutrophils correlate with sympathetic activity, lymphocytes with parasympathetic (`skills/health-reasoning.md` §1.1, citing Sternal & Kalinkovich, SCIRP). It is the highest-information single number in the CBC for training context.

**Why divided by `3.0`, not `1.65` or `3.6`.**
- `1.65` is the population mean from Forget 2017 (`skills/health-reasoning.md` §1.3). Using it as the denominator would put a healthy person at score `1.0`, but readiness ≠ health. Mean is for screening; threshold is for action.
- `3.6` is the optimal mortality predictor from the 136,347-patient surgical cohort (PMC10030720, `skills/health-reasoning.md` §1.3). Using it would delay deload signals until past the mortality-relevant cutoff. Too late for training adjustment.
- `3.0` is the most-cited "abnormal" cutoff in clinical literature; sits at the conservative end of the 3.0–3.6 range; produces score `1.0` exactly at the boundary of clinical concern. This matches the action threshold for the `caution` tier.

**Why divisive, not subtractive.** A subtractive form (`NLR − 3.0`) would lose its multiplicative interaction with the HRV term and would produce negatives for healthy users. The score is a ratio so two ratio-shaped signals compose intuitively.

### 3.2 Term 2: `HRV_baseline_7d / HRV_current_effective`

**Why this term.** HRV is the parasympathetic readout (`skills/health-reasoning.md` §1.1). Between blood draws, it is the only continuous proxy for inflammatory recovery. Aeschbacher et al. 2017 (`skills/health-reasoning.md` §1.4) shows leukocyte counts inversely associated with HRV; the COVID-19 work in Frontiers in Cardiovascular Medicine 2021 shows HRV indices tracking NLR recovery trajectory.

**Why baseline ÷ current, not current ÷ baseline.**
The score's monotonicity rule is "higher = worse." When HRV drops below baseline, the body is more strained. With baseline in the numerator, that produces a ratio greater than `1.0` — same direction as the NLR term. Both terms agree on direction.

**Why a 7-day rolling baseline.**
Per `CLAUDE.md` scoring philosophy: "Composite readiness = f(HRV trend, RHR trend, sleep debt, strain balance, subjective)." 7 days is the standard rolling window in the HRV4Training / Marco Altini literature for separating signal from day-to-day noise. The skill (`skills/health-reasoning.md` §1.2) describes diagnostic patterns in terms of "HRV improving" vs "HRV declining" — both require a baseline to define direction.

**Why exclude today from the baseline.**
If today is included in its own baseline, an anomalously high or low day partially cancels itself out. Excluding today preserves the contrast that makes the term informative.

### 3.3 Why multiplicative, not additive

`skills/health-reasoning.md` §1.2 treats convergent and divergent signal pairs as having qualitatively different meanings. A multiplicative form:
- Amplifies agreement: `HRV ↓ + NLR ↑` produces a much-greater-than-linear deload signal — correct, because both terms reflect the *same* underlying stressor in two organ systems.
- Dampens single-system divergences without canceling them: `HRV ↑ + NLR ↑` (post-illness) produces a smaller-than-additive but still-large score — correct, because autonomic recovery is real but inflammation is not yet resolved.

An additive form would understate convergent stress and overstate single-system stress. The multiplicative shape encodes the diagnostic logic of the skill directly.

## 4. Edge cases

Each edge case applies a `confidence_multiplier ∈ [0, 1]` to the base confidence and may add a `quality_flag` to the output. Multipliers compound multiplicatively (§4.6).

### 4.1 Stale CBC

| age of most recent CBC | flag | confidence_multiplier |
|---|---|---|
| `≤ 30 days` | none | `1.0` |
| `30 < age ≤ 60 days` | `cbc_aging` | `0.85` |
| `> 60 days` | `cbc_stale` | `0.7` |

Rationale for the two-tier split: 30 days is the typical interval over which acute inflammation resolves and remodels NLR; 60 days is the boundary at which the value is no longer plausibly representative. The schema (`src/ingest/schema.md`) treats the most-recent CBC as anchor regardless of age — the scorer is what enforces the age penalty.

### 4.2 Single-day HRV anomaly

**Detection.** `today_hrv` is anomalous if `|today_hrv − HRV_baseline_7d| > 2 × HRV_stddev_7d` AND `HRV_stddev_7d` is itself plausible (window not contaminated by sparse data).

**Action.** Replace `HRV_current_effective` with the median of the most recent 3 valid daily HRV values (today, today−1, today−2). Add quality flag `hrv_anomaly_smoothed`.

**Why median, not mean.** Median is robust to a single outlier. Mean would let the very anomaly we are trying to suppress shift the result.

**Confidence multiplier:** `0.9`. The smoothing is a deliberate compromise; we should weight it slightly less than a clean point value.

### 4.3 Post-illness window (elevated monocytes within 14 days)

**Trigger.** Within 14 days of any CBC where `Absolute Monocytes > 0.8 × 10⁹/L` (above the upper reference bound). The user's 2025 panel had monocytes at 1.2 — within the trigger range had the panel been recent.

**Action.** Even when NLR has normalized, lymphocyte-to-monocyte recovery lag means the inflammatory system is not yet at baseline. Append warning to `reasoning`: `"inflammatory resolution lag: autonomic recovery may lead blood-marker normalization"`. Add quality flag `post_illness_window`.

**Confidence multiplier:** `0.8`. The score is computable but its interpretation needs the warning; this multiplier ensures the scorer downweights the result even when it lands in `green`.

### 4.4 Missing data

| missing input | scorer behavior |
|---|---|
| no CBC at all | refuse: `tier = "unknown"`, `score = None`, reasoning includes `cbc_required` |
| `< 7 valid HRV days` for baseline | refuse: `tier = "unknown"`, reasoning includes `hrv_baseline_insufficient` |
| today's HRV missing, baseline OK | substitute median of last 3 valid HRV days; flag `hrv_today_imputed`; multiplier `0.85` |
| monocytes value missing on most recent CBC | post-illness rule (§4.3) does not fire; flag `monocytes_unknown`; no multiplier change |

The scorer never invents inputs. It either computes with downweighted confidence or refuses with a typed reason.

### 4.5 Source-confidence weighting (per `src/ingest/schema.md`)

Each input row carries `source_confidence ∈ [0, 1]` from the schema's confidence ladder. The scorer aggregates these as the geometric mean across the inputs actually used:

```
source_confidence_aggregate = geomean(
    [cbc_panel_row.source_confidence] +
    [hrv_row.source_confidence for hrv_row in 7d_window + today]
)
```

For the user's setup (CBC = `1.00`, Amazfit wrist HRV = `0.55`), the aggregate is approximately `geomean([1.00, 0.55, 0.55, …])` — heavily weighted by the lower-confidence wearable. This is correct: a chest-strap-fed version of this score *should* report higher confidence, and this metric is honest about that.

**Why geometric mean, not arithmetic.** Geometric mean is the natural aggregator for ratio-scaled quantities and penalizes any single low-confidence input proportionally to its order of magnitude — a `0.05` row drags the aggregate down decisively, which is the right behavior.

### 4.6 Final confidence formula

```
confidence = source_confidence_aggregate
           × stale_multiplier             # §4.1
           × hrv_anomaly_multiplier       # §4.2 if triggered, else 1.0
           × post_illness_multiplier      # §4.3 if triggered, else 1.0
           × hrv_today_imputed_multiplier # §4.4 if triggered, else 1.0
```

Clamped to `[0, 1]`. When `score is None`, `confidence = 0.0`.

## 5. How this differs from WHOOP recovery and Bevel readiness

| dimension | WHOOP recovery | Bevel readiness | this score |
|---|---|---|---|
| Inputs | HRV + RHR + sleep, single wearable | blood markers, static context | CBC differential × continuous wearable HRV |
| CBC ingested | no | yes | yes |
| HRV ingested | yes (continuous) | no | yes (continuous) |
| Update cadence | daily | per blood draw (months apart) | daily, with last-known CBC anchor |
| Detects "HRV ↑ + NLR ↑" post-illness pattern | no — would say "high recovery" | no — blood data is stale and decoupled from daily wearable | **yes — this score's reason for existing** |
| Mechanism cited | proprietary | per-marker reference ranges | `skills/health-reasoning.md` §1.1 (autonomic ↔ immune linkage) |
| Formula transparency | closed | per-marker, no fusion | open, in this file |
| Confidence reporting | none | none | per-output `confidence ∈ [0, 1]` |
| Episodic-vs-stream join | n/a | n/a | last-known-anchor with staleness penalty (§4.1) |

The novel claim of this score: the divergence between an episodic blood anchor and a continuous wearable trend is itself the diagnostic signal. `skills/health-reasoning.md` §0 ("two-signal divergence > either signal alone") is what this score operationalizes.

## 6. What this score does NOT capture

The output is one number; many things are deliberately excluded.

- **Sleep regularity.** Separate metric — see `src/score/specs/sri-spec.md`, `skills/health-reasoning.md` §2.
- **Aerobic decoupling / running economy.** Separate metric — see `src/score/specs/aerobic-decoupling-spec.md`, `skills/health-reasoning.md` §3.
- **Acute musculoskeletal load.** Lift volume (JeFit) is not an input. A heavy session can transiently elevate NLR (Kaniganti 2022, `skills/health-reasoning.md` §1.5 pitfall) — interpret a draw within ~24 h of a hard session with explicit caution; the scorer cannot detect this without an external workout-log cross-reference (a future enhancement).
- **Psychological stress not reflected in HRV.** HRV is the proxy; stress not expressed in autonomics is invisible to this score.
- **Acute infections that have not yet shifted CBC.** Early infection days may show HRV-side changes before the next blood draw.
- **Hormonal / menstrual cycle effects on HRV.** Significant in literature; not modeled here. Future spec may add a cycle-phase adjustment.
- **Medications.** Corticosteroids, immunosuppressants, beta-blockers, SSRIs, stimulants — out of scope; should be flagged at the user-profile level, not in this scorer.
- **Hydration / caffeine / alcohol confounders on HRV.** Treated as noise the 7-day baseline averages out; not modeled explicitly.
- **Sub-clinical NLR `< 0.7`.** The score assumes elevated NLR means stress. NLR `< 0.7` also suggests pathology (`skills/health-reasoning.md` §1.5 pitfall) but does not produce a "deload" signal here. Known limitation; a future spec may add a low-NLR branch.
- **Genetic / individual normal-range variation.** The `3.0` threshold is population-derived. A user with a stable personal baseline at `0.9` arguably needs a different denominator. Not implemented; logged as a known limitation.

## 7. Output schema

Strict contract; the scorer returns exactly this shape.

```python
{
    "score": float | None,              # unitless; None when refused (§4.4)
    "tier": Literal["deload", "caution", "green", "unknown"],
    "confidence": float,                # ∈ [0.0, 1.0]; 0.0 when score is None
    "reasoning": str                    # human-readable, deterministically templated
}
```

### Field contracts

- `score` — `None` if any required input is missing per §4.4; otherwise the value of §1.
- `tier` — `"unknown"` iff `score is None`. Otherwise mapped from §2 thresholds.
- `confidence` — computed per §4.6. `0.0` when `score is None`.
- `reasoning` — deterministic template. Required fragments, joined in order:
  1. **Computation:** `"Score 1.68 = (5.37/3.0) × (58/62)."`
  2. **Tier:** `"Tier: deload."`
  3. **Dominant driver:** `"NLR elevated: abs neutrophils 10.2, abs lymphocytes 1.9."` *or* `"HRV depressed: today 50 ms vs 7d baseline 58 ms."`
  4. **Active flags from §4 in plain language:** `"CBC age: 47d (aging multiplier 0.85). HRV input: Amazfit wrist (per-row confidence 0.55)."`
  5. **Warnings from §4.2 / §4.3 when triggered.**

The `reasoning` string MUST be reproducible — same inputs → same string. No model-generated prose. This makes day-over-day diffs meaningful and lets an eval set assert string equality.

## 8. Test cases the implementation must pass

Falsifiability checklist (per `skills/health-reasoning.md` §5.2). A future scorer that fails any of these is wrong, regardless of how well-coded.

1. **Healthy baseline.** `NLR = 1.65`, `HRV_current = baseline` → `score ≈ 0.55`, `tier = green`.
2. **2025 panel + matched HRV.** `NLR = 5.37`, `HRV_current ≈ baseline` → `score ≈ 1.79`, `tier = deload` regardless of HRV term.
3. **Post-illness divergence.** `NLR = 5.37`, `HRV_current > baseline` → score still `≥ 1.5` (multiplicative dampening, not cancellation). The skill §1.2 pattern must produce a deload.
4. **HRV anomaly suppression.** A single day at `−3σ` from baseline must NOT flip tier from `green` to `deload` alone; the 3-day median replaces the point value.
5. **Stale CBC compounding.** Same NLR, age `70d` → identical score, `confidence × 0.7`.
6. **Insufficient HRV baseline.** Only 4 valid HRV days → `tier = unknown`, `score = None`, reasoning includes `hrv_baseline_insufficient`.
7. **Source-confidence honesty.** Identical inputs from chest-strap (`1.00`) vs Amazfit wrist (`0.55`) produce identical scores but different confidences — never identical confidences.

## 9. Open questions (must resolve before code)

1. **HRV metric choice.** RMSSD vs SDNN vs lnRMSSD. Skill cites both SDNN- and RMSSD-derived work. Recommend RMSSD (vagal-tone proxy, dominant in the athletic literature). Loader must record which metric the wearable actually provides.
2. **HRV anomaly test parameters.** ±2σ over a 7-day window is a first cut; needs validation against actual HRV variability. Fall back to median absolute deviation if the window itself is contaminated.
3. **Threshold tuning (`1.5` / `1.0`).** Provisional. Revisit after the first 30 days of paired data and any divergence from felt-readiness in `evals/`.
4. **NLR low-end branch.** Add a `< 0.7` arm or defer? Currently flagged as a §6 known limitation.
5. **Cycle-phase modulation.** Defer until enough data exists to fit; not in v1.

## 10. Cross-references

- `CLAUDE.md` — guardrails: transparent weighted formulas, spec before code, do not bullshit.
- `skills/health-reasoning.md` §1 — physiology; supplies all citations used in §3.
- `src/ingest/schema.md` — `source_confidence` ladder, episodic-anchor join contract, `quality_flags` vocabulary.
- `rawdata/blood_panels/2025_food_poisoning_panel.md` — reference panel for the §1 worked example.
- `src/score/specs/sri-spec.md`, `src/score/specs/aerobic-decoupling-spec.md` — sibling metrics; this score does not subsume them.

# Health Reasoning Skill

## When to load

Load when reasoning about scoring formulas, interpreting trends,
ranking interventions, or evaluating divergences between predicted
and felt scores.

## What this file is not

Not a spec — computable contracts live in `src/score/specs/`. Not
medical advice. Not project orientation — that is `CLAUDE.md`.

## Section 0 — Reasoning principles

- Mechanism before formula. If you can't name a physiological pathway, you don't have a metric.
- Two-signal divergence > either signal alone. The most informative state is when two readouts disagree.
- Episodic data (blood) anchors; time-series data (wearables) tracks recovery between anchors.
- Flag uncertainty explicitly. Per `CLAUDE.md`: "When unsure about a physiological claim, flag it. Do not bullshit."
- Citations are load-bearing. Numbers come from cited studies, never from paraphrased ranges.
- User-specific values stay in scoring code, not in this file. This file is the general physiology layer.

## Section 1: Inflammatory + autonomic fusion (NLR × HRV)

### 1.1 Mechanism
Neutrophils and lymphocytes are differentially regulated by the autonomic nervous system: neutrophil count correlates with sympathetic activity, lymphocyte count with parasympathetic activity (Sternal & Kalinkovich, SCIRP). Because HRV is a parasympathetic readout, an HRV trend is a non-invasive proxy for the lymphocyte-side recovery between blood draws. NLR fuses both arms (sympathetic numerator, parasympathetic denominator), so it behaves as a single-number stress/recovery signal that wearable HRV can shadow. Supporting linkage: Aeschbacher et al. 2017 (large young-adult cohort, ScienceDirect) — leukocyte counts and subtypes were inversely associated with HRV and positively associated with HR. Frontiers in Cardiovascular Medicine 2021 (COVID-19) — SDNN, SDANN and LF/HF tracked NLR and recovery; severe patients without improving HRV took longer to clear illness.

### 1.2 Diagnostic patterns
- **HRV improving + NLR still elevated** → autonomic recovery preceding inflammatory resolution. Common post-illness. Premature reload risk: the wearable says "ready", the blood says "still fighting".
- **HRV declining + NLR elevated** → active stressor; both systems strained. Convergent stress signal.
- **HRV stable + NLR normalizing** → full recovery trajectory.
- **HRV declining + NLR normal** → autonomic stressor without measurable inflammation (sleep debt, psychological stress, overreaching) — an early-warning state.

### 1.3 Reference thresholds
- Population normal NLR mean 1.65, 95% range 0.78–3.53 (Forget et al., 2017, ~413 working adults aged 21–66).
- Healthy individuals typically sit at NLR 1–2; >3 or <0.7 suggests pathology.
- Clinical "abnormal" cutoff most commonly cited at 3.0–3.6. The 3.6 value was identified as the optimal mortality predictor in a 136,347-patient surgical cohort (PMC10030720).

### 1.4 Evidence

**Mechanism layer (autonomic ↔ immune linkage)**
- Sternal & Kalinkovich (SCIRP review) — neutrophil ↔ sympathetic, lymphocyte ↔ parasympathetic correlations in pre/post-exercise athletes.
- Aeschbacher et al. 2017 (ScienceDirect) — leukocyte ↔ HRV inverse association in a large young-adult cohort.
- Frontiers in Cardiovascular Medicine 2021 — HRV indices (SDNN, SDANN, LF/HF) tracked NLR trajectory in COVID-19 recovery.

**Applied layer (exercise physiology)**
- Lee, Sennels & Berg, Eur J Appl Physiol 2021 (PMC8192383) — synthesizes NLR / PLR / SII as exercise-programming signals reflecting strain, recovery, overtraining, and infection risk.
- Walsh / Gleeson lab work (PMC3963240); Nieman 1998 — post-exercise neutrophils continue rising and lymphocytes continue falling during recovery; N/L ratio is "a good measure of exercise stress and subsequent recovery."
- Bury, Marechal et al. (Belgian longitudinal study, 4 female endurance runners; World Athletics summary) — runners performing better in a 3,000 m time trial had lower L/N (i.e., lower NLR) pre-trial; poorer performers had higher NLR. Direct performance correlation.
- Kaniganti et al. 2022 (Kheljournal) — NLR rose acutely from 1.46 to 2.15 after a single high-intensity weightlifting session; described as "an incipient marker to monitor inflammation, overtraining, and recovery in athletes."

### 1.5 Pitfalls
- Zepp/Amazfit logs HRV at wake, not during sleep — less reliable than chest strap (per `CLAUDE.md`); weight HRV input lower in the composite.
- CBC differential is episodic, not time-series. Do not interpolate; flag staleness when the most recent draw is old (see `nlr-hrv-readiness-spec.md` 60-day stale rule).
- Acute lifting transiently elevates NLR (Kaniganti 2022, 1.46 → 2.15). Interpret a draw within ~24 h of a hard session with caution.
- NLR < 0.7 is also abnormal; the formula assumes elevated, not suppressed, ratios.

### 1.6 Spec link
`src/score/specs/nlr-hrv-readiness-spec.md`.

## Section 2: Sleep regularity (SRI)

### 2.1 Mechanism
SRI captures day-to-day *consistency* of the sleep/wake state at matched clock times — not duration, not quality. Irregular timing displaces the circadian phase. Phillips et al., Sci Rep 2017 (n=61 Harvard undergrads) found the most-irregular sleepers had dim-light melatonin onset (DLMO) 2.5 hours later, lower daytime light exposure, and lower GPA — circadian phase delay producing measurable downstream cognitive and behavioral cost. Duration and regularity are independent axes; you can sleep 8 h every night and still have a low SRI.

### 2.2 Diagnostic patterns
- **Low SRI + normal duration** → pure circadian-timing deficit. Cognitive and metabolic risk without obvious "bad sleep."
- **Low SRI + low duration** → compounded deficit; convergent risk.
- **Low SRI localized to weekend / free days** → social-jetlag pattern; behavior-driven, behavior-fixable.
- **Stable SRI suddenly dropping** → schedule perturbation (travel, work shift, life event) rather than chronic lifestyle. Treat as acute, not chronic.

### 2.3 Reference thresholds
- Range 0 (random) to 100 (perfect regularity) (Phillips et al., Sci Rep 2017).
- SRI < 70 was specifically associated with elevated all-cause mortality risk in Windred et al., Sleep 2024 (UK Biobank, n=60,977).

### 2.4 Evidence

**Mechanism layer**
- Phillips et al., Sci Rep 2017 — defined the canonical SRI formula; showed irregular sleepers had DLMO delayed 2.5 h, lower daytime light exposure, and lower GPA in the original Harvard undergrad cohort (n=61).
- National Sleep Foundation 2023 consensus statement — sleep-onset SD is the most-used legacy regularity metric and is monotonically related to SRI; useful as a proxy when full epoch-level data is unavailable.

**Applied layer (outcomes)**
- Windred et al., Sleep 2024 (UK Biobank, n=60,977) — higher SRI associated with 20–48% lower all-cause mortality, 16–39% lower cancer mortality, and 22–57% lower cardiometabolic mortality. SRI was a stronger predictor of mortality than sleep duration.
- Lunsford-Avery et al., Sci Rep 2018 (MESA cohort) — higher SRI correlated with lower 10-year cardiovascular disease risk, lower fasting glucose, lower HbA1c, and lower obesity rates.
- Zhang et al., Sleep Health 2023 (consensus statement, 47 cross-sectional studies) — higher SD of sleep onset / midpoint correlated with metabolic syndrome, T2D risk, adiposity, and poorer glycemic control.
- He et al. 2020 (PMC7228054) — in adolescents, greater night-to-night variability in sleep duration and bedtime was associated with higher trunk fat percentage and insulin levels, *independent* of average sleep duration.

### 2.5 Pitfalls
- Whoop "Sleep Consistency" and Oura "regularity" are spirit-similar but proprietary or qualitative. Do not equate them with canonical Phillips SRI.
- SRI requires minute-level (or finer) sleep/wake state data over a multi-day window. Without it, fall back to onset SD per NSF 2023, but label the result as a proxy.
- Timezone shifts within the window must be normalized before scoring, otherwise legitimate consistency reads as irregularity (see `sri-spec.md` edge cases).
- Schedule-constrained low SRI (shift work, parents of newborns) is structurally different from behavior-driven low SRI; the score is the same, the intervention is not.

### 2.6 Spec link
`src/score/specs/sri-spec.md`.

## Section 3: Aerobic decoupling (Pa:HR)

### 3.1 Mechanism
At a steady aerobic effort, heart rate "drifts" upward over time as stroke volume falls, driven by plasma volume loss, thermoregulatory demand, and rising core temperature. González-Alonso & Coyle, J Appl Physiol 1992 (PMID 1447078) experimentally established this: graded dehydration produced linear HR increases (r=0.99, p<0.01) and stroke-volume decreases; even 1.1% body-mass loss measurably affected HR. The pace-to-HR ratio (efficiency factor, EF) therefore integrates cardiovascular drift, ventilatory cost, hydration, and core-temperature stability into one number. A within-session decoupling captures *how durable* that integration is at a given effort; an across-day EF trend captures whether the underlying aerobic system is improving, holding, or fraying (Saunders et al., Sports Med 2004; Foster et al., PMC4555089 — running-economy review).

### 3.2 Diagnostic patterns
- **EF ↓ + HRV ↓** → central fatigue or illness. Both the engine and the autonomic regulator are degraded.
- **EF ↓ + HRV ↑** → peripheral / environmental cause: dehydration, heat, leg-muscle stress. Autonomic state is fine; the periphery is the bottleneck.
- **High within-session decoupling on otherwise comparable Z2 effort** → acute stressor that day (heat, sleep debt, illness onset).
- **EF z-score < −1.0 sustained 5+ days** → accumulating fatigue, illness onset, or chronic dehydration; not a one-day anomaly.
- **EF improving over weeks at matched HR** → adaptation; the "window into aerobic fitness" (Friel).

### 3.3 Reference thresholds
- Within-session Pa:HR % bands (Friel / TrainingPeaks):
  - < 5% → adapted aerobic base
  - 5–10% → moderate (above aerobic threshold, or insufficient base)
  - ≥ 10% → aerobic system inadequate at that intensity, or external stressor (heat, dehydration, illness)
- Trend layer: sustained EF z-score < −1.0 over 5 days as a fatigue / illness flag.

### 3.4 Evidence

**Mechanism layer**
- González-Alonso & Coyle 1992 (PMID 1447078) — direct experimental establishment of cardiovascular drift; HR rose linearly (r=0.99, p<0.01) with graded dehydration; 1.1% body-mass loss already measurable.
- Saunders et al., Sports Med 2004; Foster et al. (PMC4555089) running-economy review — running economy is sensitive to HR, ventilation, and core temperature; pace/HR is therefore a multifactorial integrative biomarker, not a simple HR metric.

**Applied layer**
- Friel / TrainingPeaks methodology (help-center docs) — EF improvement over weeks as a "window into aerobic fitness"; declining EF on the same route / effort indicates fatigue, illness, sleep debt, or dehydration.
- Strzelczyk et al. 2025 (PMC12271085) — ML models built on cardiovascular-drift features in 20 trained cyclists detected aerobic-fitness adaptation across 5 monthly tests; supports the *trend layer* of the metric, not just single-session bands.

### 3.5 Pitfalls
- Strava HR zones are often miscalibrated (per `CLAUDE.md`); trust pace/power over HR, and treat raw zone labels with suspicion.
- Route non-comparability is the single largest confound. Wind, terrain, surface, and elevation profile all bend EF independent of fitness — exclude these sessions from the trend (see `aerobic-decoupling-spec.md`).
- Heat and dehydration mimic detraining. Without an environmental confound flag, a single hot day can read as a fitness regression.
- Decoupling is undefined for short or intermittent efforts. Recommend ≥30 min steady aerobic; otherwise, session-level only.
- Garmin "Training Effect" and Whoop "Strain" are *not* EF; do not treat them as substitutes.

### 3.6 Spec link
`src/score/specs/aerobic-decoupling-spec.md`.

## Section 4: How these three integrate

The three metrics view the body through different lenses:

- **NLR × HRV** — inflammation + autonomic state (systemic).
- **SRI** — circadian alignment (chronobiological).
- **Pa:HR** — exercise-economy drift (peripheral + thermoregulatory).

**Convergence rule.** All three degrading simultaneously → high-confidence reload-risk signal. The diagnostic value comes not from any one, but from agreement.

**Divergence is where the platform's signal lives.** When two systems disagree, the disagreement itself is the insight.

### 4.1 Divergence matrix

| metric_A_state | metric_B_state | interpretation | action_implication | confidence_modifier |
|---|---|---|---|---|
| HRV ↑ (improving) | NLR ↑ (still elevated) | Autonomic recovery preceding inflammatory resolution. Common post-illness window. | Hold reload until NLR trends down; the wearable is a leading, not coincident, indicator here. | ×0.7 (downweight HRV optimism while CBC anchor unresolved) |
| HRV ↓ | NLR ↑ | Active stressor; both systems strained. Convergent stress signal. | Treat as deload state. | ×1.0 (no divergence) |
| HRV stable | NLR ↓ (normalizing) | Full recovery trajectory. | Resume progression; monitor next CBC for confirmation. | ×1.0 |
| HRV ↓ | NLR normal | Autonomic stressor without measurable inflammation (sleep debt, psychological stress, overreaching). | Investigate non-inflammatory stressors; do not chase NLR. | ×0.8 (fewer corroborating signals) |
| NLR×HRV degraded | SRI low | Lifestyle-driven systemic stress (circadian disruption + inflammatory load). | Intervention rank: circadian regularization first; high expected leverage. | ×1.1 (two independent lenses agree) |
| NLR×HRV degraded | SRI high | Acute, non-lifestyle stressor (illness, injury, environmental). | Search for a discrete cause; do not blame routine. | ×0.9 (fewer modifiable levers) |
| SRI low | NLR×HRV fine | Early-warning lead indicator: circadian disruption present but not yet propagated to inflammation / autonomics. | Pre-emptive intervention before the systemic signal degrades. | ×0.8 (single-lens; act with humility) |
| Pa:HR drift up | HRV ↓ | Central fatigue or illness (engine + regulator both degraded). | Deload; investigate illness onset. | ×1.0 |
| Pa:HR drift up | HRV ↑ | Peripheral / environmental: dehydration, heat, leg stress. Autonomic state is fine. | Hydrate, cool, manage environment; do not deload reflexively. | ×0.9 (single-system finding) |
| Pa:HR drift up | SRI low | Recovery debt expressing as exercise-economy decay. | Treat sleep regularity as upstream cause; expect EF to lag SRI improvement. | ×1.0 |
| Pa:HR drift up | NLR×HRV fine | Pure peripheral / environmental cause. | Confound-check (heat, route, hydration); do not treat as systemic. | ×0.7 on training-state inference |
| All three degraded | — | Convergent reload-risk across systemic, chronobiological, and peripheral lenses. | Hard deload. | ×1.2 (highest-confidence state) |

**Confidence weighting rule.** When signals disagree, downweight the score whose *anchor* is older or thinner — a stale CBC weakens the NLR×HRV side; insufficient HRV baseline weakens HRV-based interpretations. Cross-reference §1.2, §2.2, §3.2 for within-section divergence patterns; the matrix above only captures cross-section pairs.

## Section 5: Principles for deriving new fused metrics

This skill exists to support not just the three flagship metrics, but the *style of reasoning* that lets the agent (and you) propose new ones. The platform's wedge is fusing data sources no single consumer device sees.

### 5.1 Fusion heuristics (use these to propose)
- Combine signals from non-overlapping data sources (episodic blood × continuous wearable; circadian timing × workout drift; lift volume × autonomic recovery).
- Prefer fusions where the two signals have *different latencies* — anchors (slow) vs. trackers (fast). Disagreements between a slow and a fast signal are the highest-yield divergence patterns.
- Prefer fusions where one signal is *modifiable today* (sleep timing, hydration) and the other is *measurable tomorrow* (next blood draw, weekly EF trend). This produces actionable feedback loops.

### 5.2 Required gates (a candidate metric must pass all of these before it ships)
- **Mechanism gate** — at least one peer-reviewed mechanistic link between the two signals, not statistical correlation alone.
- **Falsifiability gate** — every metric must come with a divergence pattern that would make it *wrong*. If you can't describe what would falsify it, you don't have a metric.
- **Threshold-source gate** — bands must come from cited literature or be explicitly labeled as provisional. Never invent thresholds.
- **Spec gate** — once the skill section is drafted, a corresponding spec in `src/score/specs/` must be written before code (per `CLAUDE.md`: "spec before code").

### 5.3 Candidate metric template
1. **Name and one-line claim.**
2. **Mechanism** — the physiological pathway in 2–4 lines.
3. **Inputs** — which data sources, at which cadences.
4. **Formula** — algebraic, written before any code.
5. **Evidence (mechanism layer + applied layer)** — cited, not paraphrased.
6. **Diagnostic patterns** — including the divergence pattern that would make this metric wrong.
7. **Pitfalls** — confounds, source quirks, scope limits.
8. **Spec stub** — pointer to the future `src/score/specs/<name>-spec.md`.

### 5.4 Anti-patterns (refuse to ship a metric that does any of these)
- **Fishing in correlation matrices** — finding two signals that happen to track each other and naming the result a metric. No mechanism, no metric.
- **Same-source fusion** — combining two derivatives of the same wearable stream and presenting it as multi-source. The platform's value is *cross-source* fusion.
- **Rebrand of an existing vendor score** — repackaging Whoop strain, Oura readiness, or Garmin Body Battery under a new name. If the formula isn't novel, the metric isn't novel.
- **Reverse-engineering a metric to fit a felt outcome** — choosing the formula or thresholds because they retroactively explain a day you remember as "bad." This is the most dangerous failure mode: it produces a metric that confirms beliefs instead of testing them. By construction, a metric tuned against memory rather than literature fails the falsifiability gate — there is no pattern that could make it wrong, because it was built to be right about the past.

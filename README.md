# healthOS

**Personal health intelligence layer.** Ingests messy multi-source health data (Zepp/Amazfit, JeFit, Strava, blood panels) and produces monthly reports with a composite readiness score, bio-age proxy, and ranked top-3 interventions.

## The Wedge

No consumer device sees all your data. healthOS does—and derives more insights because of it.

By fusing data sources that no consumer app combines, healthOS turns fragmented wearables, workouts, and blood labs into a unified physiological picture:

- **CBC differential** (NLR, monocytes) — no wearable ingests this
- **Wearable HRV** — every wearable has it; none ties it to inflammatory markers
- **Workout pace/HR decoupling** — TrainingPeaks computes this but it's coach-facing
- **Sleep regularity** — Phillips SRI is peer-reviewed; no consumer app implements it

## Three Flagship Metrics

1. **NLR × HRV Training-Readiness Score** — Inflammatory markers (CBC) meet autonomic state (HRV)
2. **Sleep Regularity Index (SRI)** — Phillips formula applied to personal sleep/wake timestamps
3. **Aerobic Decoupling Trend** — Pace:HR efficiency Z-score over time, with cross-interpretation against HRV

See the detailed specs in `src/score/specs/` for full formulas and implementation rules.

## Data Sources & Quirks

| Source | What | Quirk | Weighting |
|--------|------|-------|-----------|
| Zepp/Amazfit | HRV, RHR, sleep state | HRV logged at wake, not during sleep. Less reliable than chest strap. | Lower |
| JeFit | Lift volume, 1RM estimates | Strain proxy | Standard |
| Strava | Cardio sessions, pace, HR | HR zones often miscalibrated — trust pace/power over HR. | Standard |
| Blood panels | CBC differential, markers | Episodic, not time-series. Context, not signal. | Context-only |

## Scoring Philosophy

- **Transparent weighted formulas over ML.** Every number is defendable.
- **Composite readiness** = `f(NLR, HRV trend, RHR trend, sleep regularity, strain balance, subjective)`
- **Bio-age proxy is illustrative**, not medical guidance. We're honest about uncertainty.
- **Single headline number** with drill-downs underneath for interpretation.

## Architecture

```
src/
├── ingest/           Per-source CSV loaders, normalized to common schema
├── score/            Composite scoring, bio-age proxy
│   └── specs/        Detailed formulas for readiness, SRI, aerobic decoupling
├── trends/           Month-over-month analysis, statistical significance
├── interventions/    Ranker, evidence-tagged recommendations
└── report/           Monthly report generator

skills/              Domain knowledge: health reasoning, formulas, assumptions
data/                Local data storage (CSV exports, caches)
.claude/             Custom instructions and context

CLAUDE.md            Development guidelines, guardrails
```

## Implementation Specs

Three detailed specification documents define the scoring engine:

### 1. **NLR × HRV Training-Readiness Score** (`nlr-hrv-readiness-spec.md`)
- Formula: `readiness_score = (NLR / 3.0) × (baseline_HRV / current_HRV)`
- Thresholds: `>= 1.5` (deload), `1.0–1.5` (caution), `< 1.0` (green)
- Handles stale CBC data, HRV anomalies, post-illness lag detection
- Output includes confidence scores and flags

### 2. **Sleep Regularity Index (SRI)** (`sri-spec.md`)
- Canonical Phillips formula: measures day-to-day sleep/wake consistency
- Rolling 14-day window, 1-minute epoch resolution
- Thresholds: `< 70` (irregular), `70–80` (moderate), `>= 80` (high)
- Handles timezone shifts, missing epochs, shift-work patterns
- Backup proxy: sleep onset standard deviation

### 3. **Aerobic Decoupling Trend** (`aerobic-decoupling-spec.md`)
- Per-session: `decoupling_pct = ((EF_first_half - EF_second_half) / EF_first_half) × 100`
- Trend layer: Z-score of efficiency factor over 30-day rolling window
- Cross-signals with HRV to distinguish central vs peripheral fatigue
- Handles heat/dehydration, illness, and route non-comparability confounders
- Requires >= 30-minute steady aerobic sessions

## Guardrails

- 🚫 **No synthetic data.** Ever.
- 📊 **Statistical methods first.** ML only if explicitly requested.
- 📐 **Formula before code.** Full spec for any component >30 lines before implementation.
- 🚩 **Flag uncertainty.** When unsure about physiological claims, flag explicitly.
- 📋 **Spec before code.** All major scoring components have detailed specs.

## Getting Started

### Requirements
- Python 3.9+
- Pandas, NumPy, SciPy
- Per-source export files (see `src/ingest/` for expected formats)

### Basic Usage

```python
from src.ingest import load_zepp, load_jfit, load_strava, load_blood
from src.score import composite_readiness

# Load data
hrv_data = load_zepp('zepp_export.csv')
strength = load_jfit('jfit_export.csv')
cardio = load_strava('strava_export.csv')
labs = load_blood('labs.csv')

# Compute readiness
score = composite_readiness(hrv_data, strength, cardio, labs)
print(f"Readiness: {score:.1f}/100")
print(f"Zone: {score.zone}")
```

### Monthly Report

```python
from src.report import generate_monthly_report

report = generate_monthly_report(
    month='2026-04',
    hrv_data=hrv_data,
    strength=strength,
    cardio=cardio,
    labs=labs
)
report.to_html('month_report.html')
```

## Domain Knowledge

See **`skills/health-reasoning.md`** for the physiological foundations:

- **Section 1:** Inflammatory + autonomic fusion (NLR ↔ HRV mechanism)
  - Neutrophils ↔ sympathetic, lymphocytes ↔ parasympathetic
  - Diagnostic patterns for recovery stages
  - Literature: Forget 2017, Lee/Sennels/Berg 2021, Walsh/Gleeson

- **Section 2:** Sleep regularity (Phillips formula, mortality data)
  - Why SRI > sleep duration as a predictor
  - References: Phillips 2017, Windred 2024, Zhang 2023

- **Section 3:** Aerobic decoupling
  - González-Alonso & Coyle mechanism
  - Central vs peripheral fatigue distinction
  - Friel methodology, EF + HRV cross-interpretation

- **Section 4:** Integration
  - Convergent signals (all three degrading) = strong reload-risk signal
  - Divergent signals = diagnostic insights

## Validation & Testing

- `evals/` — Labeled days, divergence analysis between computed and felt scores
- Statistical significance testing for month-over-month changes
- Confounded signal detection (heat, illness, route changes)

## Data Privacy

- **Local computation.** No cloud sync or external processing.
- **Your data, your rules.** Keep everything in your own environment.
- CSV exports stored in `data/` directory

## Limitations & Caveats

- **Blood panels are episodic**, not continuous. They provide context, not real-time signals.
- **Zepp HRV is less reliable** than chest strap. Weighted accordingly in composite.
- **Bio-age is illustrative**, not medical guidance. Consult healthcare providers.
- **Strava HR zones are often miscalibrated.** We prefer pace/power metrics.
- **Sleep regularity ≠ sleep quality.** SRI captures timing consistency, not depth or restoration.
- **Aerobic decoupling is influenced by environment.** Heat, hydration, and illness are confounders.

## Development

See **`CLAUDE.md`** for development guidelines:
- Guardrails on synthetic data, ML use, formula-first approach
- Spec-before-code policy for major components
- Physiological-claim flagging requirements

## Contributing

This is a personal health project. Thoughtful improvements welcome:

- Statistical improvements to scoring algorithms
- New data source integrations (with proper normalization)
- Validation studies against clinical markers
- Better documentation of assumptions

See [CLAUDE.md](./CLAUDE.md) for development guidelines.

## License

MIT License — See LICENSE file for details.

---

**healthOS** is a personal data intelligence project. It is not medical advice. Always consult healthcare professionals for health decisions.

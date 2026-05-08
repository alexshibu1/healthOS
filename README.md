# healthOS

**Personal health intelligence layer.** Ingests messy multi-source health data and produces monthly reports with a composite readiness score, bio-age proxy, and ranked top-3 interventions.

## The Wedge

No consumer device sees all your data. healthOS does—and derives more insights because of it.

By fusing data sources that no consumer app combines, healthOS turns fragmented wearables, workouts, and blood labs into a unified physiological picture:

- **CBC differential** (NLR, monocytes) — no wearable ingests this
- **Wearable HRV** — every wearable has it; none ties it to inflammatory markers
- **Workout pace/HR decoupling** — TrainingPeaks computes this but it's coach-facing
- **Sleep regularity** — Phillips SRI is peer-reviewed; no consumer app implements it

## Three Flagship Metrics

1. **NLR × HRV Training-Readiness Score** — Inflammatory markers meet autonomic state
2. **Sleep Regularity Index** — Phillips formula applied to personal data
3. **Aerobic Decoupling Trend** — Z-score of pace:HR efficiency over time

## Data Sources

| Source | What | Quirk | Weight |
|--------|------|-------|--------|
| Zepp/Amazfit | HRV, RHR, sleep | HRV logged at wake, not during sleep. Less reliable than chest strap. | Lower |
| JeFit | Lift volume, 1RM estimates | Strain proxy | Standard |
| Strava | Cardio strain, pace, power | HR zones often miscalibrated — trust pace/power over HR | Standard |
| Blood panels | CBC differential, markers | Episodic, not time-series. Context, not signal. | Context |

## Scoring Philosophy

- **Transparent weighted formulas over ML.** Every number is defendable.
- **Composite readiness** = `f(HRV trend, RHR trend, sleep debt, strain balance, subjective)`
- **Bio-age proxy is illustrative, not medical.** We're honest about uncertainty.
- **Single headline number** with drill-downs underneath.

See [skills/health-reasoning.md](./skills/health-reasoning.md) for full physiological reasoning.

## Architecture

```
src/
├── ingest/       Per-source CSV loaders, normalized to common schema
├── score/        Composite scoring, bio-age proxy
├── trends/       Month-over-month analysis, statistical significance
├── interventions/Ranker, evidence-tagged recommendations
└── report/       Monthly report generator

skills/          Domain knowledge: health reasoning, formulas, assumptions
evals/           Labeled days, divergence analysis for validation
```

## Guardrails

- ✋ **No synthetic data.** Ever.
- 📊 **Statistical methods first.** ML only if explicitly requested.
- 📐 **Formula before code.** Show the math first for any component >30 lines.
- 🚩 **Flag uncertainty.** When unsure about physiological claims, we flag it. No bullshit.
- 📋 **Spec before code.** Detailed specs for major components in `src/score/specs/`.

## Getting Started

### Requirements
- Python 3.9+
- Pandas, NumPy, SciPy
- Per-source export files (see `src/ingest/` for formats)

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

## Implementation Specs

- `src/score/specs/` — Detailed formulas and assumptions
- `skills/health-reasoning.md` — Physiological foundations
- `evals/` — Test cases and divergence analysis

## Data Privacy

- **Local computation.** No cloud sync or external processing.
- **Your data, your rules.** Keep everything in your own environment.

## Limitations & Caveats

- **Blood panels are episodic**, not continuous. They provide context, not real-time signals.
- **Zepp HRV is less reliable** than chest strap. Weighted accordingly.
- **Bio-age is illustrative**, not medical guidance. Consult a healthcare provider.
- **Strava HR zones are often miscalibrated.** We prefer pace/power metrics.
- **Sleep regularity ≠ sleep quality.** SRI captures timing, not depth or restoration.

## Contributing

This is a personal health project, but thoughtful improvements are welcome:

- Statistical improvements to scoring algorithms
- New data source integrations (with proper normalization)
- Validation studies against clinical markers
- Better documentation of assumptions

See [CLAUDE.md](./CLAUDE.md) for development guidelines.

## License

MIT License — See LICENSE file for details.

---

**healthOS** is a personal data intelligence project. It is not medical advice. Always consult healthcare professionals for health decisions.

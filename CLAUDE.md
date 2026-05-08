# health-os

## What this is

Personal health intelligence layer. Ingests messy multi-source data
(WHOOP-alt, Zepp/Amazfit, JeFit, Strava, blood panels) and produces
a monthly report with a composite readiness score, a bio-age proxy,
and a ranked top-3 of 80/20 interventions.

The wedge: no consumer device sees all my data. This does.

## Data sources and quirks

- Zepp/Amazfit: HRV logged at wake, not during sleep. Less reliable than chest strap. Weight lower in composite.
- JeFit: lift volume + 1RM estimates. Use for strain proxy.
- Strava: cardio strain. HR zones often miscalibrated — trust pace/power over HR.
- Blood panels: episodic, not time-series. Treat as context, not signal.

## Scoring philosophy

- Transparent weighted formulas over ML. I need to defend every number.
- Composite readiness = f(HRV trend, RHR trend, sleep debt, strain balance, subjective).
- Bio-age proxy is illustrative, not medical. Be honest about uncertainty.
- Single headline number. Drill-downs underneath.

## Guardrails

- Do not generate synthetic data. Ever.
- Do not use ML libraries unless I explicitly ask. Statistical methods first.
- Show me the formula before the code.
- When unsure about a physiological claim, flag it. Do not bullshit.
- Spec before code for any component over ~30 lines.

## File structure

- src/ingest/ — per-source CSV loaders, normalize to common schema
- src/score/ — composite scoring, bio-age proxy
- src/trends/ — month-over-month, statistical significance
- src/interventions/ — ranker, evidence-tagged
- src/report/ — monthly report generator
- skills/ — domain skills (see skills/health-reasoning.md)
- evals/ — labeled days, divergence analysis

## Eval criteria

The score is good if it correlates with my felt-recovery on 15 labeled days
(see evals/labeled-days.md). Divergences must be explainable.

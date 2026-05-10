# `alex_demo` — public fixture tree

This folder mirrors the shape of a real `rawdata/` directory so **`make demo`** and CI can run without your private exports.

## Narrative this fixture is shaped around

The synthetic timeline is intentionally labeled so **you** (and anyone cloning the repo) know what the demo is pretending happened:

1. **January 2026** — Respiratory illness / close call with pneumonia (recovery arc — dates are **demo labels**, not medical records).
2. **Late March 2026** — CBC draw in `blood_panels/synthetic_panel.md` is written as **post-illness rebound / inflammatory tail** chemistry (still **not real PHI** — stylized numbers aligned to that story).
3. **March–April 2026** — Overlapping **GI-style illness window** in `context_flags.yaml` exercises composite + divergence + LLM handoff text (also labeled synthetic).

Your **real** long-form summaries (e.g. Oct 2025 tables, medication notes, OCOR-style targets) belong in **your private `rawdata/`** — not committed here. This demo only carries **enough** structured CBC + flags to drive NLR×HRV, composite, and narrative hooks.

## Where the wearable streams live

| Role | In this demo |
|------|----------------|
| Zepp / Amazfit Helio exports (sleep, HR, HRV, activity) | `amazfit helio/` — **this is where wake HRV and related series live** (same layout as your private tree). |
| Strava | `strava/activities.csv` |
| JeFit | `bigAppleALEX_*.csv` at fixture root |
| Blood markdown panels | `blood_panels/*.md` |

On your machine, the **full** device export set should live under **`rawdata/`** at the repo root (or whatever you set `RAWDATA_ROOT` to), with the same folder names as here.

Run **`bash scripts/init_private_rawdata.sh`** once to create that skeleton; see **`docs/private-rawdata-layout.md`** for paths and environment variables.

## Files to edit when refreshing the public slice

- `profile.yaml` — demo athlete stub.
- `context_flags.yaml` — illness / travel / injury windows referenced by scoring + LLM prompt “Recent context”.
- `blood_panels/synthetic_panel.md` — YAML frontmatter + markdown tables (must keep **Marker | Value | Reference Range | Status** headers per loader).
- `systemic_daily.csv` — monthly trend input when present.

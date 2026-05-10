# Private `rawdata/` layout (your machine only)

The repo expects a folder named **`rawdata/`** at the project root (`src/ingest/config.py`). That directory is **gitignored** — nothing under it is committed.

## One-time scaffold

From the repo root:

```bash
bash scripts/init_private_rawdata.sh
```

This creates empty Amazfit / Strava / blood panel paths and drops a **`rawdata/README.txt`** reminder on disk.

## What goes where

| Path under `rawdata/` | Contents |
|----------------------|----------|
| `amazfit helio/` | Zepp export CSVs (`SLEEP`, `SLEEP_MINUTE`, `HEARTRATE_AUTO`, `ACTIVITY`, …) — **wake HRV lives here.** |
| `strava/` | `activities.csv` (and any other files your Strava loader expects). |
| `bigAppleALEX_*.csv` (optional at **root** of `RAWDATA_ROOT`) | JeFit export filename pattern used by the loader. |
| `blood_panels/*.md` | Markdown panels with YAML frontmatter + tables (`Marker \| Value \| Reference Range \| Status`). One file per draw. |
| `universal.csv` (optional) | Wide single-file ingest — see `src/ingest/universal_csv/spec.md`. Loaded automatically when present. |
| `profile.yaml` | Optional — copied/adapted from `data/examples/alex_demo/profile.yaml` if you want overrides next to data. |
| `context_flags.yaml` | Optional — illness / travel / injury windows (same schema as demo). |
| `systemic_daily.csv` | Optional — your merged daily systemic CSV for trends if you maintain one. |
| `notes/` | **Optional, not ingested.** Drop free-form summaries (Oct 2025 health tables, OCOR targets, med lists) for **your** reference; point an LLM at these manually if needed — they are **not** wired into `load_all` today. |

## Starting from the public demo

Copy the fixture tree, then replace files with your exports:

```bash
cp -R data/examples/alex_demo/. rawdata/
# Then overwrite amazfit helio/, strava/, blood_panels/, etc. with real exports.
```

Edit paths in **`CONTEXT_FLAGS`** / **`HEALTHOS_PROFILE`** when you run the pipeline, or place `profile.yaml` and `context_flags.yaml` inside `rawdata/` and export:

```bash
export RAWDATA_ROOT="$(pwd)/rawdata"
export HEALTHOS_PROFILE="$(pwd)/rawdata/profile.yaml"
export CONTEXT_FLAGS="$(pwd)/rawdata/context_flags.yaml"
```

## Privacy

Do not commit `rawdata/` or paste PHI into issues/PRs. If you need a **sanitized** public demo slice, trim and copy into `data/examples/alex_demo/` separately.

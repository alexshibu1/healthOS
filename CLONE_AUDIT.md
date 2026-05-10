# Clone-and-run audit (read-only)

Perspective: a stranger runs `git clone` and follows **README.md** and obvious defaults. Commands below were run from the repo root on **macOS** with **Python 3.11** (pyenv). Browser console was **not** exercised in this audit; **`npm run build`** was used as a proxy that the TS bundle type-checks and bundles.

---

## Step 1: Read README from the top — what it is, how to run

- **Worked / Broken / Confusing:** **Confusing** (clear product pitch; run instructions arrive late).

- **Observation:** The **first paragraph** is a solid one-sentence product summary (“Personal health intelligence layer…”). The **next** blocks are **The Wedge**, **Pipeline** (mermaid), **Demo (web report)** screenshot, then **Three flagship metrics** (long). The first explicit **“how to run”** is **`## Run the demo`** (`make demo`) around **line 69**, not the paragraph immediately after the opener. A rushed reader may scroll past narrative before seeing commands.

- **Fix needed:** Add a **3-line Quickstart** immediately under the title or after the first paragraph: install deps + `make demo` + URL (or note that demo ends in `npm run dev`). Optional: move **`Run the demo`** higher.

---

## Step 2: Run install commands “as written”

- **Worked / Broken / Confusing:** **Confusing** — README **does not** spell out install commands before **`make demo`**.

- **Observation:** **`Run the demo`** only shows `make demo`. There is **no** `pip install -r requirements.txt` and **no** `cd web && npm install` in that section. **`Getting Started`** lists Python deps by name but not an explicit pip command. A newcomer must infer installs from **`requirements.txt`** / **`web/package-lock.json`**. When **`pip install -r requirements.txt`** and **`cd web && npm install`** were run in this environment, they **succeeded** (exit 0).

- **Fix needed:** In **`Run the demo`** (or Quickstart), add:
  - `pip install -r requirements.txt` (from repo root)
  - `cd web && npm ci` or `npm install`

---

## Step 3: Dependency completeness (`requirements.txt`, `package.json`)

- **Worked / Broken / Confusing:** **Worked** with minor **Confusing** notes.

- **Observation:** **`requirements.txt`** includes pandas, scipy, pyarrow, PyYAML, pytest, tzdata. **`numpy`** is not pinned explicitly but is pulled in as a **pandas** dependency (typical installs succeed). **`package.json`** lists Vite, React, Tailwind, Recharts, Framer Motion, etc.; **`npm install`** completed without missing-package errors on this machine.

- **Fix needed:** Optional: add **`numpy`** explicitly if you want deterministic installs or offline tooling that installs wheels separately.

---

## Step 4: Run `make demo`

- **Worked / Broken / Confusing:** **Confusing** / **Broken** for “done when command returns.”

- **Observation:** The **`Makefile`** **`demo`** target runs the **full Python pipeline** successfully **when each step is considered separately** (same order as the Makefile): ingest → scorers → composite → bio_age → trends → interventions → **`snapshot_builder`** → then **`cd web && npm run dev`**. That **last line starts Vite and blocks forever**, so **`make demo` never “finishes”** in the shell sense — the user must Ctrl+C to exit the dev server. **Exit code 0** was observed for a **full scripted run** of all Python steps ending at **`snapshot_builder`** (excluding **`npm run dev`**). **stderr** on this host repeatedly shows **`hashlib` blake2b/blake2s “not found”** traces from Python startup — alarming-looking but **non-fatal** here (known pyenv/OpenSSL class of noise).

- **Fix needed:** Document that **`make demo` intentionally leaves the dev server running**, or split **`demo`** vs **`demo-pipeline`** (pipeline-only, no `npm run dev`). Optionally note **hashlib** noise for macOS/pyenv users.

---

## Step 5: `snapshot.json` produced?

- **Worked**

- **Observation:** After the **full** Makefile Python sequence (through **`python -m src.report.snapshot_builder --date … --out web/src/data/snapshot.json`**), **`web/src/data/snapshot.json`** is **written** (“Wrote …/snapshot.json”). **`make demo`** alone does not return; if the user Ctrl+C **before** the snapshot step completes, they may have **no or stale** JSON.

- **Fix needed:** None for correctness if the user lets the Makefile progress past **`snapshot_builder`** before interacting with the dev server.

---

## Step 6: Dashboard renders (`npm run dev` / build)

- **Worked** (build); **Confusing** (demo UX).

- **Observation:** **`npm run build`** in **`web/`** completed successfully (**`tsc -b && vite build`**, exit 0). **`loadSnapshot()`** validates JSON at runtime; invalid snapshots throw at load time. **`npm run dev`** was not left running for manual UI verification in this audit.

- **Fix needed:** None from build alone.

---

## Step 7: Plausible data, “—”, empty arrays, console errors

- **Worked / Confusing**

- **Observation** (after **full** demo pipeline on **`data/examples/alex_demo`**): **`state`** is **`insufficient_data`** because **NLR×HRV** remains **`unknown`** (wedge gate); **`todayScoreDisplay`** is **`"—"`** (intentional). **`secondaryReadouts`** is **`[]`** — **empty** (no **`data/trends/<month>.json`** in default flow falls back to placeholders per **`snapshot_builder`**; still reads sparse). **Flagship cards:** **NLR×HRV** shows **`displayScore`: `"—"`** (expected). **SRI** has numeric **`score`** (e.g. 65) but **`displayScore`** is still **`"—"`** when headline is **`insufficient_data`** (by design in builder — **confusing** if the user expects to “see SRI” as a headline number). **Decoupling** shows **`displayZscore`: `"—σ"`** when unknown. **Streams:** **JeFit** may show **`missing`** if the demo CSV name/layout doesn’t match loader expectations vs **`whoop`** placeholder **missing**. **Interventions** reference **`Composite 0.0 below 55`** after regeneration — **consistent** with **`insufficient_data`** (not the old stale “38” text).

- **Fix needed:** Smallest clarity wins: README one-liner that **demo snapshot may be mostly “insufficient_data”** until HRV/CBC coverage supports NLR×HRV; optional UI copy distinguishing **SRI numeric ring vs composite headline**.

---

## Step 8: Run on own data — path, folder layout, format

- **Worked / Confusing**

- **Observation:** **`## Run on your own data`** lists **`RAWDATA_ROOT`**, **`amazfit helio/`** tree, **`strava/activities.csv`**, **`bigAppleALEX_*.csv`**, **`blood_panels/*.md`**, optional **`profile.yaml`**, **`context_flags.yaml`**, **`systemic_daily.csv`**, and points to **`load_all --help`** and **`src/ingest/`**. That is a **real** path but **dense** (many filenames). **`Defaults`** say **`rawdata/`** at repo root — correct per **`src/ingest/config.py`**.

- **Fix needed:** Add a **minimal tree diagram** or link **`data/examples/alex_demo`** as the copy-paste shape; mention **JeFit filename glob** explicitly (`bigAppleALEX_*.csv`).

---

## Step 9: LICENSE line in README

- **Broken** (repo artifact).

- **Observation:** README **License** section says **“MIT License — See LICENSE file”** but **no `LICENSE` file** exists in the repo root (glob found 0 files).

- **Fix needed:** Add **`LICENSE`** or change README wording.

---

## Summary table

| Step | Verdict |
|------|---------|
| README one-liner | Works |
| README immediate “how to run” | Confusing (late) |
| Documented install commands | Missing before demo |
| pip / npm installs (when inferred) | Worked |
| deps completeness | Worked (numpy transitive) |
| `make demo` “completes” | Broken as non-blocking command |
| Python pipeline + snapshot | Worked |
| `npm run build` | Worked |
| Dashboard data “pretty” | Confusing (honest insufficient_data demo) |
| Own-data instructions | Works but dense |
| LICENSE | Broken vs README |

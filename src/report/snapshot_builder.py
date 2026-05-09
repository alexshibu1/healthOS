"""
Build ``SnapshotData`` JSON for ``web/src/types.ts`` from parquet scores +
optional trends/interventions artefacts.

CLI: python -m src.report.snapshot_builder --date YYYY-MM-DD --out path/to/snapshot.json

Spec: src/report/spec-snapshot.md
"""

from __future__ import annotations

import argparse
import calendar
import json
import math
import os
import re
import sys
from datetime import date, timedelta
from pathlib import Path
from typing import Any, Mapping, MutableMapping

import pandas as pd
import yaml

_REPO_ROOT = Path(__file__).resolve().parents[2]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from src.interventions.rank import rank_interventions
from src.context.flags import get_active_flags


class SnapshotBuildError(RuntimeError):
    """Raised before JSON emit when artefacts are missing."""

    def __init__(self, missing_path: Path, regenerate_hint: str) -> None:
        self.missing_path = Path(missing_path)
        self.regenerate_hint = regenerate_hint.strip()
        combined = (
            f"Missing or invalid artefact:\n"
            f"  path     : {self.missing_path}\n"
            f"  regenerate hint:\n    {regenerate_hint.replace(chr(10), chr(10) + '    ')}"
        )
        super().__init__(combined)


def _scores_dir(root: Path) -> Path:
    return root / "data" / "scores"


_REQUIRED_PARQUET = (
    "composite.parquet",
    "nlr_hrv.parquet",
    "sri.parquet",
    "aerobic_decoupling.parquet",
    "bio_age.parquet",
)


_COMPOSITE_TO_SNAPSHOT_UI: dict[str, str] = {
    "recovered": "recovered",
    "cleared": "cleared",
    "deload": "deload",
    "autonomic-recovery-leading": "autonomic-recovery-leading",
    "peripheral-strain": "peripheral-strain",
    "illness-risk": "illness-risk",
    "accumulating-fatigue": "accumulating-fatigue",
    "insufficient_data": "insufficient_data",
}


# Composite `caution` is NLR-tier only; KPI headline maps it to SPA label "caution"
_COMPOSITE_TO_SNAPSHOT_UI["caution"] = "caution"


_STATE_ACTION_BRIDGE: dict[str, str] = {
    "illness-risk": "Stop planned intensity; prioritize rest and clinician follow-up.",
    "deload": "Cap session intensity and truncate volume blocks until physiology normalizes.",
    "accumulating-fatigue": "Pull volume for 72h; favour sleep anchors before reassessing strain.",
    "peripheral-strain": (
        "Treat as environmental/cardiovascular economy — hydrate, stabilise pacing before deload reflex."
    ),
    "autonomic-recovery-leading": "Hold reload ramps while labs catch up — autonomic rebound already visible.",
    "cleared": "Resume density gradually; prioritise CBC follow-up cadence negotiated with physician.",
    "recovered": "Maintain current stimulus so long as context flags remain quiet.",
    "insufficient_data": "Defer training prescriptions until CBC + wearable baselines converge.",
    "caution": "Cap intensity temporarily while mixed signals reconcile.",
}


_CBC_DAYS_RX = re.compile(r"CBC age:\s*(\d+)\s*d", re.I)

_NLR_REASON_SHORT: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"No CBC data", re.I), "Fresh CBC differential required."),
    (
        re.compile(r"Insufficient HRV baseline", re.I),
        "Insufficient wake HRV history for baseline window.",
    ),
    (
        re.compile(r"Today's HRV missing", re.I),
        "Today's HRV missing with no allowable substitute median.",
    ),
]


def _format_missing_parquet(repo_root: Path, name: str) -> SnapshotBuildError:
    p = _scores_dir(repo_root) / name
    base = "See src/report/spec-snapshot.md §1 for parquet contracts."
    hints = {
        "composite.parquet": (
            "Populate via src.score.composite.score_range(...) after assembling per-day dicts "
            "from nlr_hrv_readiness.score_day + flagship inputs (wired to ingest in your runner)."
        ),
        "nlr_hrv.parquet": "Populate via src.score.nlr_hrv_readiness.score_range(...).",
        "sri.parquet": "Populate via python -m src.score.sri (after ingest).",
        "aerobic_decoupling.parquet": (
            "Populate via python -m src.score.aerobic_decoupling (after ingest)."
        ),
        "bio_age.parquet": (
            "Run src.score.bio_age.score_timeseries_to_parquet("
            "input_csv=…, chronological_age=float from data/profile.yaml, output_parquet=…)."
        ),
    }
    extra = hints.get(name) or (
        "Run the scorer modules under src/score/ that emit this parquet; see Makefile demo "
        "target for ordering."
    )
    return SnapshotBuildError(p, f"{base}\n{extra}")


def _assert_parquets(repo_root: Path) -> dict[str, Path]:
    sd = _scores_dir(repo_root)
    out: dict[str, Path] = {}
    for fn in _REQUIRED_PARQUET:
        fp = sd / fn
        if not fp.is_file():
            raise _format_missing_parquet(repo_root, fn)
        out[fn] = fp.resolve()
    return out


def _read_parquet(path: Path, required_cols: tuple[str, ...]) -> pd.DataFrame:
    df = pd.read_parquet(path)
    miss = sorted(set(required_cols) - set(df.columns))
    if miss:
        raise SnapshotBuildError(
            path,
            f"Parquet schema drift — missing columns {miss}. Rewrite writer for {path.name}.",
        )
    df = df.copy()
    df["date"] = pd.to_datetime(df["date"]).dt.date
    return df


def _previous_calendar_month(month_anchor: date) -> tuple[int, int]:
    y, m = month_anchor.year, month_anchor.month
    if m == 1:
        return y - 1, 12
    return y, m - 1


def _month_dates(y: int, m: int) -> tuple[date, date]:
    start = date(y, m, 1)
    last = calendar.monthrange(y, m)[1]
    return start, date(y, m, last)


def _month_series_mean(comp: pd.DataFrame, dt: date) -> tuple[float, float | None]:
    """Mean composite.score for calendar month(dt) vs prior calendar month."""

    y, m = dt.year, dt.month
    s0, e0 = _month_dates(y, m)
    py, pm = _previous_calendar_month(date(y, m, 1))
    s1, e1 = _month_dates(py, pm)

    v0 = pd.to_numeric(comp[(comp["date"] >= s0) & (comp["date"] <= e0)]["score"], errors="coerce").dropna()
    v1 = pd.to_numeric(comp[(comp["date"] >= s1) & (comp["date"] <= e1)]["score"], errors="coerce").dropna()
    cur = float(v0.mean()) if len(v0) else float("nan")
    prev = float(v1.mean()) if len(v1) else None
    return cur, prev


def _six_month_hist(comp: pd.DataFrame, anchor: date) -> list[dict[str, Any]]:
    y, m = anchor.year, anchor.month
    hist: list[dict[str, Any]] = []

    yy, mm = y, m
    for delta in reversed(range(5, -1, -1)):
        ty, tm = yy, mm
        for _ in range(delta):
            ty, tm = _previous_calendar_month(date(ty, tm, 28))
        s, e = _month_dates(ty, tm)
        sub = pd.to_numeric(comp[(comp["date"] >= s) & (comp["date"] <= e)]["score"], errors="coerce").dropna()
        mean_score = round(float(sub.mean()), 4) if len(sub) else 0.0
        hist.append({"month": f"{calendar.month_abbr[tm]} {ty}", "score": round(mean_score)})
    return hist


def _parse_divergence_flags(raw_val: Any) -> list[str]:
    if raw_val is None or (isinstance(raw_val, float) and pd.isna(raw_val)):
        return []
    if isinstance(raw_val, str):
        s = raw_val.strip()
        if s.startswith("["):
            try:
                parsed = json.loads(s)
                if isinstance(parsed, list):
                    return [str(x) for x in parsed]
            except json.JSONDecodeError:
                pass
        return [s]
    try:
        return [str(x) for x in list(raw_val)]
    except Exception:
        return []


def _sri_unknown_reason(reasoning: str | None, tier_s: str) -> str | None:
    """Short copy for parquet rows without scorer narrative."""

    if tier_s != "unknown":
        return None
    if reasoning and reasoning.strip():
        return reasoning.strip()[:260]
    return "SRI tier unknown — scorer not emitting band."


def _sparkline(series: pd.Series, width: int) -> list[float]:
    vals = pd.to_numeric(series, errors="coerce").tolist()
    if len(vals) < width:
        vals = ([0.0] * (width - len(vals))) + vals
    out_f: list[float] = []
    for x in vals[-width:]:
        if isinstance(x, float) and (math.isnan(x) if x == x else True):
            out_f.append(0.0)
        else:
            out_f.append(float(x or 0))
    return out_f


def _nlr_unknown_display(reasoning: str) -> tuple[str | None, int | None]:
    r = reasoning or ""
    age_m = _CBC_DAYS_RX.search(r)
    cbc_age = int(age_m.group(1)) if age_m else None
    note: str | None = None
    if cbc_age is not None and ("stale" in r.lower() or "cbc_stale" in r.lower()):
        note = f"CBC {cbc_age}d stale"
    elif cbc_age is not None:
        note = f"CBC {cbc_age}d old"

    if note is None:
        for rx, canned in _NLR_REASON_SHORT:
            if rx.search(r):
                note = canned
                break
    if note is None and r.strip():
        note = r[:160] + ("…" if len(r) > 160 else "")
    return note, cbc_age


def _state_color(metric: str, val: float) -> str:
    """Map heuristic metric to ``StateColor`` token string."""

    if metric == "cohens":
        return "amber" if abs(val) >= 0.35 else "green"
    if metric == "bio_pull":
        if val > 0.6:
            return "red"
        if val > 0.35:
            return "amber"
        if val >= 0:
            return "rose"
        return "green"
    return "green"


def _tier_from_sri_score(score_val: float) -> str:
    if score_val >= 80:
        return "high"
    if score_val >= 70:
        return "moderate"
    return "irregular"


def _profile_path(repo_root: Path) -> Path:
    env = os.environ.get("HEALTHOS_PROFILE")
    if env:
        return Path(env).expanduser().resolve()
    return repo_root / "data" / "profile.yaml"


def _context_flags_path(repo_root: Path) -> Path:
    for key in ("HEALTHOS_CONTEXT_FLAGS", "CONTEXT_FLAGS"):
        env = os.environ.get(key)
        if env:
            return Path(env).expanduser().resolve()
    return repo_root / "data" / "context_flags.yaml"


def _trends_dir(repo_root: Path) -> Path:
    env = os.environ.get("HEALTHOS_TRENDS_DIR")
    if env:
        return Path(env).expanduser().resolve()
    return repo_root / "data" / "trends"


def _interventions_dir(repo_root: Path) -> Path:
    env = os.environ.get("HEALTHOS_INTERVENTIONS_DIR")
    if env:
        return Path(env).expanduser().resolve()
    return repo_root / "data" / "interventions"


def load_profile_yaml(repo_root: Path) -> Mapping[str, Any]:
    pp = _profile_path(repo_root)
    if not pp.is_file():
        raise SnapshotBuildError(pp, "Create data/profile.yaml with chronological age:int.")
    return yaml.safe_load(pp.read_text(encoding="utf-8")) or {}


def _bio_breakdown(contrib_blob: Any) -> list[dict[str, Any]]:
    if isinstance(contrib_blob, str):
        data = json.loads(contrib_blob or "[]")
    else:
        data = contrib_blob
    NAME_MAP = {
        "sri": "Sleep regularity",
        "hrv_trend": "HRV 30d trend",
        "rhr_baseline": "Resting HR drift",
    }
    rows: list[dict[str, Any]] = []
    for item in data or []:
        raw_name = item.get("name") or ""
        disp = NAME_MAP.get(str(raw_name), str(raw_name).replace("_", " ").title())
        pull = float(item.get("years_pulled", item.get("pullYears", 0)))
        share = float(item.get("share_of_total", 0))
        rationale = item.get("rationale", "") or ""
        rows.append({
            "name": disp,
            "pullYears": round(pull, 4),
            "weightPct": round(share * 100.0, 4),
            "detail": rationale[:260],
            "state": _state_color("bio_pull", pull),
        })
    return rows


def _fallback_secondary(bio_row: Mapping[str, Any], comp_score_for_note: float) -> list[dict[str, Any]]:
    """
    Fallback when ``data/trends/<YYYY-MM>.json`` absent:


    Principle: recycle transparent bio-age pulls + cite composite coverage ---
    placeholders keep the SecondaryReadouts strip populated without inventing unseen metrics.


    """
    out: list[dict[str, Any]] = []
    try:
        contribs = _bio_breakdown(bio_row["contributors_json"])
    except Exception:
        contribs = []

    if contribs:
        for c in contribs[:2]:
            out.append({
                "label": f"Bio-age · {c['name'][:18]}",
                "value": f"{c['pullYears']:+.1f} yrs",
                "note": "share of summed |Δ| magnitude (see breakdown)",
                "state": c["state"],
            })
    gy = bio_row.get("gap_years")
    if gy is not None and pd.notna(gy):
        out.append({
            "label": "Bio-age gap",
            "value": f"{float(gy):+.1f} yrs",
            "note": "proxy vs chronological baseline",
            "state": _state_color("bio_pull", float(gy)),
        })

    out.append({
        "label": "Trend file",
        "value": "(absent)",
        "note": f"Today's composite `{comp_score_for_note:.1f}`; run trends writer for richer scan lines.",
        "state": "amber",
    })
    pad = {"label": "Placeholder", "value": "--", "note": "Pad to four slots when bio contributors sparse.", "state": "amber"}
    while len(out) < 4:
        out.append(dict(pad))
    return out[:4]


def _trends_secondary(blob: Mapping[str, Any]) -> list[dict[str, Any]]:
    ranked = blob.get("trends_ranked_by_effect_size") or []
    labels = {"composite": "Composite ΔMoM", "nlr_hrv": "NLR×HRV Δ", "sri": "SRI Δ", "decoupling": "Decoupling Δ"}
    readouts = []
    for row in ranked[:4]:
        key = str(row.get("key") or "metric")
        d = row.get("cohens_d") or 0.0
        sig = row.get("significant")
        readouts.append({
            "label": labels.get(key, key.upper()),
            "value": f"{float(d):+.2f}σ",
            "note": "MoM effect size; significant" if sig else "MoM effect size; exploratory",
            "state": _state_color("cohens", float(d)),
        })
    return readouts


def _drivers_from_context(repo_root: Path, scoring_date: date, nlr_row: Mapping[str, Any]) -> list[dict[str, Any]]:
    tier_nlr = str(nlr_row.get("tier") or "").lower()
    reasoning = str(nlr_row.get("reasoning") or "")
    note, cb_age = _nlr_unknown_display(reasoning)
    drivers: list[dict[str, Any]] = []

    if tier_nlr == "unknown":
        drivers.append({
            "signal": "NLR×HRV",
            "value": "— unavailable",
            "note": note or "NLR scorer tier=unknown.",
            "state": "amber",
        })
    elif (sv := pd.to_numeric(nlr_row.get("score"), errors="coerce")) == sv:
        col = (
            "red" if tier_nlr == "deload" else "amber" if tier_nlr in ("caution", "yellow") else "green"
        )
        drivers.append({
            "signal": "NLR×HRV",
            "value": f"{float(sv):.2f}",
            "note": reasoning[:220] + ("…" if len(reasoning) > 220 else ""),
            "state": col,
        })
    elif cb_age:
        drivers.append({
            "signal": "CBC anchor",
            "value": f"{cb_age}d since draw",
            "note": reasoning[:200] + ("…" if len(reasoning) > 200 else ""),
            "state": "amber" if cb_age > 45 else "green",
        })

    ctx_path = _context_flags_path(repo_root)
    if ctx_path.is_file():
        loaded = yaml.safe_load(ctx_path.read_text(encoding="utf-8")) or {}
        pairs = (
            ("Illness window", "illness_windows"),
            ("Travel window", "travel_windows"),
            ("Injury window", "injury_windows"),
        )
        for label, ck in pairs:
            wins = loaded.get(ck) or []
            if not wins:
                continue
            win0 = wins[0]
            note_txt = str(win0.get("note") or "")
            rng = ""
            try:
                st = pd.to_datetime(win0["start"]).date()
                ed = pd.to_datetime(win0["end"]).date()
                rng = f"{st.isoformat()} – {ed.isoformat()}"
                active = st <= scoring_date <= ed
            except Exception:
                active = False
                rng = rng or str(win0)

            drv_state = (
                "rose" if active and ck == "illness_windows"
                else "blue" if active
                else "green"
            )
            drivers.append({
                "signal": label + (" (active)" if active else ""),
                "value": note_txt[:96] if note_txt else rng[:96],
                "note": rng,
                "state": drv_state,
            })

    return drivers


def _diag_question(insufficient: bool, missing_bits: list[str]) -> Mapping[str, Any] | None:
    if not insufficient:
        return None
    human = "; ".join(missing_bits[:5]) if missing_bits else "flagship coverage"
    return {
        "prompt": (
            f"Insufficient-data gate — missing: {human}. Which explanation best matches?"
        ),
        "options": [
            {
                "id": "fresh_cbc",
                "label": "Fresh CBC differential landed.",
                "response": {
                    "headline": "Queue blood panel ingest → rebuild nlr_hrv + composite parquets.",
                    "confidenceTransition": "",
                    "actions": ["Ingest CBC", "Re-run parquet writers"],
                },
            },
            {
                "id": "wearable_backfill",
                "label": "Wearable CSV back-filled for HRV dates.",
                "response": {
                    "headline": "Backfilled HEARTRATE_AUTO restores baseline counting window.",
                    "confidenceTransition": "",
                    "actions": ["load_all ingest", "nlr_hrv.score_range"],
                },
            },
            {
                "id": "planned_break",
                "label": "Intentional deload unrelated to telemetry gaps.",
                "response": {
                    "headline": "Annotate deliberate rest/travel windows in context_flags.yaml.",
                    "confidenceTransition": "",
                    "actions": ["Edit YAML windows", "Re-run composite"],
                },
            },
        ],
    }


def _interventions_fallback(_repo_root: Path, _interventions_fp: Path, env: Mapping[str, Any]) -> list[dict[str, Any]]:
    ranked = rank_interventions(dict(env), limit=3)
    out_i: list[dict[str, Any]] = []
    mo_lbl_short = env["window_label_short"]
    for i, rule in enumerate(ranked, 1):
        act = str(rule["action"])
        lc = act.lower()
        cat: Any = (
            "sleep" if "sleep" in lc
            else "training" if "zone" in lc or "training" in lc or "lift" in lc
            else "recovery"
        )
        item: dict[str, Any] = {
            "action": act,
            "effort": int(rule["effort"]),
            "impact": str(rule["impact"]),
            "category": cat,
            "why": str(rule["why"]),
            "skillRef": str(rule["skill_ref"]),
            "shortcut": f"⌘{i}",
            "projectedComposite": {"value": "+2 pts" if rule["impact"] == "HIGH" else "+1 pt", "on": mo_lbl_short},
        }
        gy = env.get("gap_years") or 0
        try:
            gy_f = float(gy)
        except (TypeError, ValueError):
            gy_f = 0.0
        if gy_f > 2.0:
            item["projectedBioAge"] = {"value": "-0.2 yrs", "on": "bio-age gap"}
        out_i.append(item)

    while len(out_i) < 3:
        out_i.append({
            "action": "Protect sleep anchors",
            "effort": 2,
            "impact": "MED",
            "category": "sleep",
            "why": (
                "No intervention rules triggered — deterministic fallback until lookup.yaml matches scoring."
            ),
            "skillRef": "§2.2",
            "shortcut": f"⌘{len(out_i) + 1}",
            "projectedComposite": {"value": "+1 pt", "on": mo_lbl_short},
        })
    return out_i[:3]


def load_interventions_file_or_rank(
    repo_root: Path, interventions_fp: Path, env: Mapping[str, Any]
) -> list[dict[str, Any]]:
    """Prefer JSON list on disk else deterministic rank."""

    if interventions_fp.is_file():
        blob = json.loads(interventions_fp.read_text(encoding="utf-8"))
        if isinstance(blob, list) and blob:
            return blob
        if isinstance(blob, dict) and isinstance(blob.get("interventions"), list):
            lst = blob["interventions"]
            if lst:
                return lst
    return _interventions_fallback(repo_root, interventions_fp, env)


def streams_from_parquets(scoring_date: date, nlr_tab: pd.DataFrame, ado_tab: pd.DataFrame) -> list[dict[str, Any]]:
    """
    Streams pills without raw-device sync:


    Principle: freshest scoring row date vs snapshot date ⇒ verbal band (`fresh`|`stale`…).


    Thresholds chosen for UI only — update when TelemetrySync ships.


    """

    def age_days(tbl: pd.DataFrame) -> int:
        sub = tbl[tbl["date"] <= scoring_date]
        if sub.empty:
            return 999
        mx = max(sub["date"])
        return int((scoring_date - mx).days) if isinstance(mx, date) else 999

    def bucket(days: int) -> tuple[str, str]:
        if days <= 3:
            return "fresh", f"{max(days, 0)}d"
        if days <= 14:
            return "stale", f"{days}d"
        if days <= 60:
            return "old", f"{days}d"
        return "missing", "60d+"

    d_nlr = age_days(nlr_tab)
    d_ef = age_days(ado_tab)
    st_lab, lbl_lab = bucket(min(d_nlr, d_ef))
    return [
        {"source": "amazfit", "label": "AMAZFIT", "status": bucket(d_nlr)[0], "synced": bucket(d_nlr)[1]},
        {"source": "strava", "label": "STRAVA", "status": bucket(d_ef)[0], "synced": bucket(d_ef)[1]},
        {"source": "jefit", "label": "JEFIT", "status": "missing", "synced": "unknown"},
        {"source": "whoop", "label": "WHOOP", "status": "missing", "synced": "n/a"},
        {"source": "bloodwork", "label": "LABS", "status": st_lab, "synced": lbl_lab},
    ]


def _nlr_numeric_for_rules(nlr_score: Any, reasoning: str) -> float:
    """Heuristic CBC NLR for intervention triggers (~3 neighbourhood)."""

    m = re.search(r"\b(?:NLR|nlr)[^\d]{0,8}(\d+\.?\d*)\b", reasoning or "")
    if m:
        try:
            v = float(m.group(1))
            if v > 0.5:
                return v
        except ValueError:
            pass

    nv = pd.to_numeric(nlr_score, errors="coerce")
    if nv == nv and float(nv) > 1e-3:
        return max(3.0, float(nv))

    return 3.1


def _strip_none_shallow(flagship: Mapping[str, Any]) -> dict[str, Any]:
    """Remove optional None keys TS marks optional (display fields)."""


    def prune(d: dict[str, Any]) -> dict[str, Any]:
        return {k: v for k, v in d.items() if v is not None}

    return {
        "nlrHrv": prune(dict(flagship["nlrHrv"])),
        "sri": prune(dict(flagship["sri"])),
        "decoupling": prune(dict(flagship["decoupling"])),
    }


def build_snapshot(score_date: date, *, repo_root: Path | None = None) -> dict[str, Any]:
    rr = Path(repo_root).resolve() if repo_root else _REPO_ROOT.resolve()

    ctx_yaml = _context_flags_path(rr)
    if not ctx_yaml.is_file():
        raise SnapshotBuildError(ctx_yaml, "Create data/context_flags.yaml (even if windows empty []).")

    paths = _assert_parquets(rr)
    comp = _read_parquet(
        paths["composite.parquet"],
        ("date", "state", "score", "primary_signal", "divergence_flags", "reasoning", "confidence"),
    )
    nlr = _read_parquet(paths["nlr_hrv.parquet"], ("date", "score", "tier", "confidence", "reasoning"))

    sp = pd.read_parquet(paths["sri.parquet"])
    miss_s = sorted({"date", "score", "tier"} - set(sp.columns))
    if miss_s:
        raise SnapshotBuildError(paths["sri.parquet"], f"sri parquet missing columns {miss_s}")
    sp = sp.copy()
    sp["date"] = pd.to_datetime(sp["date"]).dt.date

    ad = pd.read_parquet(paths["aerobic_decoupling.parquet"])
    cols = [c.lower() if isinstance(c, str) else c for c in ad.columns]
    ad.columns = cols
    if "zscore" not in ad.columns and "ef_zscore" in ad.columns:
        ad = ad.rename(columns={"ef_zscore": "zscore"})
    miss_a = sorted({"date", "tier", "zscore"} - set(ad.columns))
    if miss_a:
        raise SnapshotBuildError(paths["aerobic_decoupling.parquet"], f"aerobic_decoupling parquet missing {miss_a}")
    ad["date"] = pd.to_datetime(ad["date"]).dt.date

    bio = _read_parquet(paths["bio_age.parquet"], ("date", "proxy_age", "gap_years", "contributors_json"))

    if score_date not in set(comp["date"]):
        raise SnapshotBuildError(
            paths["composite.parquet"],
            f"No composite.parquet row for {score_date}. Extend parquet writer date range.",
        )

    row_c = comp.loc[comp["date"] == score_date].iloc[-1]

    composite_state = str(row_c["state"])

    headline_state = _COMPOSITE_TO_SNAPSHOT_UI.get(composite_state, "caution")
    insufficient_data = headline_state == "insufficient_data"

    y_prev = score_date - timedelta(days=1)
    row_y = comp.loc[comp["date"] == y_prev]
    sc_now = float(row_c["score"])
    sc_y = float(row_y.iloc[-1]["score"]) if len(row_y) else sc_now

    r_nlr = nlr.loc[nlr["date"] == score_date]
    nlr_d = r_nlr.iloc[-1].to_dict() if len(r_nlr) else {}
    tier_nlr = str(nlr_d.get("tier") or "").lower()

    r_sri = sp.loc[sp["date"] == score_date]
    sri_d = r_sri.iloc[-1].to_dict() if len(r_sri) else {}
    sri_score_raw = pd.to_numeric(sri_d.get("score"), errors="coerce")
    tier_sri = str(sri_d.get("tier") or "").lower()
    if not tier_sri and sri_score_raw == sri_score_raw:
        tier_sri = _tier_from_sri_score(float(sri_score_raw))

    r_d = ad.loc[ad["date"] == score_date]
    ado_d = r_d.iloc[-1].to_dict() if len(r_d) else {}
    tier_ado = str(ado_d.get("tier") or "").lower()

    r_bio = bio.loc[bio["date"] == score_date]
    bio_sr = r_bio.iloc[-1] if len(r_bio) else bio.iloc[-1]

    missing_bits: list[str] = []
    if insufficient_data:
        missing_bits.append(
            "NLR×HRV wedge unknown — fused headline withheld (see refusal reasoning)",
        )
    rn = str(nlr_d.get("reasoning") or "")
    if insufficient_data:
        mb_text = rn.lower()
        if "baseline" in mb_text:
            missing_bits.insert(0, "Wake HRV baseline window")
        if "cbc" in mb_text:
            missing_bits.insert(0, "CBC availability / staleness messaging")
        if tier_sri == "unknown" or not sri_d:
            missing_bits.append("SRI scorer")
        if tier_ado == "unknown" or not ado_d:
            missing_bits.append("Aerobic decoupling")
    uniq: list[str] = []
    for m in missing_bits:
        if m not in uniq:
            uniq.append(m)
    missing_bits = uniq[:6]

    nlr_unknown = tier_nlr == "unknown" or insufficient_data
    sri_unknown = tier_sri == "unknown" or insufficient_data or not sri_d
    ado_unknown = tier_ado == "unknown" or insufficient_data or not ado_d

    display_note, cb_age_days = _nlr_unknown_display(rn)
    bridge_parts = []
    if insufficient_data:
        sri_has_band = bool(sri_d) and tier_sri and tier_sri != "unknown"
        ado_has_band = bool(ado_d) and tier_ado and str(tier_ado).lower() != "unknown"
        if tier_nlr == "unknown" and (sri_has_band or ado_has_band):
            bridge_parts.append(
                "Headline composite requires NLR×HRV (wedge); SRI / aerobic readouts below are "
                "supportive only — do not infer a 0–100 training readiness from partial lenses alone."
            )
        else:
            bridge_parts.append(
                "Composite halted in insufficient-data until flagship inputs converge."
            )
    else:
        bridge_parts.append(str(row_c["reasoning"] or "").split(".")[0] + ".")
        if rn and not rn.startswith(str(bridge_parts[0][:20])):
            bridge_parts.append(rn[:240] + ("…" if len(rn) > 240 else ""))
    if nlr_unknown:
        bridge_parts.insert(0, f"NLR×HRV absent — {(display_note or 'unknown refusal reason')}")
    if cb_age_days and "stale" in (display_note or "").lower():
        bridge_parts.append(f"Laboratory anchor {cb_age_days}d old.")

    subline_clean = " ".join(bridge_parts).strip()
    if not subline_clean:
        subline_clean = (str(row_c.get("reasoning") or "")[:520]).strip()

    today_delta = {"value": round(sc_now - sc_y, 4), "unit": "pts", "vs": "yesterday"}

    action_line = (
        _STATE_ACTION_BRIDGE["insufficient_data"]
        if insufficient_data
        else _STATE_ACTION_BRIDGE.get(composite_state, _STATE_ACTION_BRIDGE["caution"])
    )

    mont_cur, mont_prev = _month_series_mean(comp, score_date)
    if mont_prev is None or mont_prev != mont_prev:
        vs_lm = 0.0
    elif mont_cur != mont_cur:
        vs_lm = 0.0
    else:
        vs_lm = round(float(mont_cur) - float(mont_prev), 4)

    y, mo = score_date.year, score_date.month
    ms, me = _month_dates(y, mo)
    month_human = f"{calendar.month_name[mo]} {y}"

    traj: list[dict[str, Any]] = []
    by_d = {r["date"]: r for _, r in comp.iterrows()}
    walker = ms
    while walker <= me:
        rc = by_d.get(walker)
        st_ui = (
            _COMPOSITE_TO_SNAPSHOT_UI.get(str(rc["state"]), "caution") if rc is not None
            else "insufficient_data"
        )
        sc = float(pd.to_numeric(rc["score"], errors="coerce") or 0) if rc is not None else 0.0
        traj.append({"state": st_ui, "score": round(sc)})
        walker += timedelta(days=1)

    seven_days: list[str] = []
    for k in reversed(range(7)):
        dd = score_date - timedelta(days=k)
        rk = comp.loc[comp["date"] == dd]
        if len(rk):
            seven_days.append(_COMPOSITE_TO_SNAPSHOT_UI.get(str(rk.iloc[-1]["state"]), "caution"))
        else:
            seven_days.append("insufficient_data")

    trends_fp = _trends_dir(rr) / f"{y:04d}-{mo:02d}.json"

    readiness_extra = ""
    if trends_fp.is_file():
        blob = json.loads(trends_fp.read_text(encoding="utf-8"))
        secondary = _trends_secondary(blob)
        if blob.get("trends_ranked_by_effect_size"):
            top = blob["trends_ranked_by_effect_size"][0]
            readiness_extra = f" Leading MoM mover `{top['key']}` Cohen's d≈{top.get('cohens_d')}."
    else:
        secondary = _fallback_secondary(bio_sr.to_dict(), sc_now)

    month_mean_primary = mont_cur if mont_cur == mont_cur else sc_now
    readiness = {
        "score": round(float(month_mean_primary), 4),
        "vsLastMonth": vs_lm,
        "windowLabel": f"{calendar.month_abbr[mo]} {y} cohort",
        "meaning": (
            f"This calendar month composites averaged `{month_mean_primary:.1f}/100`; "
            f"MoM Δ `{vs_lm:+.2f}` vs prior calendar month."
        ),
        "reasoning": readiness_extra.strip(),
    }

    hist = _six_month_hist(comp, score_date)

    parity_target = readiness["score"]
    if hist and round(float(hist[-1]["score"]) - float(parity_target), 6) != 0.0:

        hist[-1]["score"] = round(float(parity_target), 4)

    profile = load_profile_yaml(rr)

    chron_years = float(profile.get("age"))

    breakdown = _bio_breakdown(bio_sr["contributors_json"])

    bio_age_blob = {
        "years": float(bio_sr["proxy_age"]),
        "chronologicalYears": chron_years,
        "meaning": (
            f"Proxy `{float(bio_sr['proxy_age']):.2f}y` vs chronological `{chron_years:.2f}y` "
            f"(Δ {float(bio_sr['gap_years']):+.2f} y)."
        ),
        "reasoning": "Additive transparent pulls enumerated in breakdown — see parquet contributors_json.",
        "breakdown": breakdown,
    }

    div_flags = _parse_divergence_flags(row_c["divergence_flags"])

    drivers_all = _drivers_from_context(rr, score_date, nlr_d)

    dq = _diag_question(insufficient_data, missing_bits)

    divergence_obj: dict[str, Any] = {
        "triggered": bool(insufficient_data or drivers_all),
        "pattern": div_flags[0] if div_flags else ("insufficient_data" if insufficient_data else ""),
        "skillRef": "skills/health-reasoning.md §4 divergence matrix",
        "reasoning": str(row_c.get("reasoning") or ""),
        "drivers": drivers_all,
    }
    if dq is not None:
        divergence_obj["question"] = dq

    nlr_series_tail = nlr.loc[nlr["date"] <= score_date].tail(14)["score"]

    _nlr_sc = pd.to_numeric(nlr_d.get("score"), errors="coerce")
    _nlr_score_clean = float(_nlr_sc) if _nlr_sc == _nlr_sc else 0.0

    flagship_nlr: dict[str, Any] = {
        "score": round(_nlr_score_clean, 4),
        "tier": tier_nlr if tier_nlr in {"green", "caution", "deload"} else "unknown",
        "sparkline": _sparkline(nlr_series_tail.reset_index(drop=True), 14),

        # dataAgeDays: CBC-age when parsable else bounded surrogate (~60d plausible)


        "dataAgeDays": (
            max(1, min(366, int(cb_age_days)))
            if cb_age_days
            else (60 if tier_nlr != "unknown" else 330)
        ),
        "delta": today_delta,

        # reasoning: personalize with numeric refusal wording


        "reasoning": (
            (display_note or rn[:260])
            if nlr_unknown
            else (
                rn.split(";")[0][:520] if rn
                else f"Tier {tier_nlr} readiness fuse from parquet."
            )
        ),

        "displayScore": "—" if nlr_unknown else None,

    }


    sp_tail = pd.to_numeric(sp.loc[sp["date"] <= score_date]["score"], errors="coerce").tail(14)
    flagship_sri: dict[str, Any] = {
        "score": int(round(float(sri_score_raw))) if pd.notna(sri_score_raw) else 0,
        "tier": tier_sri if tier_sri in {"irregular", "moderate", "high"} else "unknown",
        "sparkline": _sparkline(sp_tail.ffill().fillna(0).reset_index(drop=True), 14),

        # windowDays: parquet optional column fallback 14


        "windowDays": int(sri_d.get("window_days") or 14),

        "delta": today_delta,
        "reasoning": (
            (
                (_sri_unknown_reason(str(sri_d.get("reasoning")), tier_sri) or "") if sri_unknown
                else str(sri_d.get("reasoning") or "").split(";")[0]
            )
            or "(no narrative row)"
        ),
        "displayScore": "—" if sri_unknown else None,

    }


    ado_tail = pd.to_numeric(ad.loc[ad["date"] <= score_date]["zscore"], errors="coerce").tail(14)
    ado_z_now = pd.to_numeric(ado_d.get("zscore"), errors="coerce") if ado_d else float("nan")
    flagship_ado = {
        "zscore": float(ado_z_now) if ado_z_now == ado_z_now else 0.0,

        # tier persisted from parquet surrogate


        "tier": ado_d.get("tier") or ("unknown"),
        "sparkline": _sparkline(ado_tail.reset_index(drop=True), 14),
        "windowDays": int(ado_d.get("window_days") or 30),
        "delta": today_delta,
        "reasoning": (
            str(ado_d.get("reasoning") or "")
            if not ado_unknown
            else (_sri_unknown_reason(str(ado_d.get("reasoning")), tier_ado) or "Decoupling lens unknown.")
        ),
        "displayZscore": ("—σ" if ado_unknown else None),

    }

    mo_abbr = calendar.month_abbr[score_date.month]
    env_intervention: MutableMapping[str, Any] = {
        "state": composite_state,
        "readiness_score": round(sc_now, 6),
        "sri_score": float(sri_score_raw) if pd.notna(sri_score_raw) else 0.0,
        "gap_years": float(bio_sr.get("gap_years") or 0),
        "nlr_value": _nlr_numeric_for_rules(nlr_d.get("score"), rn),
        "illness_active": get_active_flags(score_date)["illness"],
        "target_time": "22:45",

        # subjective_energy placeholder pending check-in parquet


        "subjective_energy_1_10": 6,
        "window_label_short": f"{mo_abbr}-{score_date.day} cohort",
    }
    ints_fp = _interventions_dir(rr) / f"{score_date.isoformat()}.json"

    ints = load_interventions_file_or_rank(rr, ints_fp, env_intervention)

    flagship_pruned = _strip_none_shallow({"nlrHrv": flagship_nlr, "sri": flagship_sri, "decoupling": flagship_ado})

    confidence_c = pd.to_numeric(row_c.get("confidence"), errors="coerce")
    conf_disp = float(confidence_c) if confidence_c == confidence_c else float("nan")
    extra_conf = ""
    if conf_disp == conf_disp:
        extra_conf = f" Composite scorer confidence `{conf_disp:.2f}`."

    if insufficient_data:
        today_reason_text = (
            subline_clean
            + extra_conf
            + " Do not extrapolate readiness from headline numbers yet."
        )
    else:
        today_reason_text = str(row_c.get("reasoning") or "").strip()

    payload: dict[str, Any] = {
        "state": headline_state,
        "score": int(round(sc_now)),
        "todayDelta": today_delta,
        "subline": subline_clean,
        "action": action_line,
        "todayReasoning": today_reason_text,
        "monthlyContext": {"readiness": readiness, "bioAge": bio_age_blob},
        "monthlyTrajectory": {
            "month": month_human,
            "days": traj,
            "todayDayOfMonth": score_date.day if ms <= score_date <= me else None,
        },
        "monthlyHistory": hist,
        "sevenDayState": seven_days,
        "secondaryReadouts": secondary,
        "streams": streams_from_parquets(score_date, nlr, ad),
        "flagship": flagship_pruned,
        "divergence": divergence_obj,
        "interventions": ints,
    }
    if insufficient_data:
        payload["todayScoreDisplay"] = "—"
    return payload


def _scrub_nonfinite(obj: Any) -> Any:
    """JSON has no NaN/Inf; coerce to None for strict parsers / TypeScript."""
    if isinstance(obj, dict):
        return {k: _scrub_nonfinite(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_scrub_nonfinite(v) for v in obj]
    if isinstance(obj, float) and (math.isnan(obj) or math.isinf(obj)):
        return None
    return obj


def _json_serialize_default(obj: Any) -> Any:
    if isinstance(obj, date):
        return obj.isoformat()
    raise TypeError(f"unsupported type {type(obj)!r}")


def main() -> None:
    ap = argparse.ArgumentParser(description="Build SnapshotData JSON for web UI.")
    ap.add_argument("--date", required=True, help="Scoring calendar date YYYY-MM-DD")
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--repo-root", type=Path, default=None)
    args = ap.parse_args()
    d = date.fromisoformat(args.date)
    rr = Path(args.repo_root).resolve() if args.repo_root else None
    try:
        blob = build_snapshot(d, repo_root=rr)
    except SnapshotBuildError as err:
        print(str(err), file=sys.stderr)
        sys.exit(1)
    outp = Path(args.out).expanduser().resolve()
    outp.parent.mkdir(parents=True, exist_ok=True)
    clean = _scrub_nonfinite(blob)
    outp.write_text(
        json.dumps(clean, indent=2, ensure_ascii=False, default=_json_serialize_default),
        encoding="utf-8",
    )
    print(f"Wrote {outp}")

    rr = rr if rr is not None else outp.resolve().parent.parent.parent.parent
    profile_default = rr / "profile.yaml"
    profile_path = Path(os.environ.get("HEALTHOS_PROFILE", profile_default)).expanduser()
    skill_path = rr / "skills" / "health-reasoning.md"
    llm_out = rr / "web" / "src" / "data" / "llm_prompt.txt"
    if profile_path.is_file() and skill_path.is_file():
        from src.report.llm_prompt import build_recommendation_prompt

        llm_text = build_recommendation_prompt(outp, profile_path, skill_path)
        llm_out.parent.mkdir(parents=True, exist_ok=True)
        llm_out.write_text(llm_text, encoding="utf-8")
        print(f"Wrote {llm_out}")


if __name__ == "__main__":
    main()
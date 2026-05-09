"""CLI: rank interventions for a calendar date and write JSON under data/interventions/."""

from __future__ import annotations

import argparse
import calendar
import json
import os
from datetime import date
from pathlib import Path

import pandas as pd

from src.context.flags import get_active_flags
from src.interventions.rank import rank_interventions


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _scores_dir() -> Path:
    env = os.environ.get("HEALTHOS_SCORES_DIR")
    if env:
        return Path(env).expanduser().resolve()
    return _repo_root() / "data" / "scores"


def _interventions_dir() -> Path:
    env = os.environ.get("HEALTHOS_INTERVENTIONS_DIR")
    if env:
        return Path(env).expanduser().resolve()
    return _repo_root() / "data" / "interventions"


def _category_for(action: str) -> str:
    a = action.lower()
    if any(w in a for w in ("sleep", "bed", "circadian", "anchor")):
        return "sleep"
    if any(w in a for w in ("train", "zone", "session", "volume", "intensity")):
        return "training"
    if any(w in a for w in ("cbc", "lab", "clinic")):
        return "nutrition"
    return "recovery"


def _build_env(score_date: date) -> dict[str, object]:
    sd = _scores_dir()
    comp = pd.read_parquet(sd / "composite.parquet")
    nlr = pd.read_parquet(sd / "nlr_hrv.parquet")
    sri = pd.read_parquet(sd / "sri.parquet")
    bio = pd.read_parquet(sd / "bio_age.parquet")

    comp["date"] = pd.to_datetime(comp["date"]).dt.date
    nlr["date"] = pd.to_datetime(nlr["date"]).dt.date
    sri["date"] = pd.to_datetime(sri["date"]).dt.date
    bio["date"] = pd.to_datetime(bio["date"]).dt.date

    row_c = comp.loc[comp["date"] == score_date].iloc[-1]
    r_nlr = nlr.loc[nlr["date"] == score_date]
    nlr_d = r_nlr.iloc[-1].to_dict() if len(r_nlr) else {}
    r_sri = sri.loc[sri["date"] == score_date]
    sri_d = r_sri.iloc[-1].to_dict() if len(r_sri) else {}
    r_bio = bio.loc[bio["date"] == score_date]
    bio_sr = r_bio.iloc[-1] if len(r_bio) else bio.iloc[-1]

    meta = {}
    mj = nlr_d.get("meta_json")
    if mj is not None and mj == mj:
        import json as _json

        meta = _json.loads(str(mj))

    nlr_val = float(meta.get("nlr", 2.5))
    sri_raw = pd.to_numeric(sri_d.get("score"), errors="coerce")
    sri_score = float(sri_raw) if sri_raw == sri_raw else 0.0

    mo_abbr = calendar.month_abbr[score_date.month]
    ctx_path = None
    for key in ("HEALTHOS_CONTEXT_FLAGS", "CONTEXT_FLAGS"):
        if os.environ.get(key):
            ctx_path = Path(os.environ[key])
            break

    return {
        "state": str(row_c["state"]),
        "readiness_score": float(row_c["score"]),
        "sri_score": sri_score,
        "sri_value": sri_score,
        "gap_years": float(bio_sr.get("gap_years") or 0),
        "nlr_value": nlr_val,
        "illness_active": bool(get_active_flags(score_date, path=ctx_path)["illness"]),
        "target_time": "22:45",
        "subjective_energy_1_10": 6,
        "window_label_short": f"{mo_abbr}-{score_date.day} cohort",
    }


def _to_snapshot_shape(rows: list[dict[str, object]]) -> list[dict[str, object]]:
    out: list[dict[str, object]] = []
    for i, r in enumerate(rows):
        action = str(r.get("action", ""))
        out.append(
            {
                "action": action,
                "effort": int(r.get("effort") or 2),
                "impact": str(r.get("impact", "MED")),
                "category": _category_for(action),
                "why": str(r.get("why", "")),
                "skillRef": str(r.get("skill_ref", "")),
                "shortcut": f"⌘{i + 1}",
            }
        )
    return out


def main() -> None:
    ap = argparse.ArgumentParser(description="Rank interventions for a date.")
    ap.add_argument("--date", required=True, help="YYYY-MM-DD")
    args = ap.parse_args()

    score_date = date.fromisoformat(args.date)
    env = _build_env(score_date)
    ranked = rank_interventions(env)
    shaped = _to_snapshot_shape(ranked)

    out_dir = _interventions_dir()
    out_dir.mkdir(parents=True, exist_ok=True)
    fp = out_dir / f"{score_date.isoformat()}.json"
    fp.write_text(json.dumps(shaped, indent=2), encoding="utf-8")
    print(fp)


if __name__ == "__main__":
    main()

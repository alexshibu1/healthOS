#!/usr/bin/env python3
"""
evals/run_eval.py

Load human labels from evals/labeled-days.md, run the real ingest pipeline for
NLR×HRV plus **production-parquet SRI and aerobic decoupling** (same row
mapping as ``src.score.composite.score_range_from_parquets``), fuse with
``composite.score_day``, compare to subjective felt recovery, write
``evals/divergence-report.md``.

Does not tune thresholds — surfaces divergence for human review only.
"""

from __future__ import annotations

import argparse
import json
import math
import re
import sys
from datetime import date, timedelta
from pathlib import Path
from typing import Any, Optional

_REPO_ROOT = Path(__file__).resolve().parents[1]
# Allow `python evals/run_eval.py` without installing the package (same as pytest pythonpath).
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

import pandas as pd

from src.ingest.config import RAWDATA_ROOT
from src.ingest.load_all import load_all
from src.context.flags import get_active_flags
from src.score.composite import (
    EfInput,
    NlrHrvInput,
    SriInput,
    _ado_row_to_input,
    _fill_hrv_direction,
    _sri_row_to_input,
    score_day as composite_score_day,
)
from src.score.nlr_hrv_readiness import score_day as nlr_hrv_score_day

_DEFAULT_LABELED = _REPO_ROOT / "evals" / "labeled-days.md"
_DEFAULT_REPORT = _REPO_ROOT / "evals" / "divergence-report.md"
_DEFAULT_SCORES_DIR = _REPO_ROOT / "data" / "scores"

_REQUIRED_PARQUETS = (
    "nlr_hrv.parquet",
    "sri.parquet",
    "aerobic_decoupling.parquet",
)

# Map 1–10 felt to 0–100 for metrics (same interpretability as "8/10 → 80/100").
_FELT_SCALE_DOC = (
    "Felt recovery (1–10 from labeled-days.md) is scaled to 0–100 as "
    "`felt_0_100 = felt_1_10 × 10` for Pearson, Spearman, and MAE vs composite score."
)

_ROW_RE = re.compile(
    r"^\|\s*(\d{4}-\d{2}-\d{2})\s*\|\s*(\d+)\s*\|",
)


def parse_labeled_days(path: Path) -> list[tuple[date, int]]:
    """Parse markdown table rows: | YYYY-MM-DD | felt | ..."""
    out: list[tuple[date, int]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        m = _ROW_RE.match(line.strip())
        if not m:
            continue
        d = date.fromisoformat(m.group(1))
        felt = int(m.group(2))
        if not 1 <= felt <= 10:
            raise ValueError(f"felt_recovery out of 1–10 for {d}: {felt}")
        out.append((d, felt))
    if not out:
        raise ValueError(f"No labeled rows found in {path}")
    out.sort(key=lambda t: t[0])
    return out


def _since_for_baseline(first_labeled: date, buffer_days: int = 45) -> str:
    """Ensure ingest pulls enough history for 7-day HRV baseline before first label."""
    return (first_labeled - timedelta(days=buffer_days)).isoformat()


def _require_flagship_parquets(scores_dir: Path) -> None:
    """
    Pre-condition: production scorer outputs must exist so C2/C3 match the
    fusion path used after ``python -m src.score.{sri,aerobic_decoupling,...}``.
    """
    scores_dir = scores_dir.resolve()
    missing = [name for name in _REQUIRED_PARQUETS if not (scores_dir / name).is_file()]
    if missing:
        rel = scores_dir.relative_to(_REPO_ROOT) if scores_dir.is_relative_to(_REPO_ROOT) else scores_dir
        listing = "\n".join(f"  - {scores_dir / m}" for m in missing)
        raise SystemExit(
            "evals/run_eval.py: required scorer parquet(s) missing.\n"
            f"Expected directory: {scores_dir}\n"
            "Run the ingest + flagship scorers first (e.g. `make demo` steps through "
            "`snapshot_builder`, or score SRI / aerobic_decoupling into "
            f"`{rel}`).\n"
            "Missing:\n"
            f"{listing}"
        )


def _load_score_parquet_indexed(path: Path) -> pd.DataFrame:
    """Read parquet and index by calendar date (one row per date expected)."""
    df = pd.read_parquet(path)
    if "date" not in df.columns:
        raise ValueError(f"{path}: expected a 'date' column")
    df = df.copy()
    df["date"] = pd.to_datetime(df["date"]).dt.date
    return df.set_index("date", drop=False)


def _row_for_scoring_date(df_ix: pd.DataFrame, scoring_date: date) -> pd.Series | None:
    if scoring_date not in df_ix.index:
        return None
    row = df_ix.loc[scoring_date]
    if isinstance(row, pd.DataFrame):
        return row.iloc[0]
    return row


def _input_snapshot(
    scoring_date: date,
    c1_raw: dict,
    c2: SriInput,
    c3: EfInput,
    context_flags: dict[str, bool],
) -> dict[str, Any]:
    """Structured inputs for the markdown report (JSON-friendly)."""
    c1 = NlrHrvInput.from_score_day(c1_raw)
    c3_eff = (
        _fill_hrv_direction(c3, c1)
        if c3.hrv_direction == "unknown" and c1.tier != "unknown"
        else c3
    )
    return {
        "scoring_date": scoring_date.isoformat(),
        "nlr_hrv": {
            "tier": c1_raw.get("tier"),
            "readiness_score": c1_raw.get("score"),
            "confidence": c1_raw.get("confidence"),
            "quality_flags": list(c1_raw.get("quality_flags") or []),
            "meta": dict(c1_raw.get("meta") or {}),
            "reasoning_excerpt": (c1_raw.get("reasoning") or "")[:500],
        },
        "sri": {
            "regularity_band": c2.regularity_band,
            "sri": c2.sri,
            "confidence": c2.confidence,
            "quality_flags": list(c2.quality_flags),
            "note": "C2 from data/scores/sri.parquet via _sri_row_to_input (same as composite parquet join).",
        },
        "decoupling": {
            "decoupling_band": c3_eff.decoupling_band,
            "ef_zscore": c3_eff.ef_zscore,
            "negative_ef_streak_days": c3_eff.negative_ef_streak_days,
            "hrv_direction": c3_eff.hrv_direction,
            "confidence": c3_eff.confidence,
            "quality_flags": list(c3_eff.quality_flags),
            "note": "C3 from data/scores/aerobic_decoupling.parquet via _ado_row_to_input.",
        },
        "context_flags": dict(context_flags),
    }


def run_eval(
    labeled_path: Path,
    report_path: Path,
    rawdata_root: Path,
    baseline_buffer_days: int,
    context_flags_path: Optional[Path],
    scores_dir: Path,
) -> tuple[float, float, float, float, float]:
    """
    Returns (pearson, spearman, mae, pred_std, felt_std); uses NaN for undefined correlations.
    """
    _require_flagship_parquets(scores_dir)
    sri_ix = _load_score_parquet_indexed(scores_dir / "sri.parquet")
    ado_ix = _load_score_parquet_indexed(scores_dir / "aerobic_decoupling.parquet")

    labeled = parse_labeled_days(labeled_path)
    first_d, last_d = labeled[0][0], labeled[-1][0]
    since = _since_for_baseline(first_d, baseline_buffer_days)

    df, episodic = load_all(rawdata_root=rawdata_root, since=since)

    rows: list[dict[str, Any]] = []
    for scoring_date, felt in labeled:
        ctx = get_active_flags(scoring_date, path=context_flags_path)
        c1_raw = nlr_hrv_score_day(
            scoring_date,
            df,
            episodic,
            context_flags=ctx,
            context_flags_path=context_flags_path,
        )
        c1 = NlrHrvInput.from_score_day(c1_raw)
        sri_row = _row_for_scoring_date(sri_ix, scoring_date)
        ado_row = _row_for_scoring_date(ado_ix, scoring_date)
        c2 = _sri_row_to_input(sri_row) if sri_row is not None else SriInput()
        c3 = _ado_row_to_input(ado_row) if ado_row is not None else EfInput()
        comp = composite_score_day(
            scoring_date,
            c1,
            c2,
            c3,
            context_flags=ctx,
            context_flags_path=context_flags_path,
        )
        felt_100 = felt * 10.0
        pred = float(comp.score)
        div = pred - felt_100
        snap = _input_snapshot(scoring_date, c1_raw, c2, c3, ctx)
        rows.append({
            "date": scoring_date,
            "felt_1_10": felt,
            "felt_0_100": felt_100,
            "predicted_composite": pred,
            "divergence": div,
            "composite_state": comp.state,
            "composite_confidence": comp.confidence,
            "primary_signal": comp.primary_signal,
            "divergence_flags": list(comp.divergence_flags),
            "composite_reasoning": comp.reasoning,
            "inputs_snapshot": snap,
        })

    pred_s = pd.Series([r["predicted_composite"] for r in rows], dtype=float)
    felt_s = pd.Series([r["felt_0_100"] for r in rows], dtype=float)

    pearson = pred_s.corr(felt_s, method="pearson")
    spearman = pred_s.corr(felt_s, method="spearman")
    pearson_f = float(pearson) if pearson == pearson else float("nan")
    spearman_f = float(spearman) if spearman == spearman else float("nan")
    mae = float((pred_s - felt_s).abs().mean())
    pred_std = float(pred_s.std(ddof=0))
    felt_std = float(felt_s.std(ddof=0))

    by_div = sorted(rows, key=lambda r: abs(r["divergence"]), reverse=True)
    top5 = by_div[:5]

    scores_rel = (
        scores_dir.resolve().relative_to(_REPO_ROOT)
        if scores_dir.resolve().is_relative_to(_REPO_ROOT)
        else scores_dir.resolve()
    )
    lines: list[str] = [
        "# Divergence report",
        "",
        f"Generated from `{labeled_path.relative_to(_REPO_ROOT)}` using the ingest pipeline "
        f"(`load_all`) for **NLR×HRV**, `{scores_rel}/sri.parquet` and "
        f"`{scores_rel}/aerobic_decoupling.parquet` for **C2/C3** (same "
        f"``_sri_row_to_input`` / ``_ado_row_to_input`` as production parquet join), "
        f"then `src.score.composite.score_day`.",
        "",
        "## Scaling (read this first)",
        "",
        _FELT_SCALE_DOC,
        "",
        "## Summary",
        "",
        f"- Labeled days: **{len(rows)}** ({first_d} → {last_d})",
        f"- Ingest `since`: `{since}` (buffer **{baseline_buffer_days}** d before first label)",
        f"- Scores dir: `{scores_dir.resolve()}`",
        f"- Pearson r (predicted composite vs felt×10): **{pearson_f:.4f}**"
        if not math.isnan(pearson_f)
        else "- Pearson r: **undefined** (zero variance on one or both series)",
        f"- Spearman ρ: **{spearman_f:.4f}**"
        if not math.isnan(spearman_f)
        else "- Spearman ρ: **undefined** (zero variance on one or both series)",
        f"- MAE (on 0–100 scale): **{mae:.4f}**",
        f"- σ(predicted): **{pred_std:.4f}**, σ(felt×10): **{felt_std:.4f}**",
        "",
        "## All days (divergence = predicted − felt×10)",
        "",
        "| date | felt 1–10 | felt×10 | predicted | divergence | state |",
        "|------|------------|---------|-----------|------------|-------|",
    ]
    for r in sorted(rows, key=lambda x: x["date"]):
        lines.append(
            f"| {r['date']} | {r['felt_1_10']} | {r['felt_0_100']:.0f} | "
            f"{r['predicted_composite']:.0f} | {r['divergence']:+.1f} | {r['composite_state']} |"
        )

    lines.extend([
        "",
        "## Top 5 divergences (by |divergence|)",
        "",
    ])

    for i, r in enumerate(top5, 1):
        lines.extend([
            f"### {i}. {r['date']} — divergence **{r['divergence']:+.1f}**",
            "",
            f"- **Felt (1–10):** {r['felt_1_10']} → felt×10 = {r['felt_0_100']:.0f}",
            f"- **Predicted composite:** {r['predicted_composite']:.0f} (state `{r['composite_state']}`, "
            f"confidence {r['composite_confidence']:.4f}, primary `{r['primary_signal']}`)",
            f"- **Divergence flags:** `{json.dumps(r['divergence_flags'])}`",
            "",
            "#### Inputs (NLR×HRV, SRI, decoupling, context)",
            "",
            "```json",
            json.dumps(
                r["inputs_snapshot"], indent=2, default=str, ensure_ascii=False
            ),
            "```",
            "",
            "#### Composite reasoning",
            "",
            r["composite_reasoning"],
            "",
            "---",
            "",
        ])

    lines.append(
        "_No thresholds were auto-tuned. C2/C3 come from disk parquets when the "
        "labeled date exists there; otherwise those lenses fall back to unknown "
        "like a missing join row in production._"
    )

    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text("\n".join(lines), encoding="utf-8")
    print(f"Wrote {report_path}")
    return pearson_f, spearman_f, mae, pred_std, felt_std


def main() -> None:
    p = argparse.ArgumentParser(description="Run labeled-days vs composite eval.")
    p.add_argument(
        "--labeled-days",
        type=Path,
        default=_DEFAULT_LABELED,
        help="Path to labeled-days.md",
    )
    p.add_argument(
        "--out",
        type=Path,
        default=_DEFAULT_REPORT,
        help="Output markdown path",
    )
    p.add_argument(
        "--rawdata-root",
        type=Path,
        default=RAWDATA_ROOT,
        help="rawdata directory (default: config.RAWDATA_ROOT)",
    )
    p.add_argument(
        "--baseline-buffer-days",
        type=int,
        default=45,
        help="Days before first labeled date to pass as load_all(since=...)",
    )
    p.add_argument(
        "--context-flags",
        type=Path,
        default=None,
        help="Override path to context_flags.yaml (default: data/context_flags.yaml)",
    )
    p.add_argument(
        "--scores-dir",
        type=Path,
        default=_DEFAULT_SCORES_DIR,
        help="Directory containing nlr_hrv.parquet, sri.parquet, aerobic_decoupling.parquet",
    )
    args = p.parse_args()
    run_eval(
        labeled_path=args.labeled_days.resolve(),
        report_path=args.out.resolve(),
        rawdata_root=args.rawdata_root.resolve(),
        baseline_buffer_days=args.baseline_buffer_days,
        context_flags_path=args.context_flags.resolve() if args.context_flags else None,
        scores_dir=args.scores_dir.resolve(),
    )


if __name__ == "__main__":
    main()

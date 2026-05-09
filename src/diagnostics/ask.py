"""
Diagnostic question registry and answer log.

Spec: src/diagnostics/spec.md
"""

from __future__ import annotations

import csv
import re
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Mapping

try:
    import yaml  # type: ignore[import-untyped]
except ImportError as e:  # pragma: no cover
    raise ImportError("PyYAML required for diagnostics; pip install pyyaml") from e


_TRIGGER_AND = re.compile(r"\s+AND\s+", re.I)
_DIVERGENCE_CLAUSE = re.compile(r"^divergence=(\w+)$")
_CONFIDENCE_CLAUSE = re.compile(r"^low_confidence_source=(\w+)$")

_ANSWERS_COLS = ["question_id", "answer_value", "ts_utc", "expires_at_utc"]


def _default_questions_path() -> Path:
    return Path(__file__).resolve().parents[2] / "data" / "diagnostic_questions.yaml"


def _default_answers_path() -> Path:
    return Path(__file__).resolve().parents[2] / "data" / "diagnostic_answers.csv"


def _load_questions(path: str | Path | None) -> list[dict[str, Any]]:
    p = Path(path) if path is not None else _default_questions_path()
    raw = yaml.safe_load(p.read_text(encoding="utf-8"))
    return raw.get("questions") or []


def _trigger_matches(trigger: str, snapshot: Mapping[str, Any]) -> bool:
    """Evaluate v1 diagnostic trigger grammar against snapshot."""
    clauses = _TRIGGER_AND.split(trigger.strip())
    for clause in clauses:
        clause = clause.strip()
        if not clause:
            continue
        m_div = _DIVERGENCE_CLAUSE.match(clause)
        if m_div:
            flag_name = m_div.group(1)
            divergence_flags = snapshot.get("divergence_flags") or []
            if flag_name not in divergence_flags:
                return False
            continue
        m_conf = _CONFIDENCE_CLAUSE.match(clause)
        if m_conf:
            source = m_conf.group(1)
            conf = snapshot.get(f"source_confidence_{source}", 1.0)
            if float(conf) >= 0.7:
                return False
            continue
        # Unknown clause form → fail closed
        return False
    return True


def _parse_utc(value: datetime | str) -> datetime:
    if isinstance(value, datetime):
        if value.tzinfo is None:
            raise ValueError("datetime must be timezone-aware UTC")
        return value.astimezone(timezone.utc)
    s = str(value).strip()
    if s.endswith("Z"):
        s = s[:-1] + "+00:00"
    dt = datetime.fromisoformat(s)
    if dt.tzinfo is None:
        raise ValueError(f"timestamp string must include UTC offset: {value!r}")
    return dt.astimezone(timezone.utc)


def get_priority_questions(
    snapshot: dict[str, Any],
    *,
    questions_path: str | Path | None = None,
    limit: int = 3,
) -> list[dict[str, Any]]:
    """
    Return up to ``limit`` questions whose trigger matches ``snapshot``,
    sorted by shift_potential descending.
    """
    questions = _load_questions(questions_path)
    matched = [q for q in questions if _trigger_matches(str(q.get("trigger", "")), snapshot)]
    matched.sort(key=lambda q: float(q.get("shift_potential", 0.0)), reverse=True)
    out = []
    for q in matched[:limit]:
        out.append({
            "id": q["id"],
            "question": q["question"],
            "options": q.get("options", {}),
            "shift_potential": float(q["shift_potential"]),
            "decay_days": int(q["decay_days"]),
        })
    return out


def log_answer(
    question_id: str,
    answer_value: str,
    ts: datetime | str,
    *,
    questions_path: str | Path | None = None,
    answers_path: str | Path | None = None,
) -> Path:
    """
    Validate and append one answer row to ``data/diagnostic_answers.csv``.
    Returns path to the CSV file.
    """
    questions = _load_questions(questions_path)
    q_by_id = {q["id"]: q for q in questions}

    if question_id not in q_by_id:
        raise ValueError(f"unknown question_id: {question_id!r}")
    q = q_by_id[question_id]
    valid_keys = set(q.get("options", {}).keys())
    if answer_value not in valid_keys:
        raise ValueError(
            f"invalid answer {answer_value!r} for {question_id!r}; "
            f"valid options: {sorted(valid_keys)}"
        )

    ts_utc = _parse_utc(ts)
    expires_at_utc = ts_utc + timedelta(days=int(q["decay_days"]))

    fp = Path(answers_path) if answers_path is not None else _default_answers_path()
    fp.parent.mkdir(parents=True, exist_ok=True)

    write_header = not fp.exists() or fp.stat().st_size == 0
    with fp.open("a", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=_ANSWERS_COLS)
        if write_header:
            writer.writeheader()
        writer.writerow({
            "question_id": question_id,
            "answer_value": answer_value,
            "ts_utc": ts_utc.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "expires_at_utc": expires_at_utc.strftime("%Y-%m-%dT%H:%M:%SZ"),
        })
    return fp


def active_diagnostic_flags(
    as_of: date | str,
    *,
    questions_path: str | Path | None = None,
    answers_path: str | Path | None = None,
) -> dict[str, Any]:
    """
    Return merged flag dict from non-expired diagnostic answers.

    Most-recently-logged non-expired answer wins per question_id.
    """
    fp = Path(answers_path) if answers_path is not None else _default_answers_path()
    if not fp.exists():
        return {}

    if isinstance(as_of, str):
        as_of_dt = datetime.fromisoformat(as_of).replace(tzinfo=timezone.utc)
    else:
        as_of_dt = datetime(as_of.year, as_of.month, as_of.day, tzinfo=timezone.utc)

    rows: list[dict[str, str]] = []
    with fp.open(newline="", encoding="utf-8") as fh:
        reader = csv.DictReader(fh)
        for row in reader:
            try:
                exp = _parse_utc(row["expires_at_utc"])
            except (ValueError, KeyError):
                continue
            if exp <= as_of_dt:
                continue
            rows.append(dict(row))

    if not rows:
        return {}

    # Sort newest first; first encountered value per question_id wins
    rows.sort(key=lambda r: r.get("ts_utc", ""), reverse=True)

    questions = _load_questions(questions_path)
    q_by_id = {q["id"]: q for q in questions}

    seen_qids: set[str] = set()
    merged: dict[str, Any] = {}
    for row in rows:
        qid = row.get("question_id", "")
        if qid in seen_qids:
            continue
        seen_qids.add(qid)
        q = q_by_id.get(qid)
        if q is None:
            continue
        answer_val = row.get("answer_value", "")
        effects: dict[str, Any] = (q.get("effects") or {}).get(answer_val) or {}
        for k, v in effects.items():
            if k not in merged:
                merged[k] = v
    return merged


# ── CLI ────────────────────────────────────────────────────────────────────────

def _cli_main() -> None:
    import argparse
    import json

    parser = argparse.ArgumentParser(description="Log a diagnostic answer.")
    parser.add_argument("--question-id", required=True)
    parser.add_argument("--answer", required=True, dest="answer_value")
    args = parser.parse_args()

    now = datetime.now(timezone.utc)
    fp = log_answer(args.question_id, args.answer_value, now)
    print(f"Logged: {args.question_id}={args.answer_value} → {fp}")

    # Snapshot rebuild (best-effort)
    _snapshot_rebuild(now.date())


def _snapshot_rebuild(today: date) -> None:
    scores_parquet = Path(__file__).resolve().parents[2] / "data" / "scores" / "composite.parquet"
    if not scores_parquet.exists():
        print("No prior composite score found; answer logged.")
        return

    try:
        import pandas as pd
        from src.score.composite import (
            CompositeResult,
            EfInput,
            NlrHrvInput,
            SriInput,
            score_day,
        )
    except ImportError as exc:
        print(f"Snapshot rebuild skipped: {exc}")
        return

    try:
        df = pd.read_parquet(scores_parquet)
        if df.empty:
            print("No prior composite score found; answer logged.")
            return

        # Use most recent row for before/after comparison
        latest = df.sort_values("date").iloc[-1]
        score_date = pd.to_datetime(latest["date"]).date()

        # Reconstruct minimal C1 from stored columns
        c1 = NlrHrvInput(
            tier=str(latest.get("state", "unknown")),
            score=None,
            confidence=float(latest.get("confidence", 0.5)),
        )
        before_state = str(latest.get("state", "?"))
        before_score = int(latest.get("score", 0))
        before_conf = float(latest.get("confidence", 0.0))

        diag_flags = active_diagnostic_flags(score_date)
        after = score_day(score_date, c1, diagnostic_flags=diag_flags)

        print(f"\nBefore: state={before_state} score={before_score} confidence={before_conf:.2f}")
        print(f"After:  state={after.state} score={after.score} confidence={after.confidence:.2f}")
        if after.state != before_state:
            print(f"Reasoning: {after.reasoning}")
    except Exception as exc:
        print(f"Snapshot rebuild error (answer still logged): {exc}")


if __name__ == "__main__":
    _cli_main()

"""
Deterministic intervention ranking from YAML lookup triggers.

Spec: src/interventions/spec.md
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Mapping

try:
    import yaml  # type: ignore[import-untyped]
except ImportError as e:  # pragma: no cover
    raise ImportError("PyYAML required for interventions lookup") from e


_RULE_SPLIT = re.compile(r"\s+AND\s+", re.I)
_COMP_RE = re.compile(r"^(\w+)\s*(<=|>=|=|<|>)\s*(.+)$")


class _SafeFormat(dict):
    """Replace unknown placeholders with a sentinel."""

    def __missing__(self, key: str) -> str:
        return f"<missing:{key}>"


def _parse_scalar(raw: str) -> Any:
    s = raw.strip().strip('"').strip("'")
    low = s.lower()
    if low == "true":
        return True
    if low == "false":
        return False
    try:
        if "." in s:
            return float(s)
        return int(s)
    except ValueError:
        return s


def trigger_matches(trigger: str, snapshot: Mapping[str, Any]) -> bool:
    """
    Evaluate trigger DSL (AND-separated clauses).

    Clause forms:
      - field OP value  with OP in = < > <= >=
      - bare field       truthy check on snapshot[field]
    """
    parts = _RULE_SPLIT.split(trigger.strip())
    if not parts or parts == [""]:
        return False
    for part in parts:
        part = part.strip()
        if not part:
            continue
        m = _COMP_RE.match(part)
        if m:
            field, op, rhs_raw = m.group(1), m.group(2), m.group(3).strip()
            lhs = snapshot.get(field)
            rhs = _parse_scalar(rhs_raw)
            try:
                if op == "=":
                    ok = lhs == rhs
                elif op == "<":
                    ok = lhs < rhs  # type: ignore[operator]
                elif op == ">":
                    ok = lhs > rhs  # type: ignore[operator]
                elif op == "<=":
                    ok = lhs <= rhs  # type: ignore[operator]
                elif op == ">=":
                    ok = lhs >= rhs  # type: ignore[operator]
                else:
                    ok = False
            except TypeError:
                ok = False
            if not ok:
                return False
            continue
        # Bare identifier → truthy
        val = snapshot.get(part)
        if not val:
            return False
    return True


_IMPACT_ORDER = {"HIGH": 3, "MED": 2, "LOW": 1}


def _default_lookup_path() -> Path:
    return Path(__file__).resolve().parent / "lookup.yaml"


def rank_interventions(
    snapshot: dict[str, Any],
    *,
    lookup_path: str | Path | None = None,
    limit: int = 3,
) -> list[dict[str, Any]]:
    """
    Load lookup YAML, filter matching rules, return top ``limit`` by impact then effort.
    """
    p = Path(lookup_path) if lookup_path is not None else _default_lookup_path()
    raw = yaml.safe_load(p.read_text(encoding="utf-8"))
    rules = raw.get("rules") or []
    matched: list[dict[str, Any]] = []
    for rule in rules:
        trig = rule.get("trigger")
        if not trig:
            continue
        if not trigger_matches(str(trig), snapshot):
            continue
        matched.append(rule)

    def sort_key(r: dict[str, Any]) -> tuple[int, int]:
        imp = _IMPACT_ORDER.get(str(r.get("impact", "LOW")), 1)
        effort = int(r.get("effort") or 0)
        return (imp, effort)

    matched.sort(key=sort_key, reverse=True)

    out: list[dict[str, Any]] = []
    for rule in matched[:limit]:
        tmpl = str(rule.get("why_template", ""))
        why = tmpl.format_map(_SafeFormat(snapshot))
        out.append(
            {
                "action": rule.get("action", ""),
                "skill_ref": rule.get("skill_ref", ""),
                "effort": int(rule.get("effort") or 0),
                "impact": str(rule.get("impact", "")),
                "why": why,
            }
        )
    return out


def write_interventions_json(
    interventions: list[dict[str, Any]],
    *,
    as_of_date: str,
    out_dir: str | Path | None = None,
) -> Path:
    """Write ``data/interventions/<YYYY-MM-DD>.json``."""
    root = Path(__file__).resolve().parents[2]
    d = Path(out_dir) if out_dir is not None else root / "data" / "interventions"
    d.mkdir(parents=True, exist_ok=True)
    fp = d / f"{as_of_date}.json"
    fp.write_text(json.dumps(interventions, indent=2), encoding="utf-8")
    return fp

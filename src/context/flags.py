"""
Context flags — ``data/context_flags.yaml``.

YAML schema (top-level mapping):

+------------------+-------------------------------------------------------+
| Key              | Value                                                  |
+==================+=======================================================+
| illness_windows  | list of windows                                       |
+------------------+-------------------------------------------------------+
| travel_windows   | list of windows                                       |
+------------------+-------------------------------------------------------+
| injury_windows   | list of windows                                       |
+------------------+-------------------------------------------------------+

Each window object::

    start: YYYY-MM-DD          # required — inclusive calendar date
    end: YYYY-MM-DD            # required — inclusive calendar date
    note: optional free text   # narrative only; scorers may ignore

Missing lists default to ``[]``. Unknown top-level keys are ignored.

Contract:

- ``load_context_flags(path)``: parses YAML into internal structures.
- ``get_active_flags(date, context=None, *, path=None)``: returns::

      {"illness": bool, "travel": bool, "injury": bool}

  ``True`` when ``date`` falls inside **any** window for that category
  (inclusive ``start`` and ``end``). Dates may be ``datetime.date`` or
  ISO strings ``YYYY-MM-DD``.

Call once per scoring date from scorers; no decay or expiry logic here.
"""

from __future__ import annotations

import os
from datetime import date, datetime
from pathlib import Path
from typing import Any, Mapping, Sequence

try:
    import yaml  # type: ignore[import-untyped]
except ImportError as e:  # pragma: no cover
    raise ImportError(
        "context flags require PyYAML; install with: pip install pyyaml"
    ) from e


def _default_flags_path() -> Path:
    for key in ("HEALTHOS_CONTEXT_FLAGS", "CONTEXT_FLAGS"):
        env = os.environ.get(key)
        if env:
            return Path(env).expanduser().resolve()
    return Path(__file__).resolve().parents[2] / "data" / "context_flags.yaml"


def _parse_day(value: Any, ctx: str) -> date:
    if isinstance(value, date) and not isinstance(value, datetime):
        return value
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, str):
        return date.fromisoformat(value.strip())
    raise ValueError(f"{ctx}: expected date or ISO string, got {type(value).__name__}")


def _normalize_day(value: date | str) -> date:
    if isinstance(value, date):
        return value
    return date.fromisoformat(str(value).strip())


def load_context_flags(path: Path | None = None) -> dict[str, list[dict[str, Any]]]:
    """Load YAML into ``illness_windows``, ``travel_windows``, ``injury_windows`` lists."""

    p = path if path is not None else _default_flags_path()
    raw = yaml.safe_load(p.read_text(encoding="utf-8"))
    if raw is None:
        raw = {}
    if not isinstance(raw, Mapping):
        raise ValueError(
            f"context_flags root must be a mapping, got {type(raw).__name__}"
        )

    def windows(key: str) -> list[dict[str, Any]]:
        w = raw.get(key, [])
        if w is None:
            return []
        if not isinstance(w, Sequence) or isinstance(w, (str, bytes)):
            raise ValueError(f"{key}: expected a list")
        out: list[dict[str, Any]] = []
        for i, item in enumerate(w):
            if not isinstance(item, Mapping):
                raise ValueError(f"{key}[{i}]: expected mapping")
            if "start" not in item or "end" not in item:
                raise ValueError(f"{key}[{i}]: requires start and end")
            out.append(dict(item))
        return out

    return {
        "illness_windows": windows("illness_windows"),
        "travel_windows": windows("travel_windows"),
        "injury_windows": windows("injury_windows"),
    }


def get_active_flags(
    scoring_date: date | str,
    context: Mapping[str, Any] | None = None,
    *,
    path: Path | None = None,
) -> dict[str, bool]:
    """
    Return whether ``scoring_date`` lies inside any illness / travel /
    injury window.
    """

    ctx = context if context is not None else load_context_flags(path)
    day = _normalize_day(scoring_date)

    def active(windows_key: str) -> bool:
        for i, win in enumerate(ctx[windows_key]):
            try:
                start = _parse_day(win["start"], f"{windows_key}[{i}].start")
                end = _parse_day(win["end"], f"{windows_key}[{i}].end")
            except KeyError as e:
                raise ValueError(f"{windows_key}[{i}]: missing {e}") from e
            if start > end:
                raise ValueError(
                    f"{windows_key}[{i}]: start {start} after end {end}"
                )
            if start <= day <= end:
                return True
        return False

    return {
        "illness": active("illness_windows"),
        "travel": active("travel_windows"),
        "injury": active("injury_windows"),
    }

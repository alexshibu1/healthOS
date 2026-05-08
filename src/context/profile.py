"""
Profile loader — ``data/profile.yaml``.

YAML schema (all keys required, scalar types as stated):

+------------------------------+----------------------------------------+
| Field                        | Type / notes                           |
+==============================+========================================+
| age                          | int                                    |
+------------------------------+----------------------------------------+
| sex                          | str (free text, e.g. male/female)      |
+------------------------------+----------------------------------------+
| weight_kg                    | float or int                           |
+------------------------------+----------------------------------------+
| height_cm                    | float or int                           |
+------------------------------+----------------------------------------+
| primary_training_modality    | str (e.g. running, lifting, mixed)     |
+------------------------------+----------------------------------------+
| primary_goal                 | str (e.g. longevity, race prep)        |
+------------------------------+----------------------------------------+

Contract:

- ``load_profile(path) -> Profile``: reads YAML, validates required keys,
  returns a frozen snapshot dataclass. No baseline computation and no
  derived fields.

Rejected loads raise ``ValueError`` with a message naming the problem.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

try:
    import yaml  # type: ignore[import-untyped]
except ImportError as e:  # pragma: no cover
    raise ImportError(
        "profile loader requires PyYAML; install with: pip install pyyaml"
    ) from e

_REQUIRED_KEYS = (
    "age",
    "sex",
    "weight_kg",
    "height_cm",
    "primary_training_modality",
    "primary_goal",
)


def _default_profile_path() -> Path:
    # .../healthOS/src/context/profile.py → repo root is parents[2]
    return Path(__file__).resolve().parents[2] / "data" / "profile.yaml"


@dataclass(frozen=True)
class Profile:
    age: int
    sex: str
    weight_kg: float
    height_cm: float
    primary_training_modality: str
    primary_goal: str


def load_profile(path: Path | None = None) -> Profile:
    """Load ``profile.yaml`` and return a :class:`Profile`."""

    p = path if path is not None else _default_profile_path()
    raw_text = p.read_text(encoding="utf-8")
    data = yaml.safe_load(raw_text)
    if not isinstance(data, Mapping):
        raise ValueError(f"profile root must be a mapping, got {type(data).__name__}")

    missing = [k for k in _REQUIRED_KEYS if k not in data or data[k] is None]
    if missing:
        raise ValueError(f"profile missing required field(s): {', '.join(missing)}")

    try:
        return Profile(
            age=_coerce_int(data["age"], "age"),
            sex=_coerce_str(data["sex"], "sex"),
            weight_kg=_coerce_float(data["weight_kg"], "weight_kg"),
            height_cm=_coerce_float(data["height_cm"], "height_cm"),
            primary_training_modality=_coerce_str(
                data["primary_training_modality"],
                "primary_training_modality",
            ),
            primary_goal=_coerce_str(data["primary_goal"], "primary_goal"),
        )
    except ValueError:
        raise
    except Exception as e:  # noqa: BLE001 — bubble up as ValueError
        raise ValueError(f"invalid profile field: {e}") from e


def _coerce_int(v: Any, name: str) -> int:
    if isinstance(v, bool):
        raise ValueError(f"{name}: expected int, got bool")
    try:
        return int(v)
    except (TypeError, ValueError) as e:
        raise ValueError(f"{name}: expected int coercible value, got {v!r}") from e


def _coerce_float(v: Any, name: str) -> float:
    if isinstance(v, bool):
        raise ValueError(f"{name}: expected float, got bool")
    try:
        return float(v)
    except (TypeError, ValueError) as e:
        raise ValueError(f"{name}: expected numeric value, got {v!r}") from e


def _coerce_str(v: Any, name: str) -> str:
    if not isinstance(v, str):
        raise ValueError(f"{name}: expected str, got {type(v).__name__}")
    s = v.strip()
    if not s:
        raise ValueError(f"{name}: empty string not allowed")
    return s

"""
src/ingest/schema.py — unified observation model.

The authoritative field definitions, nullability rules, and validation
invariants live in src/ingest/schema.md.  This module is the Python
representation of that spec — it does not add logic not in the spec.

All loaders in src/ingest/<source>/ must import from here.
The scoring layer in src/score/ reads Observation objects produced here.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from typing import Optional


# ── core observation row ──────────────────────────────────────────────────────

@dataclass
class Observation:
    """
    One row in the unified observation table.  Every field maps 1-to-1 to
    a column in schema.md §Core observation table.

    Required fields (no default) must be set by every loader.
    Optional fields default to None / empty list / empty dict.
    ingested_at_utc is stamped automatically at construction time.
    """

    # provenance — required
    observation_id:   str
    source:           str          # enum: amazfit | strava | jefit | blood_panel | manual
    source_file:      str          # path relative to rawdata/
    source_section:   Optional[str]
    source_row_id:    str

    # cadence and type — required
    cadence_kind:     str          # stream | event
    metric_kind:      str          # snake_case, see schema.md §metric_kind catalog

    # time — required
    ts_utc:           datetime     # UTC-aware; for intervals, this is the start
    tz_original:      str          # IANA name or fixed offset; never empty
    ts_original:      str          # verbatim source string; the audit trail

    # confidence — required
    source_confidence: float       # [0.0, 1.0]; per schema.md §Source confidence ladder

    # links — optional
    parent_event_id:  Optional[str]   = None
    ts_end_utc:       Optional[datetime] = None   # for interval observations

    # value — optional; exactly one of numeric/text should be non-null per row
    value_numeric:    Optional[float]  = None
    value_unit:       Optional[str]    = None     # canonical unit; required when value_numeric set
    value_text:       Optional[str]    = None     # for categorical observations

    # metadata — optional
    quality_flags:    list[str]        = field(default_factory=list)
    payload:          dict             = field(default_factory=dict)
    ingested_at_utc:  datetime         = field(
        default_factory=lambda: datetime.now(timezone.utc)
    )


# ── reject row ────────────────────────────────────────────────────────────────

@dataclass
class Reject:
    """
    Row that failed validation.  Goes to rejects/ table, never silently dropped.
    See schema.md §Validation contract invariant 8.
    """
    source:           str
    source_file:      str
    source_row_id:    str
    raw_row:          dict          # the original CSV row dict, unmodified
    reasons:          list[str]     # one string per violated invariant
    ingested_at_utc:  datetime      = field(
        default_factory=lambda: datetime.now(timezone.utc)
    )


# ── deterministic ID ──────────────────────────────────────────────────────────

def make_observation_id(
    source:         str,
    source_file:    str,
    source_section: Optional[str],
    source_row_id:  str,
    metric_kind:    str,
) -> str:
    """
    16-char hex ID, deterministic from provenance fields.

    Formula (schema.md §Identity rule):
        sha1("{source}|{source_file}|{source_section or ''}|{source_row_id}|{metric_kind}")[:16]

    Same inputs → same ID.  Re-ingesting the same file is idempotent:
    "insert or replace" on observation_id produces no duplicates.
    """
    key = f"{source}|{source_file}|{source_section or ''}|{source_row_id}|{metric_kind}"
    return hashlib.sha1(key.encode()).hexdigest()[:16]


# ── validation ────────────────────────────────────────────────────────────────

def validate_observation(obs: Observation) -> list[str]:
    """
    Assert the 8 invariants from schema.md §Validation contract.

    Returns a list of violation strings.  Empty list → observation is valid.
    Loaders call this on every row; failures go to Reject, not to the table.
    """
    errors: list[str] = []

    # 1. observation_id must be non-empty
    if not obs.observation_id:
        errors.append("observation_id is empty")

    # 2. ts_utc must be UTC-aware with zero offset
    if obs.ts_utc.tzinfo is None:
        errors.append(f"ts_utc has no tzinfo: {obs.ts_utc!r}")
    elif obs.ts_utc.utcoffset() != timedelta(0):
        errors.append(
            f"ts_utc is not UTC (offset={obs.ts_utc.utcoffset()}): {obs.ts_utc!r}"
        )

    # 3. ts_end_utc, when present, must be UTC-aware and not before ts_utc
    if obs.ts_end_utc is not None:
        if obs.ts_end_utc.tzinfo is None:
            errors.append(f"ts_end_utc has no tzinfo: {obs.ts_end_utc!r}")
        elif obs.ts_end_utc.utcoffset() != timedelta(0):
            errors.append(
                f"ts_end_utc is not UTC (offset={obs.ts_end_utc.utcoffset()}): {obs.ts_end_utc!r}"
            )
        # allow start == end (zero-duration sentinel rows are flagged, not rejected)
        if obs.ts_end_utc < obs.ts_utc:
            errors.append(
                f"ts_end_utc {obs.ts_end_utc!r} is before ts_utc {obs.ts_utc!r}"
            )

    # 4. tz_original must be non-empty
    if not obs.tz_original:
        errors.append("tz_original is empty")

    # 5. ts_original must be non-empty (the audit trail)
    if not obs.ts_original:
        errors.append("ts_original is empty")

    # 6. value_numeric implies value_unit; they must not be inconsistent
    if obs.value_numeric is not None and obs.value_unit is None:
        errors.append("value_numeric is set but value_unit is None")

    # 7. value_text and value_numeric are mutually exclusive
    if obs.value_text is not None and obs.value_numeric is not None:
        errors.append(
            "value_text and value_numeric are both non-null; "
            "a row carries either a numeric measurement or a categorical label, not both"
        )

    # 8. source_confidence must be in [0.0, 1.0]
    if not (0.0 <= obs.source_confidence <= 1.0):
        errors.append(
            f"source_confidence {obs.source_confidence!r} is outside [0.0, 1.0]"
        )

    # 9. cadence_kind must be a known value
    if obs.cadence_kind not in ("stream", "event"):
        errors.append(
            f"cadence_kind must be 'stream' or 'event', got {obs.cadence_kind!r}"
        )

    return errors

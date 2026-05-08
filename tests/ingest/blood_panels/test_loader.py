"""
tests/ingest/blood_panels/test_loader.py
Blood panel markdown loader tests (fixture copied from real panel format).
"""

from datetime import datetime, timezone
from pathlib import Path

import pytest

from src.ingest.blood_panels.loader import load

FIXTURES = Path(__file__).parent / "fixtures"
PANEL_MD = FIXTURES / "blood_panels" / "food_poisoning_panel.md"

EXPECTED_FM_FLAGS = frozenset({
    "drawn_during_illness",
    "date_unconfirmed",
    "lab_unknown",
    "non_baseline",
})

EXPECTED_SECTION_COUNTS = {
    "cbc": 10,
    "white_blood_cell_differential": 5,
    "absolute_cell_counts": 6,
    "kidney_metabolic_panel": 4,
    "electrolytes": 5,
}


def _load():
    return load(PANEL_MD, rawdata_root=FIXTURES)


def test_frontmatter_draw_date_maps_to_ts_utc_midnight():
    """draw_date (ISO) → ts_utc at 00:00:00 UTC for parent and components."""
    obs, rej = _load()
    assert not rej
    expected = datetime(2025, 6, 15, 0, 0, 0, tzinfo=timezone.utc)
    for o in obs:
        assert o.ts_utc == expected
        assert o.ts_original == "2025-06-15"


def test_five_sections_and_component_count():
    """All five analyte sections present; data rows match expected totals."""
    obs, rej = _load()
    assert not rej
    parent = next(o for o in obs if o.metric_kind == "blood_panel_draw")
    sections = set(parent.payload.get("sections_present", []))
    assert sections == set(EXPECTED_SECTION_COUNTS.keys())

    components = [o for o in obs if o.metric_kind == "blood_panel_analyte"]
    assert len(components) == sum(EXPECTED_SECTION_COUNTS.values())

    by_section: dict[str, int] = {}
    for c in components:
        assert c.source_section is not None
        by_section[c.source_section] = by_section.get(c.source_section, 0) + 1
    assert by_section == EXPECTED_SECTION_COUNTS


def test_nlr_not_stored():
    """Computed NLR/PLR/SII live in narrative only — no observation rows."""
    obs, rej = _load()
    assert not rej
    for o in obs:
        assert "nlr" not in o.metric_kind.lower()
        slug = (o.payload or {}).get("analyte_slug") or ""
        assert "nlr" not in slug.lower()
        name = (o.payload or {}).get("marker_display_name") or ""
        assert name.strip().upper() != "NLR"


def test_quality_flags_propagate_from_frontmatter():
    """Frontmatter quality_flags appear on parent and every component."""
    obs, rej = _load()
    assert not rej
    for o in obs:
        assert EXPECTED_FM_FLAGS.issubset(set(o.quality_flags)), (
            f"missing flags on {o.metric_kind} {o.source_row_id}: {o.quality_flags!r}"
        )


def test_special_notation_preserved_in_payload():
    """Censored / approximate lab notation stays auditable in payload."""
    obs, rej = _load()
    assert not rej
    by_slug = {
        o.payload["analyte_slug"]: o
        for o in obs
        if o.metric_kind == "blood_panel_analyte"
    }

    egfr = by_slug["egfr"]
    assert egfr.payload["original_value_str"] == ">90 (estimated)"
    assert egfr.payload["value_qualifier"] == ">"
    assert egfr.value_numeric == pytest.approx(90.0)

    ag = by_slug["anion_gap"]
    assert ag.payload["original_value_str"] == "~11"
    assert ag.payload["value_qualifier"] == "~"
    assert ag.value_numeric == pytest.approx(11.0)

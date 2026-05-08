"""
tests/ingest/amazfit/test_body_loader.py
Tests for the Amazfit BODY loader.
"""

from pathlib import Path

import pytest

from src.ingest.amazfit.body_loader import load

FIXTURES  = Path(__file__).parent / "fixtures"
BODY_CSV  = FIXTURES / "body_fixture.csv"
ROOT      = FIXTURES


def test_load_returns_4_observations():
    """4 data rows → 4 observations, no rejects."""
    obs, rej = load(BODY_CSV, rawdata_root=ROOT)
    assert len(obs) == 4
    assert len(rej) == 0


def test_weight_kg_parsed_correctly():
    """
    Row 1: weight=69.5 → value_numeric=69.5, value_unit='kg'.
    Row 3: weight=72.4 → value_numeric=72.4.
    """
    obs, _ = load(BODY_CSV, rawdata_root=ROOT)
    # observations are in file order
    assert obs[0].value_numeric == pytest.approx(69.5)
    assert obs[2].value_numeric == pytest.approx(72.4)
    for o in obs:
        assert o.value_unit == "kg"
        assert o.metric_kind == "body_weight"


def test_height_mismatch_flag_for_height_158():
    """
    Rows with height=158.0 (≠ 166.0 expected) must carry 'height_mismatch' flag.
    Rows with height=166.0 must NOT carry it.
    """
    obs, _ = load(BODY_CSV, rawdata_root=ROOT)
    # rows 0 and 1 have height=158.0; rows 2 and 3 have height=166.0
    assert "height_mismatch" in obs[0].quality_flags
    assert "height_mismatch" in obs[1].quality_flags
    assert "height_mismatch" not in obs[2].quality_flags
    assert "height_mismatch" not in obs[3].quality_flags


def test_body_comp_null_strings_become_none_in_payload():
    """
    All body composition fields arrive as literal 'null' in the fixture.
    They must be stored as None in the payload, not as the string 'null'.
    """
    obs, _ = load(BODY_CSV, rawdata_root=ROOT)
    comp_fields = ("fatRate", "bodyWaterRate", "boneMass",
                   "metabolism", "muscleRate", "visceralFat")
    for o in obs:
        for field in comp_fields:
            assert field in o.payload
            assert o.payload[field] is None, (
                f"Expected None for {field}, got {o.payload[field]!r}"
            )


def test_observation_ids_are_deterministic():
    """Two loads of the same file produce identical observation_ids."""
    obs1, _ = load(BODY_CSV, rawdata_root=ROOT)
    obs2, _ = load(BODY_CSV, rawdata_root=ROOT)
    assert [o.observation_id for o in obs1] == [o.observation_id for o in obs2]

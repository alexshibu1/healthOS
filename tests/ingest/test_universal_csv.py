"""Tests for ``src.ingest.universal_csv.loader``."""

from __future__ import annotations

from pathlib import Path

import pytest

from src.ingest.universal_csv.loader import load


def _write(tmp: Path, content: str) -> Path:
    p = tmp / "universal.csv"
    p.write_text(content, encoding="utf-8")
    return p


def test_full_row_all_columns_observation_count(tmp_path: Path) -> None:
    csv_text = """date,hrv_ms,rhr_bpm,sleep_onset,sleep_offset,sleep_hours,steps,weight_kg,workout_type,workout_distance_m,workout_moving_time_s,workout_avg_hr,workout_avg_pace_s_per_km,neutrophils_abs,lymphocytes_abs,monocytes_abs,glucose_mmol,notes
2026-05-09,45,52,2026-05-08T23:00:00,2026-05-09T07:00:00,8,9000,71.5,run,5000,2400,145,360,10.2,1.9,1.2,5.4,demo note
"""
    p = _write(tmp_path, csv_text)
    obs, rej = load(p, rawdata_root=tmp_path)
    assert not rej
    # hrv, rhr, activity_steps, blood_glucose, body_weight, sleep_summary,
    # workout_session + 4 components, blood_panel_draw + 3 analytes
    assert len(obs) == 15
    hrv_obs = [o for o in obs if o.metric_kind == "hrv"]
    assert len(hrv_obs) == 1
    assert hrv_obs[0].value_numeric == pytest.approx(45)


def test_hrv_ms_emits_metric_kind_hrv_not_hr(tmp_path: Path) -> None:
    """Regression: NLR×HRV scorer filters metric_kind == hrv (see nlr_hrv_readiness)."""
    csv_text = """date,hrv_ms
2026-05-09,48
"""
    p = _write(tmp_path, csv_text)
    obs, rej = load(p, rawdata_root=tmp_path)
    assert not rej
    assert len(obs) == 1
    assert obs[0].metric_kind == "hrv"
    assert obs[0].value_unit == "ms"


def test_blank_cbc_no_blood_panel_draw(tmp_path: Path) -> None:
    csv_text = """date,neutrophils_abs,lymphocytes_abs,monocytes_abs
2026-05-09,,,
"""
    p = _write(tmp_path, csv_text)
    obs, rej = load(p, rawdata_root=tmp_path)
    assert not rej
    kinds = {o.metric_kind for o in obs}
    assert "blood_panel_draw" not in kinds
    assert "blood_panel_analyte" not in kinds


def test_nlr_derivation_inputs_not_stored_as_nlr_metric(tmp_path: Path) -> None:
    csv_text = """date,neutrophils_abs,lymphocytes_abs,monocytes_abs
2026-03-28,10.2,1.9,1.2
"""
    p = _write(tmp_path, csv_text)
    obs, rej = load(p, rawdata_root=tmp_path)
    assert not rej
    assert all(o.metric_kind.lower() != "nlr" for o in obs)
    n_row = next(
        o
        for o in obs
        if o.metric_kind == "blood_panel_analyte"
        and o.payload.get("analyte_slug") == "neutrophils_abs"
    )
    l_row = next(
        o
        for o in obs
        if o.metric_kind == "blood_panel_analyte"
        and o.payload.get("analyte_slug") == "lymphocytes_abs"
    )
    assert n_row.value_numeric == pytest.approx(10.2)
    assert l_row.value_numeric == pytest.approx(1.9)
    ratio = n_row.value_numeric / l_row.value_numeric
    assert ratio == pytest.approx(10.2 / 1.9, rel=1e-9)
    assert ratio == pytest.approx(5.37, abs=0.02)


def test_date_only_steps_one_activity_steps(tmp_path: Path) -> None:
    csv_text = """date,steps
2026-05-09,8421
"""
    p = _write(tmp_path, csv_text)
    obs, rej = load(p, rawdata_root=tmp_path)
    assert not rej
    assert len(obs) == 1
    assert obs[0].metric_kind == "activity_steps"


def test_blank_date_rejects(tmp_path: Path) -> None:
    csv_text = """date,steps
,100
"""
    p = _write(tmp_path, csv_text)
    obs, rej = load(p, rawdata_root=tmp_path)
    assert obs == []
    assert len(rej) == 1
    assert "missing_date" in rej[0].reasons

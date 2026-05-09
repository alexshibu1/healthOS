"""
tests/score/test_composite.py

Tests for src/score/composite.py — three-lens state-first composite readiness scorer.
Spec: src/score/specs/composite-spec.md

Coverage:
  §1  — state classification (one test per state, checked in priority order)
  §2  — five real-day scenarios using real NLR and context_flags.yaml windows
  §3  — supporting unit tests (band bounds, divergence flags, confidence, helpers)
"""

from __future__ import annotations

import math
from datetime import date
from pathlib import Path

import pytest

from src.score.composite import (
    CompositeResult,
    EfInput,
    NlrHrvInput,
    SriInput,
    _STATE_BANDS,
    _detect_divergences,
    _detect_recent_illness,
    _fill_hrv_direction,
    _score_in_band,
    score_day,
)

# Real context_flags.yaml — illness window 2025-06-08 → 2025-06-29
_FLAGS_PATH = Path(__file__).resolve().parents[2] / "data" / "context_flags.yaml"

# Convenience flag dicts so synthetic tests never touch the YAML
_NO_ILLNESS = {"illness": False, "travel": False, "injury": False}
_ACTIVE_ILLNESS = {"illness": True, "travel": False, "injury": False}


# ══════════════════════════════════════════════════════════════════════════════
# §1  State classification — one test per state (priority-order)
# ══════════════════════════════════════════════════════════════════════════════


class TestStateClassification:
    """
    Each test drives score_day() with synthetic inputs that should trigger
    exactly one state.  Both state label AND primary_signal are asserted.
    """

    def test_illness_risk(self):
        """
        Rule 1 (highest priority): illness_flag=True + C1.tier ∈ {deload,caution}
        → illness-risk regardless of C2/C3.
        """
        c1 = NlrHrvInput(
            tier="deload", score=2.5, confidence=0.80,
            nlr_term=1.8, hrv_term=1.2,
        )
        result = score_day(
            date(2025, 6, 15), c1,
            context_flags=_ACTIVE_ILLNESS, recent_illness=False,
        )
        assert result.state == "illness-risk"
        assert result.primary_signal == "context"
        lo, hi = _STATE_BANDS["illness-risk"]
        assert lo <= result.score <= hi, f"score {result.score} outside [{lo},{hi}]"

    def test_autonomic_recovery_leading(self):
        """
        Rule 2 (checked BEFORE deload): C1.tier=deload, NLR elevated (nlr_term>1.0),
        HRV already improving (hrv_term<1.0), C3.decoupling_band not central
        → autonomic-recovery-leading (skill §1.2: wearable leads blood).
        """
        # nlr_term=1.40 > 1.0 (elevated); hrv_term=0.85 < 1.0 (improving)
        c1 = NlrHrvInput(
            tier="deload", score=1.8, confidence=0.75,
            nlr_term=1.40, hrv_term=0.85,
        )
        c3 = EfInput(decoupling_band="good", hrv_direction="up", confidence=0.80)
        result = score_day(
            date(2025, 4, 15), c1, c3=c3,
            context_flags=_NO_ILLNESS, recent_illness=False,
        )
        assert result.state == "autonomic-recovery-leading"
        assert result.primary_signal == "nlr_hrv"
        lo, hi = _STATE_BANDS["autonomic-recovery-leading"]
        assert lo <= result.score <= hi

    def test_deload(self):
        """
        Rule 3: C1.tier=deload, NLR elevated but HRV NOT improving
        (hrv_term > 1.0 → today below baseline).
        Rule 2 is bypassed because hrv_improving=False.
        """
        # nlr_term=1.5 > 1.0 (elevated); hrv_term=1.15 > 1.0 (declining, not improving)
        c1 = NlrHrvInput(
            tier="deload", score=2.0, confidence=0.80,
            nlr_term=1.5, hrv_term=1.15,
        )
        result = score_day(
            date(2025, 7, 10), c1,
            context_flags=_NO_ILLNESS, recent_illness=False,
        )
        assert result.state == "deload"
        assert result.primary_signal == "nlr_hrv"
        lo, hi = _STATE_BANDS["deload"]
        assert lo <= result.score <= hi

    def test_peripheral_strain(self):
        """
        Rule 4: C1.tier=green, C3.decoupling_band=high, C3.hrv_direction=up
        → peripheral-strain (skill §3.2: EF↓ + HRV↑ → peripheral/environmental).
        """
        c1 = NlrHrvInput(
            tier="green", score=0.6, confidence=0.90,
            nlr_term=0.7, hrv_term=0.90,
        )
        # Provide hrv_direction explicitly; _fill_hrv_direction only runs for "unknown"
        c3 = EfInput(decoupling_band="high", hrv_direction="up", confidence=0.80)
        result = score_day(
            date(2025, 8, 20), c1, c3=c3,
            context_flags=_NO_ILLNESS, recent_illness=False,
        )
        assert result.state == "peripheral-strain"
        assert result.primary_signal == "ef"
        lo, hi = _STATE_BANDS["peripheral-strain"]
        assert lo <= result.score <= hi

    def test_accumulating_fatigue_via_ef_streak(self):
        """
        Rule 5a: C3.negative_ef_streak_days ≥ 5 → accumulating-fatigue (ef).
        C3.decoupling_band=good so Rule 4 (peripheral-strain) does not fire first.
        """
        c1 = NlrHrvInput(
            tier="green", score=0.9, confidence=0.80,
            nlr_term=0.8, hrv_term=0.97,
        )
        c3 = EfInput(
            decoupling_band="good", negative_ef_streak_days=5, confidence=0.70,
        )
        result = score_day(
            date(2025, 9, 1), c1, c3=c3,
            context_flags=_NO_ILLNESS, recent_illness=False,
        )
        assert result.state == "accumulating-fatigue"
        assert result.primary_signal == "ef"
        lo, hi = _STATE_BANDS["accumulating-fatigue"]
        assert lo <= result.score <= hi

    def test_accumulating_fatigue_via_caution_irregular(self):
        """
        Rule 5b: C1.tier=caution AND C2.regularity_band=irregular → accumulating-fatigue.
        primary_signal=convergent (dual-moderate lens agreement).

        nlr_term=1.10 (elevated) but hrv_term=1.02 (HRV slightly below baseline →
        hrv_improving=False), so Rule 2 (autonomic-recovery-leading) is bypassed.
        """
        c1 = NlrHrvInput(
            tier="caution",
            score=round(1.10 * 1.02, 4),  # 1.122 → caution
            confidence=0.75,
            nlr_term=1.10,  # elevated
            hrv_term=1.02,  # not improving (> 1.0) → Rule 2 bypassed
        )
        c2 = SriInput(regularity_band="irregular", confidence=0.80)
        c3 = EfInput(decoupling_band="good", confidence=0.80)
        result = score_day(
            date(2025, 9, 5), c1, c2=c2, c3=c3,
            context_flags=_NO_ILLNESS, recent_illness=False,
        )
        assert result.state == "accumulating-fatigue"
        assert result.primary_signal == "convergent"

    def test_cleared(self):
        """
        Rule 6: recent_illness=True AND C1.tier=green AND C3=good
        → cleared (post-illness, all systems normalising).
        Uses direct override for recent_illness to avoid YAML dependency.
        """
        c1 = NlrHrvInput(
            tier="green", score=0.5, confidence=0.90,
            nlr_term=0.8, hrv_term=0.97,
        )
        result = score_day(
            date(2025, 7, 5), c1,
            context_flags=_NO_ILLNESS, recent_illness=True,
        )
        assert result.state == "cleared"
        assert result.primary_signal == "context"
        lo, hi = _STATE_BANDS["cleared"]
        assert lo <= result.score <= hi

    def test_recovered(self):
        """
        Rule 7: all three lenses nominal (C1=green, C2=high, C3=good)
        → recovered (convergent).
        """
        c1 = NlrHrvInput(
            tier="green", score=0.3, confidence=0.95,
            nlr_term=0.5, hrv_term=0.92,
        )
        c2 = SriInput(regularity_band="high", confidence=0.95)
        c3 = EfInput(decoupling_band="good", confidence=0.95)
        result = score_day(
            date(2025, 10, 1), c1, c2=c2, c3=c3,
            context_flags=_NO_ILLNESS, recent_illness=False,
        )
        assert result.state == "recovered"
        assert result.primary_signal == "convergent"
        lo, hi = _STATE_BANDS["recovered"]
        assert lo <= result.score <= hi

    def test_insufficient_data_all_three_lenses_unknown(self):
        """
        Rule 0: C1.tier, C2.regularity_band, C3.decoupling_band all unknown
        → insufficient_data, score 0, confidence 0.3 (before §4.1 cascade).
        """
        c1 = NlrHrvInput(
            tier="unknown", score=None, confidence=0.0,
            nlr_term=1.0, hrv_term=1.0,
        )
        c2 = SriInput(regularity_band="unknown", confidence=0.5)
        c3 = EfInput(decoupling_band="unknown", confidence=0.5)
        result = score_day(
            date(2026, 4, 24), c1, c2=c2, c3=c3,
            context_flags=_NO_ILLNESS, recent_illness=False,
        )
        assert result.state == "insufficient_data"
        assert result.score == 0
        assert result.confidence == 0.3
        assert result.divergence_flags == []
        assert "3 of 3 flagship lenses returned unknown" in result.reasoning


# ══════════════════════════════════════════════════════════════════════════════
# §2  Five real-day scenarios
# ══════════════════════════════════════════════════════════════════════════════


class TestRealDayScenarios:
    """
    Scenarios grounded in actual data (real panel NLR, real illness window)
    or in clinically coherent combinations of the three lenses.
    """

    def test_real_nlr_elevated_hrv_improving(self):
        """
        Real-data-driven scenario: NLR=10.2/1.9≈5.37 from the 2025-06-15 panel.
        Hypothetical recovery day where HRV today (70 ms) > 7d baseline (58 ms).

        nlr_term = 5.37/3.0 ≈ 1.79  → elevated
        hrv_term = 58/70   ≈ 0.83  → improving (today above baseline)
        score    ≈ 1.48             → caution tier (< 1.5 threshold)

        Rule 2 fires (not generic deload): both nlr_elevated AND hrv_improving,
        with C3 not showing central-fatigue signal.
        Divergence flag: autonomic_leading_nlr_elevated.
        """
        c1 = NlrHrvInput(
            tier="caution",
            score=round((5.37 / 3.0) * (58 / 70), 4),   # ≈ 1.4827
            confidence=0.80,
            nlr_term=round(5.37 / 3.0, 4),               # ≈ 1.7900
            hrv_term=round(58 / 70, 4),                   # ≈ 0.8286
        )
        assert c1.nlr_elevated   # 1.79 > 1.0
        assert c1.hrv_improving  # 0.83 < 1.0

        result = score_day(
            date(2025, 7, 1), c1,
            context_flags=_NO_ILLNESS, recent_illness=False,
        )
        assert result.state == "autonomic-recovery-leading"
        assert "autonomic_leading_nlr_elevated" in result.divergence_flags
        assert "Hold reload" in result.reasoning

    def test_real_all_green_recovered(self):
        """
        All three lenses nominal: NLR 1.8 (low), HRV today above baseline,
        SRI high, EF good → recovered.
        Score should land in [80, 100].
        """
        c1 = NlrHrvInput(
            tier="green",
            score=round((1.8 / 3.0) * (65 / 70), 4),  # ≈ 0.557
            confidence=0.90,
            nlr_term=round(1.8 / 3.0, 4),              # 0.6
            hrv_term=round(65 / 70, 4),                 # ≈ 0.929
        )
        c2 = SriInput(regularity_band="high", confidence=0.90)
        c3 = EfInput(decoupling_band="good", confidence=0.90)

        result = score_day(
            date(2025, 10, 15), c1, c2=c2, c3=c3,
            context_flags=_NO_ILLNESS, recent_illness=False,
        )
        assert result.state == "recovered"
        assert result.score >= 80

    def test_real_peripheral_strain(self):
        """
        NLR×HRV green, C3 moderate decoupling, C2 moderate SRI.
        C3.hrv_direction=stable (not central) → Rule 4 fires: peripheral-strain.
        Divergence: peripheral_environmental (EF↓ + HRV stable → environmental).
        """
        c1 = NlrHrvInput(
            tier="green", score=0.55, confidence=0.88,
            nlr_term=0.7, hrv_term=1.00,   # HRV stable (= baseline)
        )
        c2 = SriInput(regularity_band="moderate", confidence=0.75)
        c3 = EfInput(decoupling_band="moderate", hrv_direction="stable", confidence=0.80)

        result = score_day(
            date(2025, 11, 1), c1, c2=c2, c3=c3,
            context_flags=_NO_ILLNESS, recent_illness=False,
        )
        assert result.state == "peripheral-strain"
        assert result.primary_signal == "ef"
        assert "peripheral_environmental" in result.divergence_flags

    def test_real_illness_window_day(self):
        """
        2025-06-15 falls inside the real illness window (2025-06-08 → 2025-06-29).
        context_flags are loaded from the actual YAML; illness=True is asserted
        by the loader, so C1.tier=caution → illness-risk.
        """
        c1 = NlrHrvInput(
            tier="caution", score=1.3, confidence=0.75,
            nlr_term=1.1, hrv_term=1.08,
        )
        result = score_day(
            date(2025, 6, 15), c1,
            recent_illness=False,
            context_flags_path=_FLAGS_PATH,
        )
        assert result.state == "illness-risk"
        assert result.primary_signal == "context"
        assert "Stop training" in result.reasoning

    def test_real_convergent_reload_risk(self):
        """
        All three lenses degraded: C1=deload, C2=irregular, C3=high + HRV down.
        Rule 2 bypassed (hrv_term=1.10 → not improving).
        Rule 3 fires → deload.
        Divergence flags: convergent_reload_risk + convergent_stress + central_fatigue_or_illness.
        Score within deload band [50, 69].
        """
        c1 = NlrHrvInput(
            tier="deload", score=2.3, confidence=0.85,
            nlr_term=1.6, hrv_term=1.10,   # NLR↑, HRV↓ → Rule 2 bypassed
        )
        c2 = SriInput(regularity_band="irregular", confidence=0.70)
        c3 = EfInput(decoupling_band="high", hrv_direction="down", confidence=0.75)

        result = score_day(
            date(2025, 7, 20), c1, c2=c2, c3=c3,
            context_flags=_NO_ILLNESS, recent_illness=False,
        )
        assert result.state == "deload"
        assert "convergent_reload_risk" in result.divergence_flags
        assert "convergent_stress" in result.divergence_flags
        assert "central_fatigue_or_illness" in result.divergence_flags
        lo, hi = _STATE_BANDS["deload"]
        assert lo <= result.score <= hi


# ══════════════════════════════════════════════════════════════════════════════
# §3  Supporting unit tests
# ══════════════════════════════════════════════════════════════════════════════


class TestSupportingUnits:

    @pytest.mark.parametrize("state", list(_STATE_BANDS.keys()))
    def test_score_always_within_declared_band(self, state):
        """
        spec §5: score = hi − round(severity × (hi − lo)).
        Verified for every state with c1.score=1.0 (mid-range) and
        c2/c3 at moderate/moderate severity.
        """
        c1 = NlrHrvInput(
            tier="green", score=1.0, confidence=0.80,
            nlr_term=1.0, hrv_term=1.0,
        )
        c2 = SriInput(regularity_band="moderate", confidence=0.70)
        c3 = EfInput(decoupling_band="moderate", confidence=0.70)
        lo, hi = _STATE_BANDS[state]
        score = _score_in_band(state, c1, c2, c3)
        assert lo <= score <= hi, (
            f"state '{state}': _score_in_band returned {score}, expected [{lo},{hi}]"
        )

    def test_divergence_autonomic_leading_fires(self):
        """
        spec §6 Row 1: nlr_elevated AND hrv_improving → autonomic_leading_nlr_elevated.
        convergent_stress must NOT fire (HRV is improving, not declining).
        """
        c1 = NlrHrvInput(
            tier="deload", score=1.6, confidence=0.75,
            nlr_term=1.3, hrv_term=0.90,   # elevated + improving
        )
        flags = _detect_divergences(c1, SriInput(), EfInput())
        assert "autonomic_leading_nlr_elevated" in flags
        assert "convergent_stress" not in flags

    def test_divergence_convergent_reload_risk_fires(self):
        """
        spec §6 Row 12: all three lenses degraded simultaneously.
        Also verifies secondary flags that fire together.
        """
        c1 = NlrHrvInput(
            tier="deload", score=2.2, confidence=0.85,
            nlr_term=1.5, hrv_term=1.10,   # elevated + declining
        )
        c2 = SriInput(regularity_band="irregular", confidence=0.70)
        c3 = EfInput(decoupling_band="high", hrv_direction="down", confidence=0.75)
        flags = _detect_divergences(c1, c2, c3)
        assert "convergent_reload_risk" in flags
        assert "convergent_stress" in flags            # NLR↑ + HRV↓ + tier=deload
        assert "central_fatigue_or_illness" in flags   # EF high + HRV down

    def test_confidence_geomean_no_flags(self):
        """
        spec §7: base confidence = geomean(c1, c2, c3).
        All-green inputs produce no divergence flags, so base is unchanged.
        Expected: geomean(0.90, 0.80, 0.70) ≈ 0.7958.
        """
        c1 = NlrHrvInput(
            tier="green", score=0.4, confidence=0.90,
            nlr_term=0.6, hrv_term=0.95,   # NLR normal; HRV borderline-improving
        )
        c2 = SriInput(regularity_band="high", confidence=0.80)
        c3 = EfInput(decoupling_band="good", confidence=0.70)

        result = score_day(
            date(2025, 10, 1), c1, c2=c2, c3=c3,
            context_flags=_NO_ILLNESS, recent_illness=False,
        )
        assert result.divergence_flags == [], (
            f"expected no flags, got: {result.divergence_flags}"
        )
        expected_conf = math.exp(
            (math.log(0.90) + math.log(0.80) + math.log(0.70)) / 3
        )
        assert abs(result.confidence - round(expected_conf, 4)) < 1e-3

    def test_from_score_day_mapping(self):
        """
        NlrHrvInput.from_score_day() must correctly populate all fields
        from the meta dict produced by nlr_hrv_readiness.score_day().
        """
        result_dict = {
            "tier":          "caution",
            "score":         1.25,
            "confidence":    0.75,
            "quality_flags": ["hrv_anomaly_smoothed"],
            "meta": {
                "nlr_term":             1.30,
                "hrv_term":             0.88,
                "nlr":                  3.9,
                "hrv_baseline_7d":      58.0,
                "hrv_current_effective": 66.0,
            },
        }
        c1 = NlrHrvInput.from_score_day(result_dict)

        assert c1.tier    == "caution"
        assert c1.score   == pytest.approx(1.25)
        assert c1.nlr_term == pytest.approx(1.30)
        assert c1.hrv_term == pytest.approx(0.88)
        assert c1.nlr_elevated    # 1.30 > 1.0
        assert c1.hrv_improving   # 0.88 < 1.0
        assert not c1.hrv_declining  # 0.88 < 1.05
        assert "hrv_anomaly_smoothed" in c1.quality_flags

    def test_fill_hrv_direction_all_three_zones(self):
        """
        _fill_hrv_direction derives direction from C1.hrv_term:
          < 0.95 → 'up'   (today >5% above baseline)
          > 1.05 → 'down' (today >5% below baseline)
          else   → 'stable'
        """
        c3_blank = EfInput(decoupling_band="good", hrv_direction="unknown")

        # Zone 1: hrv_term=0.90 < 0.95 → up
        c1_up = NlrHrvInput(tier="green", score=0.4, confidence=0.9,
                            nlr_term=0.6, hrv_term=0.90)
        assert _fill_hrv_direction(c3_blank, c1_up).hrv_direction == "up"

        # Zone 2: hrv_term=1.00 ∈ [0.95, 1.05] → stable
        c1_stable = NlrHrvInput(tier="green", score=0.6, confidence=0.9,
                                nlr_term=0.7, hrv_term=1.00)
        assert _fill_hrv_direction(c3_blank, c1_stable).hrv_direction == "stable"

        # Zone 3: hrv_term=1.10 > 1.05 → down
        c1_down = NlrHrvInput(tier="caution", score=1.1, confidence=0.75,
                              nlr_term=0.9, hrv_term=1.10)
        assert _fill_hrv_direction(c3_blank, c1_down).hrv_direction == "down"

    def test_recent_illness_detection_from_yaml(self):
        """
        _detect_recent_illness reads the real context_flags.yaml.
        Illness window: 2025-06-08 → 2025-06-29.

        2025-07-05:  end date 2025-06-29 is 6 days before scoring_date,
                     within the 14-day window → True.
        2025-08-01:  end date is 33 days before scoring_date → False.
        """
        assert _detect_recent_illness(date(2025, 7, 5), _FLAGS_PATH) is True
        assert _detect_recent_illness(date(2025, 8, 1), _FLAGS_PATH) is False

    def test_cleared_state_via_yaml_recent_illness(self):
        """
        Integration test: scoring 2025-07-05 with context_flags_path pointing to
        the real YAML.  recent_illness is computed (not injected), and illness
        window ended 2025-06-29 (6 days prior → within 14-day window → True).
        C1=green, no active illness → cleared.
        """
        c1 = NlrHrvInput(
            tier="green", score=0.4, confidence=0.88,
            nlr_term=0.7, hrv_term=0.97,
        )
        result = score_day(
            date(2025, 7, 5), c1,
            context_flags=_NO_ILLNESS,     # illness window has ended
            context_flags_path=_FLAGS_PATH,  # recent_illness derived from YAML
        )
        assert result.state == "cleared"
        assert result.primary_signal == "context"

    def test_reasoning_is_deterministic(self):
        """
        spec §8: same inputs → same reasoning string, score, and state.
        Calling score_day() twice must produce byte-identical results.
        """
        c1 = NlrHrvInput(
            tier="green", score=0.45, confidence=0.88,
            nlr_term=0.65, hrv_term=0.95,
        )
        kwargs = dict(context_flags=_NO_ILLNESS, recent_illness=False)
        r1 = score_day(date(2025, 9, 10), c1, **kwargs)
        r2 = score_day(date(2025, 9, 10), c1, **kwargs)

        assert r1.state    == r2.state
        assert r1.score    == r2.score
        assert r1.reasoning == r2.reasoning
        assert r1.divergence_flags == r2.divergence_flags

    def test_result_is_composite_result_instance(self):
        """score_day() must return a CompositeResult dataclass."""
        c1 = NlrHrvInput(tier="green", score=0.5, confidence=0.85,
                         nlr_term=0.7, hrv_term=0.97)
        result = score_day(date(2025, 9, 20), c1,
                           context_flags=_NO_ILLNESS, recent_illness=False)
        assert isinstance(result, CompositeResult)
        assert result.state in _STATE_BANDS
        assert 0 <= result.score <= 100
        assert 0.0 <= result.confidence <= 1.0
        assert result.primary_signal in {"nlr_hrv", "sri", "ef", "convergent", "context"}

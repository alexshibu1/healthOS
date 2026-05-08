"""
src/score/composite.py

Composite Readiness Score — three-lens fusion.

Spec: src/score/specs/composite-spec.md
Physiology: skills/health-reasoning.md §4 (divergence matrix)

Design principle (composite-spec §1):
    A weighted sum loses information when lenses disagree. Disagreement is
    the diagnostic signal. This scorer leads with a STATE LABEL, then a
    score normalized within that state's band. Divergence patterns from §4
    are surfaced as named flags, not averaged away.

Inputs:
    C1 — NLR × HRV readiness (src/score/nlr_hrv_readiness.py)
    C2 — Sleep Regularity Index (not yet implemented; accepts "unknown" gracefully)
    C3 — Aerobic Decoupling / EF  (not yet implemented; accepts "unknown" gracefully)
    context_flags — from src/context/flags.py

Output: CompositeResult dataclass + parquet at data/scores/composite.parquet
"""

from __future__ import annotations

import json
import math
from dataclasses import dataclass, field
from datetime import date, timedelta
from pathlib import Path
from typing import Any, Optional

import pandas as pd

from src.context.flags import get_active_flags, load_context_flags

# ── constants ──────────────────────────────────────────────────────────────────

# Spec §5 — state score bands (lo, hi).  Higher = more training-ready.
_STATE_BANDS: dict[str, tuple[int, int]] = {
    "illness-risk":               (10, 29),
    "deload":                     (50, 69),
    "accumulating-fatigue":       (30, 49),
    "peripheral-strain":          (55, 69),
    "autonomic-recovery-leading": (65, 79),
    "cleared":                    (75, 89),
    "recovered":                  (80, 100),
}

# Spec §6 — divergence modifiers (compound multiplicatively; cap to [0, 1])
_DIVERGENCE_MODS: dict[str, float] = {
    "convergent_reload_risk":          1.2,
    "lifestyle_driven_systemic_stress": 1.1,
    "convergent_stress":               1.0,
    "recovery_debt_ef_decay":          1.0,
    "central_fatigue_or_illness":      1.0,
    "acute_noncircadian_stressor":     0.9,
    "peripheral_environmental":        0.9,
    "autonomic_stress_no_inflammation": 0.8,
    "circadian_early_warning":         0.8,
    "autonomic_leading_nlr_elevated":  0.7,
    "pure_peripheral":                 0.7,
}

_RECENT_ILLNESS_WINDOW_DAYS = 14   # "cleared" detection window
_SCORES_DIR = Path(__file__).resolve().parents[2] / "data" / "scores"

# Default confidence for unknown/missing lens inputs
_UNKNOWN_CONF = 0.5


# ── typed input containers ────────────────────────────────────────────────────

@dataclass
class NlrHrvInput:
    """
    C1 input from nlr_hrv_readiness.score_day().

    composite-spec §2: nlr_term > 1.0 → NLR elevated;
                       hrv_term < 1.0  → HRV improving (today > baseline).
    """
    tier: str                        # deload | caution | green | unknown
    score: Optional[float]           # raw readiness score (§1)
    confidence: float
    nlr_term: float    = 1.0         # NLR / 3.0 — from meta dict
    hrv_term:  float   = 1.0         # baseline / current — from meta dict
    quality_flags: list[str] = field(default_factory=list)

    @classmethod
    def from_score_day(cls, result: dict) -> "NlrHrvInput":
        """Construct from the output dict of nlr_hrv_readiness.score_day()."""
        meta = result.get("meta", {})
        return cls(
            tier          = result.get("tier", "unknown"),
            score         = result.get("score"),
            confidence    = result.get("confidence", _UNKNOWN_CONF),
            nlr_term      = meta.get("nlr_term", 1.0),
            hrv_term      = meta.get("hrv_term", 1.0),
            quality_flags = result.get("quality_flags", []),
        )

    @property
    def nlr_elevated(self) -> bool:
        """NLR > NLR_THRESHOLD (3.0)."""
        return self.nlr_term > 1.0

    @property
    def hrv_improving(self) -> bool:
        """Today's HRV above 7d baseline (composite-spec §2: hrv_term < 1.0)."""
        return self.hrv_term < 1.0

    @property
    def hrv_declining(self) -> bool:
        """Today's HRV meaningfully below baseline (> 5% drop to filter noise)."""
        return self.hrv_term > 1.05


@dataclass
class SriInput:
    """
    C2 input from the SRI scorer (not yet implemented).

    Pass regularity_band="unknown" and confidence=0.5 until the scorer ships.
    """
    regularity_band: str = "unknown"  # irregular | moderate | high | unknown
    sri: Optional[float] = None       # 0–100
    confidence: float    = _UNKNOWN_CONF
    quality_flags: list[str] = field(default_factory=list)


@dataclass
class EfInput:
    """
    C3 input from the aerobic decoupling scorer (not yet implemented).

    hrv_direction: populated by caller from C1.meta (up if hrv_term < 0.95,
    down if hrv_term > 1.05, stable otherwise).  Enables the §4 Pa:HR×HRV
    cross-signal split without re-importing C1.
    """
    decoupling_band: str          = "unknown"  # high | moderate | good | unknown
    ef_zscore: Optional[float]    = None
    negative_ef_streak_days: int  = 0
    hrv_direction: str            = "unknown"  # up | down | stable | unknown
    confidence: float             = _UNKNOWN_CONF
    quality_flags: list[str]      = field(default_factory=list)


@dataclass
class CompositeResult:
    """
    composite-spec §3 output schema.
    """
    state:            str           # one of 7 states
    score:            int           # 0–100, normalized within state band
    primary_signal:   str           # nlr_hrv | sri | ef | convergent | context
    divergence_flags: list[str]     # patterns from skill §4
    reasoning:        str           # deterministic template
    confidence:       float         # ∈ [0, 1]


# ── public API ─────────────────────────────────────────────────────────────────

def score_day(
    scoring_date: date,
    c1: NlrHrvInput,
    c2: Optional[SriInput] = None,
    c3: Optional[EfInput]  = None,
    context_flags: Optional[dict[str, bool]] = None,
    *,
    recent_illness: Optional[bool] = None,
    context_flags_path: Optional[Path] = None,
) -> CompositeResult:
    """
    Compute the composite readiness state for one calendar day.

    composite-spec §4: state is determined by priority-ordered rules applied
    to the three lens inputs and context flags.  Score is normalized within
    the state's band per §5.

    Parameters
    ----------
    scoring_date        : Date being scored.
    c1                  : NLR × HRV input.  Required.
    c2                  : SRI input.  None → treated as all-unknown.
    c3                  : Aerobic decoupling input.  None → all-unknown.
    context_flags       : Pre-loaded flags dict.  None → loaded from YAML.
    recent_illness      : Override for "illness ended within 14 days" check.
                          If None, computed from context_flags YAML windows.
    context_flags_path  : Override path for context_flags.yaml.
    """
    c2 = c2 or SriInput()
    c3 = c3 or EfInput()

    # ── context ────────────────────────────────────────────────────────────────
    if context_flags is None:
        context_flags = get_active_flags(scoring_date, path=context_flags_path)
    illness_flag = bool(context_flags.get("illness", False))

    if recent_illness is None:
        recent_illness = _detect_recent_illness(scoring_date, context_flags_path)

    # ── populate C3.hrv_direction from C1 if caller left it at default ─────────
    if c3.hrv_direction == "unknown" and c1.tier != "unknown":
        c3 = _fill_hrv_direction(c3, c1)

    # ── state classification (spec §4.1, priority order) ──────────────────────
    state, primary_signal = _classify_state(c1, c2, c3, illness_flag, recent_illness)

    # ── divergence flags (spec §6) ─────────────────────────────────────────────
    divergence_flags = _detect_divergences(c1, c2, c3)

    # ── within-state score (spec §5) ──────────────────────────────────────────
    score = _score_in_band(state, c1, c2, c3)

    # ── confidence (spec §7) ──────────────────────────────────────────────────
    confidence = _compute_confidence(c1, c2, c3, divergence_flags)

    # ── reasoning ─────────────────────────────────────────────────────────────
    reasoning = _build_reasoning(
        state, score, primary_signal, c1, c2, c3,
        divergence_flags, illness_flag, recent_illness, confidence
    )

    return CompositeResult(
        state            = state,
        score            = score,
        primary_signal   = primary_signal,
        divergence_flags = divergence_flags,
        reasoning        = reasoning,
        confidence       = round(confidence, 4),
    )


def score_range(
    start_date: date,
    end_date: date,
    c1_results: dict[date, dict],
    c2_results: Optional[dict[date, SriInput]] = None,
    c3_results: Optional[dict[date, EfInput]]  = None,
    context_flags_path: Optional[Path]          = None,
    output_path: Optional[Path]                 = None,
) -> pd.DataFrame:
    """
    Score every day in [start_date, end_date] and write to parquet.

    Parameters
    ----------
    c1_results  : dict mapping date → output dict from nlr_hrv_readiness.score_day().
    c2_results  : dict mapping date → SriInput.  Missing dates use all-unknown.
    c3_results  : dict mapping date → EfInput.   Missing dates use all-unknown.
    output_path : Override for data/scores/composite.parquet.
    """
    c2_results = c2_results or {}
    c3_results = c3_results or {}

    rows = []
    current = start_date
    while current <= end_date:
        c1_raw = c1_results.get(current)
        c1 = NlrHrvInput.from_score_day(c1_raw) if c1_raw else NlrHrvInput(
            tier="unknown", score=None, confidence=_UNKNOWN_CONF
        )
        c2 = c2_results.get(current) or SriInput()
        c3 = c3_results.get(current) or EfInput()

        ctx = get_active_flags(current, path=context_flags_path)
        r = score_day(current, c1, c2, c3, context_flags=ctx,
                      context_flags_path=context_flags_path)

        rows.append({
            "date":            current,
            "state":           r.state,
            "score":           r.score,
            "primary_signal":  r.primary_signal,
            "divergence_flags": json.dumps(r.divergence_flags),
            "reasoning":       r.reasoning,
            "confidence":      r.confidence,
        })
        current += timedelta(days=1)

    out_df = pd.DataFrame(rows)
    out_path = output_path or (_SCORES_DIR / "composite.parquet")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_df.to_parquet(out_path, index=False)
    return out_df


# ── state classification ───────────────────────────────────────────────────────

def _classify_state(
    c1: NlrHrvInput,
    c2: SriInput,
    c3: EfInput,
    illness_flag: bool,
    recent_illness: bool,
) -> tuple[str, str]:
    """
    Apply priority-ordered state rules from composite-spec §4.1.

    Returns (state, primary_signal).
    """

    # Rule 1 — illness-risk (context + systemic strain)
    if illness_flag and c1.tier in ("deload", "caution"):
        return "illness-risk", "context"

    # Rule 2 — autonomic-recovery-leading (NLR elevated, HRV already improving)
    # Checked BEFORE general deload: this is a specific diagnostic subtype.
    # Skill §1.2: "HRV improving + NLR still elevated → autonomic recovery preceding
    # inflammatory resolution."
    if (
        c1.tier in ("deload", "caution")
        and c1.nlr_elevated
        and c1.hrv_improving
        and c3.decoupling_band in ("good", "unknown")
    ):
        return "autonomic-recovery-leading", "nlr_hrv"

    # Rule 3 — deload (C1 says so; rule 2 already excluded the divergent subtype)
    if c1.tier == "deload":
        return "deload", "nlr_hrv"

    # Rule 4 — peripheral-strain (EF decoupling without central/systemic cause)
    # Skill §3.2: "EF ↓ + HRV ↑ → peripheral/environmental".
    if (
        c1.tier in ("green", "caution", "unknown")
        and c3.decoupling_band in ("high", "moderate")
        and c3.hrv_direction in ("up", "stable", "unknown")
    ):
        return "peripheral-strain", "ef"

    # Rule 5 — accumulating-fatigue
    # Skill §3.2: "sustained ef_zscore < −1.0 for 5 days → accumulating fatigue"
    if c3.negative_ef_streak_days >= 5:
        return "accumulating-fatigue", "ef"
    if (
        c1.tier == "caution"
        and c2.regularity_band in ("irregular", "moderate")
    ):
        return "accumulating-fatigue", "convergent"

    # Rule 6 — cleared (recently exited illness, all systems normalizing)
    if (
        recent_illness
        and c1.tier == "green"
        and c2.regularity_band in ("high", "moderate", "unknown")
        and c3.decoupling_band in ("good", "unknown")
    ):
        return "cleared", "context"

    # Rule 7 — recovered (all nominal)
    if (
        c1.tier in ("green", "unknown")
        and c2.regularity_band in ("high", "moderate", "unknown")
        and c3.decoupling_band in ("good", "unknown")
    ):
        ps = "convergent" if (
            c1.tier == "green" and c2.regularity_band in ("high", "moderate")
        ) else "nlr_hrv"
        return "recovered", ps

    # Default: something is off but no specific pattern triggered
    return "accumulating-fatigue", "convergent"


# ── divergence detection (spec §6 / skill §4) ─────────────────────────────────

def _detect_divergences(
    c1: NlrHrvInput,
    c2: SriInput,
    c3: EfInput,
) -> list[str]:
    """
    Detect cross-lens divergence patterns from skill §4 divergence matrix.
    Multiple flags can fire simultaneously — each encodes a distinct mechanism.
    """
    flags: list[str] = []

    # Row 1: HRV↑ + NLR↑ → autonomic leading inflammatory resolution
    if c1.nlr_elevated and c1.hrv_improving:
        flags.append("autonomic_leading_nlr_elevated")

    # Row 2: HRV↓ + NLR↑ → convergent stress (both systems strained)
    if c1.nlr_elevated and c1.hrv_declining and c1.tier in ("deload", "caution"):
        flags.append("convergent_stress")

    # Row 4: HRV↓ + NLR normal → autonomic stressor without measurable inflammation
    if not c1.nlr_elevated and c1.hrv_declining:
        flags.append("autonomic_stress_no_inflammation")

    # Row 5: NLR×HRV degraded + SRI irregular → lifestyle-driven systemic stress
    if c1.tier in ("deload", "caution") and c2.regularity_band == "irregular":
        flags.append("lifestyle_driven_systemic_stress")

    # Row 6: NLR×HRV degraded + SRI high → acute, non-circadian stressor
    if c1.tier in ("deload", "caution") and c2.regularity_band == "high":
        flags.append("acute_noncircadian_stressor")

    # Row 7: SRI irregular + NLR×HRV fine → early circadian warning
    if c2.regularity_band == "irregular" and c1.tier == "green":
        flags.append("circadian_early_warning")

    # Row 8: Pa:HR↑ + HRV↓ → central fatigue / illness
    if c3.decoupling_band in ("high", "moderate") and c3.hrv_direction == "down":
        flags.append("central_fatigue_or_illness")

    # Row 9: Pa:HR↑ + HRV↑ → peripheral / environmental
    if c3.decoupling_band in ("high", "moderate") and c3.hrv_direction in ("up", "stable"):
        flags.append("peripheral_environmental")

    # Row 10: Pa:HR↑ + SRI irregular → recovery debt expressing as EF decay
    if c3.decoupling_band in ("high", "moderate") and c2.regularity_band == "irregular":
        flags.append("recovery_debt_ef_decay")

    # Row 11: Pa:HR↑ + NLR×HRV fine → pure peripheral / environmental
    if c3.decoupling_band in ("high", "moderate") and c1.tier == "green":
        flags.append("pure_peripheral")

    # Row 12: All three degraded → convergent reload risk (highest confidence)
    if (
        c1.tier == "deload"
        and c2.regularity_band == "irregular"
        and c3.decoupling_band == "high"
    ):
        flags.append("convergent_reload_risk")

    return flags


# ── within-state score (spec §5) ──────────────────────────────────────────────

_C2_SEV: dict[str, float] = {
    "irregular": 1.0, "moderate": 0.5, "high": 0.0, "unknown": 0.3
}
_C3_SEV: dict[str, float] = {
    "high": 1.0, "moderate": 0.5, "good": 0.0, "unknown": 0.3
}


def _clamp(x: float, lo: float = 0.0, hi: float = 1.0) -> float:
    return max(lo, min(hi, x))


def _compute_severity(
    state: str,
    c1: NlrHrvInput,
    c2: SriInput,
    c3: EfInput,
) -> float:
    """
    spec §5.1 severity formulas.  Returns ∈ [0.0, 1.0]:
    0 = best within state (→ score = hi), 1 = worst within state (→ score = lo).
    """
    c1_raw = c1.score if c1.score is not None else 0.7
    c2_sev = _C2_SEV.get(c2.regularity_band, 0.3)
    c3_sev = _C3_SEV.get(c3.decoupling_band, 0.3)

    if state == "illness-risk":
        return _clamp(
            0.7 * _clamp((c1_raw - 1.0) / 2.0)
            + 0.2 * c2_sev
            + 0.1 * c3_sev
        )
    if state == "deload":
        return _clamp(
            0.7 * _clamp((c1_raw - 1.5) / 1.5)
            + 0.15 * c2_sev
            + 0.15 * c3_sev
        )
    if state == "accumulating-fatigue":
        return _clamp(
            0.5 * _clamp(c1_raw / 1.5)
            + 0.3 * c2_sev
            + 0.2 * c3_sev
        )
    if state == "peripheral-strain":
        return _clamp(
            0.2 * _clamp(c1_raw / 1.0)
            + 0.1 * c2_sev
            + 0.7 * c3_sev
        )
    if state == "autonomic-recovery-leading":
        # How far HRV has improved vs how elevated NLR remains
        hrv_improvement = _clamp(1.0 - c1.hrv_term)   # 0=no improvement, 1=double baseline
        return _clamp(
            0.6 * _clamp((c1_raw - 1.0) / 1.0)
            + 0.2 * (1.0 - hrv_improvement)
            + 0.2 * c2_sev
        )
    if state in ("cleared", "recovered"):
        return _clamp(
            0.6 * _clamp(c1_raw / 1.0)
            + 0.2 * c2_sev
            + 0.2 * c3_sev
        )
    return 0.5  # unknown state


def _score_in_band(
    state: str,
    c1: NlrHrvInput,
    c2: SriInput,
    c3: EfInput,
) -> int:
    """
    spec §5: score = hi − round(severity × (hi − lo)).
    severity 0 → score hi (best within band); severity 1 → score lo (worst).
    """
    lo, hi = _STATE_BANDS.get(state, (40, 60))
    severity = _compute_severity(state, c1, c2, c3)
    return max(lo, min(hi, round(hi - severity * (hi - lo))))


# ── confidence (spec §7) ──────────────────────────────────────────────────────

def _compute_confidence(
    c1: NlrHrvInput,
    c2: SriInput,
    c3: EfInput,
    divergence_flags: list[str],
) -> float:
    """
    spec §7: base = geomean(c1, c2, c3 confidences); then compound divergence mods.
    """
    base = _geomean([c1.confidence, c2.confidence, c3.confidence])
    for flag in divergence_flags:
        mod = _DIVERGENCE_MODS.get(flag, 1.0)
        base *= mod
    return max(0.0, min(1.0, base))


def _geomean(values: list[float]) -> float:
    if not values:
        return 0.0
    log_sum = sum(math.log(max(v, 1e-9)) for v in values)
    return math.exp(log_sum / len(values))


# ── reasoning (spec §8) ───────────────────────────────────────────────────────

# Action implications per state (spec §4 table)
_STATE_ACTIONS: dict[str, str] = {
    "illness-risk":               "Stop training; investigate illness onset.",
    "deload":                     "Cap volume; no high-intensity sessions.",
    "accumulating-fatigue":       "Reduce load; monitor for 3–5 days before reassessing.",
    "peripheral-strain":          "Confound-check heat, hydration, leg stress; do not deload reflexively.",
    "autonomic-recovery-leading": "Hold reload; wearable leads blood — wait for NLR confirmation.",
    "cleared":                    "Resume carefully; monitor first CBC confirmation post-illness.",
    "recovered":                  "Unrestricted training; maintain current load.",
}

# Plain-language divergence descriptions
_DIVERGENCE_DESCRIPTIONS: dict[str, str] = {
    "autonomic_leading_nlr_elevated":  "HRV improving while NLR still elevated: autonomic recovery may be ahead of inflammatory resolution (skill §1.2).",
    "convergent_stress":               "HRV declining and NLR elevated: both autonomic and inflammatory systems strained — convergent stress signal.",
    "autonomic_stress_no_inflammation": "HRV declining without elevated NLR: autonomic stressor (sleep debt, psychological stress, overreaching) without measurable inflammation.",
    "lifestyle_driven_systemic_stress": "NLR×HRV degraded and sleep regularity low: lifestyle-driven systemic stress pattern; circadian regularization has high expected leverage.",
    "acute_noncircadian_stressor":     "NLR×HRV degraded with high sleep regularity: acute, non-lifestyle stressor; search for discrete cause.",
    "circadian_early_warning":         "Sleep irregularity present while NLR×HRV is normal: early circadian warning before systemic propagation.",
    "central_fatigue_or_illness":      "EF drifting and HRV declining: central fatigue pattern — both engine and regulator degraded.",
    "peripheral_environmental":        "EF drifting and HRV stable or improving: peripheral / environmental cause (heat, dehydration, leg stress); autonomic state intact.",
    "recovery_debt_ef_decay":          "EF drift coincides with irregular sleep: recovery debt expressing as exercise-economy decay.",
    "pure_peripheral":                 "EF drift with NLR×HRV normal: pure peripheral or environmental cause; do not treat as systemic.",
    "convergent_reload_risk":          "All three lenses degraded simultaneously: highest-confidence deload signal.",
}


def _build_reasoning(
    state: str,
    score: int,
    primary_signal: str,
    c1: NlrHrvInput,
    c2: SriInput,
    c3: EfInput,
    divergence_flags: list[str],
    illness_flag: bool,
    recent_illness: bool,
    confidence: float,
) -> str:
    """
    composite-spec §8: deterministic reasoning template.
    Same inputs → same string.
    """
    parts: list[str] = []

    # 1. State declaration
    parts.append(f"State: {state} (score {score}/100).")

    # 2. Primary driver
    if primary_signal == "context":
        ctx_reason = "illness window active" if illness_flag else "recent illness window"
        parts.append(f"Primary signal: context ({ctx_reason}).")
    elif primary_signal == "nlr_hrv":
        if c1.score is not None:
            parts.append(
                f"Primary signal: NLR×HRV (tier={c1.tier}, "
                f"readiness score={round(c1.score, 2)}, "
                f"NLR term={round(c1.nlr_term, 2)}, "
                f"HRV term={round(c1.hrv_term, 2)})."
            )
        else:
            parts.append(f"Primary signal: NLR×HRV (tier={c1.tier}).")
    elif primary_signal == "ef":
        parts.append(
            f"Primary signal: aerobic decoupling "
            f"(band={c3.decoupling_band}, "
            f"EF streak={c3.negative_ef_streak_days}d, "
            f"HRV direction={c3.hrv_direction})."
        )
    elif primary_signal == "sri":
        parts.append(
            f"Primary signal: sleep regularity "
            f"(band={c2.regularity_band}, "
            f"SRI={round(c2.sri, 1) if c2.sri is not None else 'unknown'})."
        )
    elif primary_signal == "convergent":
        parts.append(
            f"Primary signal: convergent ("
            f"NLR×HRV={c1.tier}, "
            f"SRI={c2.regularity_band}, "
            f"EF={c3.decoupling_band})."
        )

    # 3. Divergence patterns
    for flag in divergence_flags:
        desc = _DIVERGENCE_DESCRIPTIONS.get(flag)
        if desc:
            parts.append(desc)

    # 4. Confidence
    conf_pct = round(confidence * 100, 1)
    if divergence_flags:
        mod_names = [f for f in divergence_flags if f in _DIVERGENCE_MODS]
        parts.append(
            f"Confidence: {conf_pct}% (divergence modifiers: "
            f"{', '.join(mod_names) or 'none'})."
        )
    else:
        parts.append(f"Confidence: {conf_pct}%.")

    # 5. Action implication
    action = _STATE_ACTIONS.get(state, "Monitor and reassess.")
    parts.append(f"Action: {action}")

    return " ".join(parts)


# ── helpers ────────────────────────────────────────────────────────────────────

def _detect_recent_illness(
    scoring_date: date,
    context_flags_path: Optional[Path] = None,
) -> bool:
    """
    composite-spec §4.1 Rule 6: illness window ended within last 14 days.

    Returns True when any illness window ended in (scoring_date − 14d, scoring_date].
    """
    try:
        ctx = load_context_flags(context_flags_path)
    except (FileNotFoundError, ValueError):
        return False

    window_start = scoring_date - timedelta(days=_RECENT_ILLNESS_WINDOW_DAYS)
    for win in ctx.get("illness_windows", []):
        try:
            from datetime import date as _date
            end = win["end"] if isinstance(win["end"], _date) else _date.fromisoformat(str(win["end"]))
            if window_start < end < scoring_date:
                return True
        except (KeyError, ValueError):
            continue
    return False


def _fill_hrv_direction(c3: EfInput, c1: NlrHrvInput) -> EfInput:
    """
    Derive C3.hrv_direction from C1.hrv_term when the caller left it at 'unknown'.
    composite-spec §2: hrv_term < 0.95 → up, > 1.05 → down, else stable.
    """
    if c1.hrv_term < 0.95:
        direction = "up"
    elif c1.hrv_term > 1.05:
        direction = "down"
    else:
        direction = "stable"

    return EfInput(
        decoupling_band        = c3.decoupling_band,
        ef_zscore              = c3.ef_zscore,
        negative_ef_streak_days = c3.negative_ef_streak_days,
        hrv_direction          = direction,
        confidence             = c3.confidence,
        quality_flags          = list(c3.quality_flags),
    )

"""Five MVP tests for ``src.context`` profile + flags loaders."""

from datetime import date
from pathlib import Path

import pytest

from src.context.flags import get_active_flags, load_context_flags
from src.context.profile import Profile, load_profile

FIXTURES = Path(__file__).parent / "fixtures"


def test_profile_loads():
    """Valid YAML with all required fields → Profile dataclass."""
    p = load_profile(FIXTURES / "profile_ok.yaml")
    assert isinstance(p, Profile)
    assert p.age == 21
    assert p.sex == "male"
    assert p.weight_kg == 72.0
    assert p.height_cm == 178.0
    assert p.primary_training_modality == "running"
    assert p.primary_goal == "longevity"


def test_profile_rejects_missing_required_field():
    """Omitting a required key raises ValueError."""
    with pytest.raises(ValueError, match="primary_goal"):
        load_profile(FIXTURES / "profile_missing_goal.yaml")


def test_flags_load():
    """context_flags YAML parses into three window lists."""
    ctx = load_context_flags(FIXTURES / "context_flags_ok.yaml")
    assert len(ctx["illness_windows"]) == 1
    assert ctx["illness_windows"][0]["note"] == (
        "food poisoning, panel drawn 2025-06-15"
    )
    assert ctx["travel_windows"] == []
    assert ctx["injury_windows"] == []


def test_flags_all_false_outside_windows():
    """Date outside every window → all categories False."""
    flags = get_active_flags(
        date(2020, 1, 1),
        path=FIXTURES / "context_flags_ok.yaml",
    )
    assert flags == {"illness": False, "travel": False, "injury": False}


def test_flags_illness_true_inside_window():
    """Date inside illness interval → illness True only."""
    flags = get_active_flags(
        date(2025, 6, 20),
        path=FIXTURES / "context_flags_ok.yaml",
    )
    assert flags["illness"] is True
    assert flags["travel"] is False
    assert flags["injury"] is False

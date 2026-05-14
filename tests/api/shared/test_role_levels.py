"""Levels-by-role-family lookup. Drives the post-interview form's level
dropdown options and validates the agent's level_suggestion."""
from api.shared.role_levels import DEFAULT_LEVELS, levels_for


def test_data_engineering_levels():
    assert levels_for("Senior Data Engineer") == [
        "Mid-Level", "Senior", "Staff", "Principal",
    ]


def test_creative_director_levels():
    assert levels_for("Creative Director") == [
        "Director", "Senior Director", "VP Creative",
    ]


def test_unknown_role_falls_back_to_default():
    assert levels_for("Brand Strategist") == DEFAULT_LEVELS
    assert DEFAULT_LEVELS == ["Junior", "Mid", "Senior", "Lead"]


def test_none_role_falls_back_to_default():
    assert levels_for(None) == DEFAULT_LEVELS

"""Per-role-family seniority ladders. Sole consumer right now is the
post-interview decision form (level dropdown) and the interview-recommender
agent's `level_suggestion` validation. Keep additions here, not inline."""
from __future__ import annotations

DEFAULT_LEVELS: list[str] = ["Junior", "Mid", "Senior", "Lead"]

_LEVELS_BY_TITLE_KEYWORD: dict[str, list[str]] = {
    "data engineer":     ["Mid-Level", "Senior", "Staff", "Principal"],
    "creative director": ["Director", "Senior Director", "VP Creative"],
}


def levels_for(role_title: str | None) -> list[str]:
    """Return the level ladder for `role_title`, or DEFAULT_LEVELS when no
    keyword matches. Match is case-insensitive substring against the keys."""
    if not role_title:
        return DEFAULT_LEVELS
    haystack = role_title.lower()
    for keyword, ladder in _LEVELS_BY_TITLE_KEYWORD.items():
        if keyword in haystack:
            return ladder
    return DEFAULT_LEVELS

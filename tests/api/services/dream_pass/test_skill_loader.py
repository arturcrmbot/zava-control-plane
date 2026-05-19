from __future__ import annotations

from pathlib import Path
from textwrap import dedent

import pytest

from api.server.services.dream_pass.skill_loader import DreamSkillLoadError, dream_skill_path, load_dream_skill


def test_load_skill_with_frontmatter(tmp_path: Path) -> None:
    target = tmp_path / 'SKILL.md'
    target.write_text(
        dedent(
            '''
            ---
            domain: hiring
            version: 1.0
            max_candidates_per_pass: 3
            max_experiments_per_pass: 9
            ---
            Look for recurring rejection patterns.
            '''
        ).lstrip(),
        encoding='utf-8',
    )
    skill = load_dream_skill(target)
    assert skill.domain == 'hiring'
    assert skill.version == '1.0'
    assert skill.max_candidates_per_pass == 3
    assert 'rejection patterns' in skill.body


def test_missing_frontmatter_raises(tmp_path: Path) -> None:
    target = tmp_path / 'SKILL.md'
    target.write_text('just a body, no frontmatter', encoding='utf-8')
    with pytest.raises(DreamSkillLoadError, match='frontmatter'):
        load_dream_skill(target)


def test_loads_hiring_dream_skill_from_repo() -> None:
    skill = load_dream_skill(dream_skill_path('hiring'))
    assert skill.domain == 'hiring'

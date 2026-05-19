from __future__ import annotations

from pathlib import Path
import re

import yaml

from api.server.services.dream_pass.types import DreamSkill


class DreamSkillLoadError(ValueError):
    pass


_FRONTMATTER = re.compile(r'^---\n(.*?)\n---\n?(.*)$', re.DOTALL)


def _repo_root() -> Path:
    here = Path(__file__).resolve()
    for parent in here.parents:
        if (parent / 'pyproject.toml').is_file():
            return parent
    raise DreamSkillLoadError('repository root not found while resolving dream skill path')


def dream_skill_path(domain: str) -> Path:
    root = _repo_root()
    candidates = [
        root / 'api' / 'server' / 'skills' / 'dream-passes' / domain / 'SKILL.md',
        root / 'skills' / 'dream-passes' / domain / 'SKILL.md',
    ]
    for candidate in candidates:
        if candidate.is_file():
            return candidate
    return candidates[0]


def load_dream_skill(path: Path | str) -> DreamSkill:
    target = Path(path)
    if not target.exists():
        raise DreamSkillLoadError(f'dream skill file not found: {target}')
    text = target.read_text(encoding='utf-8')
    match = _FRONTMATTER.match(text)
    if match is None:
        raise DreamSkillLoadError(f'dream skill {target}: missing YAML frontmatter')
    fm = yaml.safe_load(match.group(1)) or {}
    body = match.group(2).strip()
    for required in ('domain', 'version', 'max_candidates_per_pass', 'max_experiments_per_pass'):
        if required not in fm:
            raise DreamSkillLoadError(
                f"dream skill {target}: frontmatter missing '{required}'"
            )
    return DreamSkill(
        domain=str(fm['domain']),
        version=str(fm['version']),
        max_candidates_per_pass=int(fm['max_candidates_per_pass']),
        max_experiments_per_pass=int(fm['max_experiments_per_pass']),
        body=body,
    )

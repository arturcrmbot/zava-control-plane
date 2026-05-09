"""Test-side loader for compose-domain v4 sub-skill modules.

The skill directory layout uses hyphenated names (`compose-domain`,
`author-domain-skeleton`, ...) that aren't valid Python identifiers,
so we can't `import docs.superpowers...` directly. This conftest
exposes a helper that loads modules by file path via
:mod:`importlib.util` and registers them under stable names so
intra-skill imports (e.g. `from _shared.brief_validator import ...`)
still resolve.
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from typing import Any

import pytest

REPO_ROOT = Path(__file__).resolve().parents[5]
SUB_SKILLS_DIR = (
    REPO_ROOT / "docs" / "superpowers" / "skills" / "compose-domain" / "sub-skills"
)


def _load(module_name: str, path: Path) -> Any:
    if module_name in sys.modules:
        return sys.modules[module_name]
    spec = importlib.util.spec_from_file_location(module_name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"failed to load module spec at {path}")
    mod = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = mod
    spec.loader.exec_module(mod)
    return mod


# Pre-load _shared so sub-skill modules can `from _shared.brief_validator import ...`.
_load(
    "_shared",
    SUB_SKILLS_DIR / "_shared" / "__init__.py",
)
_load(
    "_shared.brief_validator",
    SUB_SKILLS_DIR / "_shared" / "brief_validator.py",
)


@pytest.fixture(scope="session")
def sub_skill_loader():
    """Return a callable ``load(sub_skill_name, module_name) -> module``."""

    def _loader(sub_skill: str, module: str) -> Any:
        path = SUB_SKILLS_DIR / sub_skill / f"{module}.py"
        # Use the on-disk hyphenated name in sys.modules to avoid collisions.
        registry_name = f"compose_domain_v4__{sub_skill.replace('-', '_')}__{module}"
        return _load(registry_name, path)

    return _loader


@pytest.fixture(scope="session")
def shared_validator():
    return sys.modules["_shared.brief_validator"]

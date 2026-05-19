"""Load and validate rubric YAML files."""
from __future__ import annotations

from pathlib import Path
from typing import Any, get_args

import yaml

from api.server.services.scoring.types import CheckKind, Rubric, RubricCheck


class RubricLoadError(ValueError):
    """Raised when a rubric YAML is missing or malformed."""


_VALID_KINDS = set(get_args(CheckKind))


def load_rubric(path: Path) -> Rubric:
    if not path.exists():
        raise RubricLoadError(f"rubric file not found: {path}")
    raw = yaml.safe_load(path.read_text())
    if not isinstance(raw, dict):
        raise RubricLoadError(f"rubric {path} must be a YAML mapping at top level")

    domain = raw.get("domain")
    if not isinstance(domain, str) or not domain:
        raise RubricLoadError(f"rubric {path}: 'domain' must be a non-empty string")

    threshold = raw.get("promotion_threshold")
    if not isinstance(threshold, (int, float)):
        raise RubricLoadError(f"rubric {path}: 'promotion_threshold' must be a number")

    min_samples = raw.get("min_samples")
    if not isinstance(min_samples, int) or min_samples <= 0:
        raise RubricLoadError(f"rubric {path}: 'min_samples' must be a positive int")

    checks_raw = raw.get("checks") or []
    if not isinstance(checks_raw, list) or not checks_raw:
        raise RubricLoadError(f"rubric {path}: 'checks' must contain at least one check")

    checks = tuple(_parse_check(path, c) for c in checks_raw)

    return Rubric(
        domain=domain,
        promotion_threshold=float(threshold),
        min_samples=min_samples,
        checks=checks,
    )


def _parse_check(path: Path, raw: Any) -> RubricCheck:
    if not isinstance(raw, dict):
        raise RubricLoadError(f"rubric {path}: each check must be a mapping")
    name = raw.get("name")
    kind = raw.get("kind")
    weight = raw.get("weight", 1.0)
    params = raw.get("params") or {}
    if not isinstance(name, str) or not name:
        raise RubricLoadError(f"rubric {path}: check missing 'name'")
    if kind not in _VALID_KINDS:
        raise RubricLoadError(
            f"rubric {path}: check '{name}' has unknown kind '{kind}'. "
            f"Valid kinds: {sorted(_VALID_KINDS)}"
        )
    if not isinstance(weight, (int, float)) or weight <= 0:
        raise RubricLoadError(f"rubric {path}: check '{name}' weight must be > 0")
    if not isinstance(params, dict):
        raise RubricLoadError(f"rubric {path}: check '{name}' params must be a mapping")
    return RubricCheck(name=name, kind=kind, weight=float(weight), params=params)

"""Config + safety helpers for the Visual Domain Composer (localhost-only)."""
from __future__ import annotations

import os
from pathlib import Path


def repo_root() -> Path:
    return Path(os.getenv("ZAVA_REPO_ROOT", os.getcwd())).resolve()


def poc_safety_ok() -> bool:
    marker = repo_root() / ".poc-safety"
    return marker.exists() and "POC_UNSAFE_FOR_PUBLIC_DEPLOY=1" in marker.read_text()


def permission_policy() -> str:
    """`autopilot` (v1 default, --allow-all) or `in_repo_only` (stricter)."""
    val = os.getenv("COMPOSE_PERMISSION_POLICY", "autopilot").strip()
    return val if val in ("autopilot", "in_repo_only") else "autopilot"


def is_in_repo(path: str) -> bool:
    try:
        Path(path).resolve().relative_to(repo_root())
        return True
    except (ValueError, OSError):
        return False

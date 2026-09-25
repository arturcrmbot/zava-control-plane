"""Persona judgement: Laya reads fast, code checks the record, an LLM takes the unclear rest.

Off unless ``JUDGEMENT_ENABLED=1``. With it off every caller behaves exactly as
before this package existed.
"""
from __future__ import annotations

import os

_TRUTHY = {"1", "true", "yes", "on"}


def judgement_enabled() -> bool:
    return os.environ.get("JUDGEMENT_ENABLED", "0").strip().lower() in _TRUTHY

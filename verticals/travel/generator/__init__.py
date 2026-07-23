"""Hand-authored generator package for the Travel vertical pack.

Everything under `verticals/travel/generator/` is source, never a
generation target. `render.py` implements the deterministic generation
logic; this module re-exports its public API. Run via
`uv run python -m verticals.travel.generator`.
"""
from __future__ import annotations

from .render import (
    GENERATOR_VERSION,
    ExternalOutputNotApprovedError,
    UnsafeCleanupTargetError,
    classify_output_path,
    clean,
    generate,
)

__all__ = [
    "GENERATOR_VERSION",
    "ExternalOutputNotApprovedError",
    "UnsafeCleanupTargetError",
    "classify_output_path",
    "clean",
    "generate",
]

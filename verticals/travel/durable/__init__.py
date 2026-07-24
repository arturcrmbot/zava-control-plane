"""Travel pack durable process engine (generated).

Re-exports the real Azure Durable Functions app
(`verticals.travel.durable.functions.app`) so
`VerticalPack.durable_functions.load_module()` -- as wired through root
`function_app.py` -- can resolve this package directly to `.app`, per the
repository's dynamic selected-pack registration mechanism (never a
hand-patched global registry). The pure, framework-free phase-plan
simulator (`engine.py`/`orchestrators.py`) stays available underneath,
untouched by Task 6.

Do not hand-edit -- change verticals.travel.generator.durable_templates
and regenerate via `uv run python -m verticals.travel.generator`.
"""
from __future__ import annotations

from verticals.travel.durable.functions import app

__all__ = ["app"]

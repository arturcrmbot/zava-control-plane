# src/functions/graphs/executors/validators/validate_creative_stub.py
"""Placeholder schema validator for the POC3 creative-campaign spine.

Each of the five agentic phases pairs the agent stub with this validator
so the graph wiring (TrackedExecutor agent -> TrackedExecutor validator
-> TerminalExecutor) matches the existing pattern. v1 is permissive —
returns ok=True as long as the agent emitted any payload — because the
real per-phase schema validators land in Phase 4 of
plan/feature-poc3-ai-agency-1.md alongside the real skills.
"""
from __future__ import annotations


async def execute(input: dict) -> dict:
    """Permissive validator: ok=True when the agent stub returned a phase
    tag. The phase-specific real validators (one per agentic phase) land
    in Phase 4."""
    phase = input.get("phase")
    if not phase:
        return {"ok": False, "blocked_reason": "missing phase tag from agent"}
    return {"ok": True, "validated_phase": phase}

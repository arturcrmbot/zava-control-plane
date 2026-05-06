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
    in Phase 4.

    Returns the agent's input merged with the validator verdict so the
    orchestrator's downstream consumers (HITL gate persona, FastAPI
    payload-stash route) can read both the agent's structured output
    AND the validator's ok/blocked_reason in a single dict. Same shape
    the real per-phase validators in Phase 4 will produce.
    """
    phase = input.get("phase")
    if not phase:
        return {**input, "ok": False, "blocked_reason": "missing phase tag from agent"}
    return {**input, "ok": True, "validated_phase": phase}

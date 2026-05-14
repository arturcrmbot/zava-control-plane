# src/functions/graphs/executors/agents/agent_hiring_stub.py
"""Placeholder agent for the POC2 hiring spine.

Each of the 10 hiring-phase graphs (budget, job_design, sourcing, triage,
screening, voice, interview, compliance, offer, onboarding) wires this agent
into its `agent` slot so the workflow runs end-to-end before per-phase skills
land. Returns a deterministic stub payload tagged with the phase so the UI's
Execution Timeline still has something to render.

Replaced per-track in Track A (domain rebind) by real GHCP-SDK agents loading
the per-phase SKILL.md (jd-drafter, cv-crystalliser, auto-shortlister, ...).
"""
from __future__ import annotations


async def execute(input: dict) -> dict:
    phase = input.get("phase") or "unknown"
    hire_id = input.get("hire_id") or input.get("workflow_id") or "?"
    return {
        "phase": phase,
        "hire_id": hire_id,
        "stub": True,
        "summary": f"hiring spine stub agent ran for phase={phase}",
    }

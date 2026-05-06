"""Governance core for the substrate.

This package wraps the Microsoft Agent Governance Toolkit (AGT, v3.4.x)
and exposes a single in-process kernel that mediates every MCP tool call,
every persona authority resolution, and every audit-ledger write across
the substrate.

Why this exists
---------------
Per ``plan/feature-agent-governance-toolkit-1.md`` (CON-002 / RISK-001):
this package is the **only** import site for ``agent_os.*``,
``agentmesh.*``, ``agent_sre.*``, ``agent_compliance.*`` modules across
the entire codebase. Every other module talks to AGT through the
``GovernanceKernel`` re-exported from here. That keeps a future
breaking-version bump of AGT to a single-file diff, and keeps the
"swap policy backend" claim honest — callers know nothing about Cedar
vs OPA vs YAML.

Public surface
--------------
- ``GovernanceKernel``   The kernel class. Reentrant, thread-safe.
- ``Decision``           Pydantic record of one policy evaluation.
- ``GovernanceDenied``   Exception raised in enforce mode on a deny.
- ``kernel()``           Module-level singleton accessor.
- ``init_governance()``  Idempotent boot hook called from FastAPI's
                         lifespan and from the Functions worker module
                         load.

Phase 1 status
--------------
This is the wiring-only skeleton. ``evaluate_tool_call`` returns
``allowed=True`` for every input regardless of args; the policy bundle
lands in Phase 2 (TASK-008..TASK-019). The kernel is intentionally
useful enough to be wired into call sites in Phase 2 without changing
its public shape.
"""
from __future__ import annotations

from .kernel import (
    Decision,
    GovernanceDenied,
    GovernanceKernel,
    kernel,
)
from .boot import init_governance

__all__ = [
    "Decision",
    "GovernanceDenied",
    "GovernanceKernel",
    "init_governance",
    "kernel",
]

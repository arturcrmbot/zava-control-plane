"""
Deterministic exception composition.

The control plane composes an Exception record the moment a workflow
suspends for HITL approval or a validator blocks it. This guarantees the
operator queue never depends on an LLM call firing — the Fleet Manager
may augment the record later, but the record exists first.
"""
from __future__ import annotations
import time
from nanoid import generate as nanoid
from api.server.services.state_store import StateStore
from api.shared.types import Exception_ as Exception, ExceptionOption


def compose_hitl_exception(store: StateStore, workflow_id: str, reason: str) -> Exception:
    """Compose a deterministic HITL exception when a workflow suspends for approval."""
    e = Exception(
        id=f"EXC-{nanoid(size=8)}",
        workflow_id=workflow_id,
        composed_by="deterministic",
        severity="medium",
        category="threshold-exceeded",
        summary=f"Workflow suspended for approval: {reason}",
        recommendation="Awaiting Fleet Manager reasoning.",
        options=[
            ExceptionOption(label="Approve", action="approve",
                            recommended=True, non_revocable=True),
            ExceptionOption(label="Request additional docs", action="request-info"),
            ExceptionOption(label="Escalate to approver L2", action="escalate"),
            ExceptionOption(label="Reject", action="reject", non_revocable=True),
        ],
        related_policy_refs=[],
        confidence=1.0,
        created_at=time.time(),
    )
    store.upsert_exception(e)
    return e


def compose_validator_exception(
    store: StateStore, workflow_id: str, validator: str, reason: str
) -> Exception:
    """Compose a deterministic exception when a validator blocks a workflow."""
    e = Exception(
        id=f"EXC-{nanoid(size=8)}",
        workflow_id=workflow_id,
        composed_by="deterministic",
        severity="high",
        category="validator-blocked",
        summary=f"Validator '{validator}' blocked workflow: {reason}",
        recommendation="Awaiting Fleet Manager reasoning.",
        options=[
            ExceptionOption(label="Re-route to GL specialist", action="reroute-gl",
                            recommended=True),
            ExceptionOption(label="Approve override", action="approve",
                            non_revocable=True),
            ExceptionOption(label="Request vendor info", action="request-info"),
            ExceptionOption(label="Escalate to CFO", action="escalate"),
            ExceptionOption(label="Reject", action="reject", non_revocable=True),
        ],
        related_policy_refs=[],
        confidence=1.0,
        created_at=time.time(),
    )
    store.upsert_exception(e)
    return e

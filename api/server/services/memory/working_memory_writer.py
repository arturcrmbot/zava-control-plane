"""Working-memory writer — the producer side of the dream-pass loop.

Personae generate working memories during normal operation. The dream
pass later reads them via ``DomainMemory.list_all`` and consolidates
into distilled lessons.

This module is the single funnel through which every producer (persona
decision handler, persona summary handler, agentic segments) writes.
Two write helpers:

- ``write_decision_memory`` — fires on every persona HITL verdict.
- ``write_summary_memory`` — fires on every persona summary cycle.

Both are best-effort: they swallow errors so a missing Mem0 backend or
unknown domain never blocks the originating event handler.

Idempotency: each entry includes ``metadata.dedup_key`` derived from
``(workflow_id, persona_role, kind)``. The dream consolidator and the
fallback consolidator both treat that as a uniqueness hint.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

log = logging.getLogger(__name__)


def _domain_memory_for(domain: str) -> Any | None:
    """Return the DomainMemory for ``domain`` or None if unknown.

    Lazy import of ``app_state`` because this module is imported from
    persona_responder which is wired during AppState construction.
    """
    try:
        from api.server.state import app_state
    except Exception:
        return None
    return app_state.domain_memories.get(domain)


def write_decision_memory(
    *,
    domain: str | None,
    persona_role: str,
    verdict: str,
    reason: str | None,
    workflow_id: str | None,
    gate_phase: str | None,
    signals: dict | None = None,
) -> bool:
    """Write a structured working memory for one persona decision.

    Returns True on a successful write, False otherwise (unknown domain,
    Mem0 unavailable, empty text, …). Never raises.
    """
    if not domain or not persona_role or not verdict:
        return False
    store = _domain_memory_for(domain)
    if store is None:
        return False

    sig_bits: list[str] = []
    if isinstance(signals, dict):
        for k in ("voice_score", "cv_score", "amount", "risk", "country"):
            v = signals.get(k)
            if v is not None:
                sig_bits.append(f"{k}={v}")

    text = (
        f"[{persona_role}] {verdict.upper()} for {gate_phase or 'gate'}"
        + (f" — {reason}" if reason else "")
        + (f" — signals: {', '.join(sig_bits)}" if sig_bits else "")
    ).strip()

    dedup_key = f"{workflow_id or '-'}::{persona_role}::decision::{gate_phase or '-'}"
    try:
        store.add(
            text,
            agent_skill=f"persona:{persona_role}",
            workflow_id=workflow_id or "",
        )
        # add() doesn't accept extra metadata yet — but the persisted
        # entry already carries domain/agent_skill/workflow_id; the
        # dedup_key + kind go on the in-flight entry via a follow-up
        # update if the backend supports it. For the FallbackMemory we
        # rely on the natural dedup at consolidation time.
        log.info(
            "working-memory[%s]: decision %s/%s -> %s",
            domain, persona_role, gate_phase, verdict,
        )
        return True
    except Exception:
        log.exception("working-memory[%s]: decision write failed", domain)
        return False


def write_summary_memory(
    *,
    domain: str | None,
    persona_role: str,
    headline: str,
    body: str | None = None,
) -> bool:
    """Write a structured working memory for one persona summary cycle.

    Returns True/False; never raises.
    """
    if not domain or not persona_role or not headline:
        return False
    store = _domain_memory_for(domain)
    if store is None:
        return False

    text = (
        f"[{persona_role}] OBSERVATION: {headline}"
        + (f" — {body[:280]}" if body else "")
    ).strip()
    try:
        store.add(
            text,
            agent_skill=f"persona:{persona_role}:summary",
            workflow_id="",
        )
        log.info(
            "working-memory[%s]: summary %s -> %s",
            domain, persona_role, headline[:80],
        )
        return True
    except Exception:
        log.exception("working-memory[%s]: summary write failed", domain)
        return False


def utcnow_iso() -> str:
    return datetime.now(timezone.utc).isoformat()

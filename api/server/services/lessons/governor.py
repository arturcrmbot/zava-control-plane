"""LessonGovernor — the one path the dream pass uses to write lessons.

Wraps a LessonStore with:
  1. AGT policy evaluation on every write/prune.
  2. Kuzu provenance writes pointing at the runs that birthed the lesson.
  3. ActionLedgerEntry writes for the signed, hash-chained audit trail.

Never bypass this. Use ``governor.write(lesson)``, never
``store.add(lesson)`` directly.
"""
from __future__ import annotations

from typing import Any, Callable, Protocol

from api.server.services.governance.kernel import (
    Decision,
    GovernanceDenied,
    GovernanceKernel,
)
from api.server.services.lessons.kuzu_provenance import KuzuLessonProvenance
from api.server.services.lessons.store import LessonStore
from api.server.services.lessons.types import Lesson, LessonCandidate


class _AuditLike(Protocol):
    def log(self, action: str, details: Any) -> None: ...


class LessonGovernor:
    """AGT-gated, ledger'd write surface for the lesson tier."""

    def __init__(
        self,
        *,
        store: LessonStore,
        kernel: Callable[[], GovernanceKernel],
        audit: _AuditLike,
        provenance: KuzuLessonProvenance,
        actor: str,
        workflow_id: str = "system:lessons",
    ) -> None:
        self._store = store
        self._kernel_factory = kernel
        self._audit = audit
        self._provenance = provenance
        self._actor = actor
        self._workflow_id = workflow_id

    def write(self, lesson: Lesson) -> None:
        decision = self._kernel_factory().evaluate_tool_call(
            actor=self._actor,
            tool="lesson.write",
            args={
                "lesson_id": lesson.id,
                "domain": lesson.scope.domain,
                "delta": lesson.provenance.rubric_score_delta,
                "n": lesson.provenance.experiment_n,
            },
            workflow_id=self._workflow_id,
        )
        self._enforce(decision)
        # Phase 2 semantics: in log_only mode the write proceeds even on
        # a policy deny — the ledger entry below records the governance
        # outcome so Phase 6 can flip to enforce without surprises.
        self._store.add(lesson)
        self._provenance.record(lesson)
        self._record_ledger(
            decision,
            action="lesson.write",
            details={
                "lesson_id": lesson.id,
                "domain": lesson.scope.domain,
                "delta": lesson.provenance.rubric_score_delta,
                "n": lesson.provenance.experiment_n,
            },
        )

    def prune(self, lesson_id: str, *, reason: str) -> None:
        decision = self._kernel_factory().evaluate_tool_call(
            actor=self._actor,
            tool="lesson.prune",
            args={"lesson_id": lesson_id, "reason": reason},
            workflow_id=self._workflow_id,
        )
        self._enforce(decision)
        self._store.prune(lesson_id, reason=reason)
        self._provenance.mark_pruned(lesson_id, reason=reason)
        self._record_ledger(
            decision,
            action="lesson.prune",
            details={"lesson_id": lesson_id, "reason": reason},
        )

    def _enforce(self, decision: Decision) -> None:
        if decision.allowed:
            return
        if decision.enforcement_mode == "enforce":
            raise GovernanceDenied(decision)
        # log_only: caller proceeds; ledger entry below records the deny.

    # ------------------------------------------------------------------
    # D1 exception portal: flagged-candidate surfaces.
    # ------------------------------------------------------------------

    def write_flagged_candidate(
        self,
        *,
        candidate: LessonCandidate,
        experiment_id: str,
        delta: float,
        n: int,
        flag_reason: str,
    ) -> None:
        """Persist a candidate lesson with status='candidate' for human review."""
        decision = self._kernel_factory().evaluate_tool_call(
            actor=self._actor,
            tool="lesson.write",
            args={
                "lesson_id": candidate.id,
                "domain": candidate.scope.domain,
                "flag_reason": flag_reason,
            },
            workflow_id=self._workflow_id,
        )
        self._enforce(decision)
        self._provenance.record_candidate(
            candidate_id=candidate.id,
            body=candidate.body,
            domain=candidate.scope.domain,
            persona_role=candidate.scope.persona_role or "",
            market=candidate.scope.market or "",
            proposed_by=candidate.proposed_by,
            experiment_id=experiment_id,
            delta=delta,
            n=n,
            flag_reason=flag_reason,
        )
        self._record_ledger(
            decision,
            action="lesson.flag_candidate",
            details={
                "lesson_id": candidate.id,
                "domain": candidate.scope.domain,
                "flag_reason": flag_reason,
                "delta": delta,
                "n": n,
                "experiment_id": experiment_id,
            },
        )

    def approve_flagged(self, *, lesson_id: str, approver: str) -> None:
        """Operator action: promote a status='candidate' Lesson to active."""
        decision = self._kernel_factory().evaluate_tool_call(
            actor=self._actor,
            tool="lesson.approve_flagged",
            args={"lesson_id": lesson_id, "approver": approver},
            workflow_id=self._workflow_id,
        )
        self._enforce(decision)
        candidate = self._provenance.fetch_candidate(lesson_id)
        if candidate is None:
            raise LookupError(f"no candidate lesson found with id {lesson_id}")
        # Re-record as active (status flips from 'candidate' to 'active').
        from dataclasses import replace as _replace
        active = _replace(candidate, status="active")
        self._store.add(active)
        self._provenance.record(active)
        self._record_ledger(
            decision,
            action="lesson.approve_flagged",
            details={"lesson_id": lesson_id, "approver": approver},
        )

    def reject_flagged(
        self, *, lesson_id: str, reviewer: str, reason: str
    ) -> None:
        """Operator action: prune a status='candidate' Lesson permanently."""
        decision = self._kernel_factory().evaluate_tool_call(
            actor=self._actor,
            tool="lesson.reject_flagged",
            args={
                "lesson_id": lesson_id,
                "reviewer": reviewer,
                "reason": reason,
            },
            workflow_id=self._workflow_id,
        )
        self._enforce(decision)
        self._provenance.mark_pruned(
            lesson_id, reason=f"rejected_by_review: {reason}"
        )
        self._record_ledger(
            decision,
            action="lesson.reject_flagged",
            details={
                "lesson_id": lesson_id,
                "reviewer": reviewer,
                "reason": reason,
            },
        )

    def _record_ledger(
        self,
        decision: Decision,
        *,
        action: str,
        details: dict[str, Any],
    ) -> None:
        # Audit logger's contract is log(action: str, details: Any). Pack
        # workflow_id + governance metadata into the details dict so the
        # hash chain and JWS signing pick them up.
        enriched = {
            **details,
            "workflow_id": self._workflow_id,
            "actor_kind": "agent",
            "actor_id": self._actor,
            "revocable": True,
            "decision_id": decision.decision_id,
            "policy_version": decision.policy_version,
            "enforcement_mode": decision.enforcement_mode,
            "governance_action": decision.action,
            "governance_allowed": decision.allowed,
        }
        self._audit.log(action, enriched)

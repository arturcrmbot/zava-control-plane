# src/server/mcp_tools/compose_exception.py
from __future__ import annotations
import json
import time
from typing import Any
from pydantic import BaseModel, Field
from nanoid import generate as nanoid
from copilot.tools import define_tool, ToolInvocation, ToolResult
from src.server.services.state_store import StateStore
from src.server.services.audit_logger import AuditLogger
from src.shared.types import Exception_ as Exception, ExceptionOption, PolicyRef


class ComposeExceptionParams(BaseModel):
    workflow_id: str
    severity: str = Field(description="critical | high | medium")
    category: str = Field(description="Exception category enum value")
    summary: str
    recommendation: str
    options: list[dict[str, Any]] | None = None
    related_policy_refs: list[dict[str, Any]] | None = None
    bulk_candidate_ids: list[str] | None = None
    confidence: float = 0.8


def make_compose_exception_tool(store: StateStore, audit: AuditLogger):
    @define_tool(description="Write an exception to the operator's queue.", skip_permission=True)
    def compose_exception(params: ComposeExceptionParams, invocation: ToolInvocation) -> ToolResult:
        # Hook-gated non-revocable action: pre-audit BEFORE write.
        audit.log("compose-exception.pre", {"workflow_id": params.workflow_id})
        e = Exception(
            id=f"EXC-{nanoid(size=8)}",
            workflow_id=params.workflow_id,
            composed_by="fleet-manager",
            severity=params.severity,  # type: ignore[arg-type]
            category=params.category,  # type: ignore[arg-type]
            summary=params.summary,
            recommendation=params.recommendation,
            options=[ExceptionOption(**o) for o in (params.options or [
                {"label": "Approve", "action": "approve", "non_revocable": False},
                {"label": "Reject", "action": "reject", "non_revocable": False},
            ])],
            related_policy_refs=[PolicyRef(**r) for r in (params.related_policy_refs or [])],
            bulk_candidate_ids=params.bulk_candidate_ids,
            confidence=params.confidence,
            created_at=time.time(),
        )
        store.upsert_exception(e)
        audit.log("compose-exception.emitted", {"exception_id": e.id, "workflow_id": e.workflow_id})
        return ToolResult(text_result_for_llm=json.dumps({"exception_id": e.id}), result_type="success")

    return compose_exception

# src/shared/types.py
from __future__ import annotations
from typing import Literal
from pydantic import BaseModel, Field

PhaseName = Literal["Intake", "Validation", "Routing", "Approval", "Payment", "Reconciliation"]

PHASE_ORDER: list[PhaseName] = [
    "Intake", "Validation", "Routing", "Approval", "Payment", "Reconciliation"
]

WorkflowStatus = Literal["in_progress", "awaiting_hitl", "completed", "failed"]
Severity = Literal["critical", "high", "medium"]
ExceptionCategory = Literal[
    "duplicate-invoice", "po-mismatch", "threshold-exceeded",
    "sanctions-flag", "compliance", "payment-timeout", "validator-blocked"
]


class Vendor(BaseModel):
    id: str
    name: str
    country: str


class InvoiceLineItem(BaseModel):
    description: str
    qty: float
    unit_price: float


class InvoiceData(BaseModel):
    number: str
    amount: float
    currency: str
    line_items: list[InvoiceLineItem] = Field(default_factory=list)
    po_ref: str


class ToolCall(BaseModel):
    tool: str
    args_preview: str
    ms: int
    ok: bool


class ActionLedgerEntry(BaseModel):
    workflow_id: str
    timestamp: float
    actor_kind: Literal["agent", "human"]
    actor_id: str
    action: str
    revocable: bool
    details: dict


class Workflow(BaseModel):
    id: str
    type: Literal["invoice-p2p"] = "invoice-p2p"
    status: WorkflowStatus = "in_progress"
    current_phase: PhaseName = "Intake"
    created_at: float
    sla_due_at: float
    vendor: Vendor
    invoice: InvoiceData
    jurisdiction: str
    agency: str
    active_exception_id: str | None = None
    action_ledger: list[ActionLedgerEntry] = Field(default_factory=list)
    tokens_spent: int = 0
    cost_usd: float = 0.0
    orchestration_instance_id: str | None = None


class Phase(BaseModel):
    workflow_id: str
    name: PhaseName
    status: Literal["pending", "in_progress", "completed", "failed"] = "pending"
    started_at: float | None = None
    completed_at: float | None = None
    agent_id: Literal["finance-agent"] = "finance-agent"
    tool_calls: list[ToolCall] = Field(default_factory=list)
    span_ids: list[str] = Field(default_factory=list)


class OtelSpan(BaseModel):
    trace_id: str
    span_id: str
    parent_span_id: str | None = None
    name: str
    start_ms: float
    end_ms: float
    attributes: dict
    status: Literal["ok", "error"] = "ok"


class ExceptionOption(BaseModel):
    label: str
    action: str
    non_revocable: bool = False


class PolicyRef(BaseModel):
    title: str
    snippet: str
    source: str


class Exception_(BaseModel):
    id: str
    workflow_id: str
    composed_by: Literal["fleet-manager", "guardrail", "simulator-injected", "validator"]
    severity: Severity
    category: ExceptionCategory
    summary: str
    recommendation: str
    options: list[ExceptionOption] = Field(default_factory=list)
    related_policy_refs: list[PolicyRef] = Field(default_factory=list)
    bulk_candidate_ids: list[str] | None = None
    confidence: float = 0.8
    created_at: float
    resolved_at: float | None = None
    resolved_by: str | None = None


class SkillAmplification(BaseModel):
    id: str
    workflow_id: str
    policy_context: list[PolicyRef] = Field(default_factory=list)
    precedents: list[dict] = Field(default_factory=list)
    recommended_approach: str
    created_at: float


class AutonomyPolicy(BaseModel):
    id: str
    description: str
    current_value: float | str | bool
    git_sha: str
    author: str
    updated_at: float


def next_phase(p: PhaseName) -> PhaseName | None:
    i = PHASE_ORDER.index(p) if p in PHASE_ORDER else -1
    if i < 0 or i >= len(PHASE_ORDER) - 1:
        return None
    return PHASE_ORDER[i + 1]

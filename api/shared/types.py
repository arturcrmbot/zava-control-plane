# src/shared/types.py
from __future__ import annotations
from typing import Literal
from pydantic import BaseModel as _PydBaseModel, ConfigDict, Field
from pydantic.alias_generators import to_camel


class BaseModel(_PydBaseModel):
    """All shared models serialize as camelCase for the React UI but still
    accept snake_case on construction. Route handlers must call
    `model_dump(by_alias=True)` to emit camelCase."""
    model_config = ConfigDict(
        alias_generator=to_camel,
        populate_by_name=True,
    )

PhaseName = Literal[
    # Invoice P2P (legacy — orchestrator deleted, kept for any in-flight workflow records)
    "Intake", "Validation", "Routing", "Approval", "Payment", "Reconciliation",
    # Expense compliance (POC1 — see api/functions/workflows/expense_claim.py)
    "Classify", "Validate Receipt", "Route", "Notify", "Arbitrate", "Audit",
    # Hiring (POC2 — see api/functions/workflows/hiring.py)
    "Budget", "Job Design", "Sourcing", "Triage", "Screening",
    "Voice", "Interview", "Compliance", "Offer", "Onboarding",
]

PHASE_ORDER: list[PhaseName] = [
    "Intake", "Validation", "Routing", "Approval", "Payment", "Reconciliation"
]

EXPENSE_PHASE_ORDER: list[PhaseName] = [
    "Intake", "Classify", "Validate Receipt", "Route", "Notify", "Arbitrate", "Audit",
]

HIRING_PHASE_ORDER: list[PhaseName] = [
    "Budget", "Job Design", "Sourcing", "Triage", "Screening",
    "Voice", "Interview", "Compliance", "Offer", "Onboarding",
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


class ClaimData(BaseModel):
    """Expense claim payload — replaces InvoiceData on Workflow.type='expense-claim'."""
    claim_id: str
    employee_id: str
    submitted_at: str
    market: Literal["UK", "US", "DE", "IN"]
    currency: str
    category: Literal["meals", "travel", "accommodation", "entertainment", "miscellaneous"]
    vendor: str
    amount: float
    attendees: int = 1
    receipt_filename: str | None = None
    receipt_mismatch_flavour: str | None = None
    ems_source: Literal["workday", "concur"]


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
    type: Literal["invoice-p2p", "expense-claim", "hiring"] = "expense-claim"
    status: WorkflowStatus = "in_progress"
    current_phase: PhaseName = "Intake"
    created_at: float
    sla_due_at: float
    # Invoice payload — set on type="invoice-p2p"; absent on expense claims.
    vendor: Vendor | None = None
    invoice: InvoiceData | None = None
    # Expense payload — set on type="expense-claim"; absent on invoice workflows.
    claim: ClaimData | None = None
    verdict: Literal["green", "amber", "red"] | None = None
    jurisdiction: str
    agency: str
    active_exception_id: str | None = None
    action_ledger: list[ActionLedgerEntry] = Field(default_factory=list)
    tokens_spent: int = 0
    cost_usd: float = 0.0
    orchestration_instance_id: str | None = None
    # POC2 hiring stash — candidate id, role family, jurisdiction. Absent on
    # POC1 workflows so the field is fully additive.
    metadata: dict = Field(default_factory=dict)


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


class McpCall(BaseModel):
    workflow_id: str
    timestamp: float
    tool: str
    url: str
    method: str = "POST"
    request: dict
    response: dict
    status_code: int
    duration_ms: int


class ExceptionOption(BaseModel):
    label: str
    action: str
    non_revocable: bool = False
    recommended: bool = False


class PolicyRef(BaseModel):
    title: str
    snippet: str
    source: str


class Exception_(BaseModel):
    id: str
    workflow_id: str
    composed_by: Literal[
        "fleet-manager", "guardrail", "simulator-injected", "validator",
        "deterministic", "fleet-manager-augmented"
    ]
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

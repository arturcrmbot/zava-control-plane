# src/shared/types.py
from __future__ import annotations
import warnings
from typing import Literal
from pydantic import BaseModel as _PydBaseModel, ConfigDict, Field, field_validator
from pydantic.alias_generators import to_camel


class BaseModel(_PydBaseModel):
    """All shared models serialize as camelCase for the React UI but still
    accept snake_case on construction. Route handlers must call
    `model_dump(by_alias=True)` to emit camelCase."""
    model_config = ConfigDict(
        alias_generator=to_camel,
        populate_by_name=True,
    )

# Phase names. Was a `Literal[...]` whitelist of the two hand-built domains'
# phases (Invoice P2P, expense, hiring) — but compose-domain v1 generated
# domains add their own phase names (e.g. "Employee Lookup", "Policy Fit
# Check"), and there is no value in maintaining the whitelist for them.
# `Phase.name` is now `str`; the whitelist below stays only as documentation
# of the hand-built phases and as the PHASE_ORDER source for the legacy
# invoice flow (which is the only caller of `next_phase()`).
PhaseName = str

# Hand-built phases — kept as a string list, not a Literal, so it documents
# what's used by the two original orchestrators without constraining the
# generated ones.
HAND_BUILT_PHASES: list[str] = [
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
    # type is the registry key (api.shared.domains.DOMAINS). Was a Literal
    # union of the eight known workflow_types; widened to `str` so adding a
    # 9th domain is a registry edit, not a types.py edit. The runtime asserts
    # `type in DOMAINS` via the model_validator below.
    type: str = "expense-claim"
    status: WorkflowStatus = "in_progress"
    current_phase: PhaseName = "Intake"
    created_at: float
    sla_due_at: float
    # Domain-agnostic opaque payload. New code (fleet-* domains and any
    # post-registry domain) writes its inputs here. POC1/POC2 keep using the
    # typed fields below for back-compat; new domains leave those None.
    payload: dict = Field(default_factory=dict)
    # --- Deprecated typed payload fields. Kept for one release for back-compat
    # with POC1 expense (`claim`) and the legacy invoice path (`vendor`,
    # `invoice`). New code reads from `payload` instead. See
    # api/shared/domains.py for the canonical per-domain shape.
    vendor: Vendor | None = None
    invoice: InvoiceData | None = None
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
    # POC2 §4.21 AG-UI: per-agent structured outputs lifted onto the workflow
    # ledger so the Control Plane can render them. Keyed by agent name (e.g.
    # "cv_crystalliser"); each value carries the canonical agent payload incl.
    # an optional `component_spec` array of AgentComponentSpec entries.
    agent_outputs: dict = Field(default_factory=dict)
    # Per-agent reasoning trace — one entry per agent.completed event from the
    # agent-tracked-executor wrapper. Each entry has: agent_label, phase,
    # started_at, completed_at, messages (full chat stream), tool_calls,
    # extracted_json, latency_ms, tokens. Append-only; re-runs are kept.
    # Generic platform field — every domain that uses the wrapper benefits.
    agent_reasoning: list = Field(default_factory=list)

    @field_validator("type")
    @classmethod
    def _check_type_against_registry(cls, v: str) -> str:
        """Warn (don't raise) when `type` isn't a registered domain.

        Imported lazily to avoid an import cycle if domains.py later wants
        to reference shared types. Allows legacy `invoice-p2p` to keep
        constructing for the in-flight workflow records the old orchestrator
        left behind. Phase 1 of feature-fleet-domain-substrate-1.
        """
        from api.shared import domains as _domains  # local import on purpose
        if v in _domains.DOMAINS or v == "invoice-p2p":
            return v
        warnings.warn(
            f"Workflow.type={v!r} is not registered in api.shared.domains.DOMAINS; "
            f"the FM and operator UI will not surface this domain correctly.",
            DeprecationWarning,
            stacklevel=2,
        )
        return v


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

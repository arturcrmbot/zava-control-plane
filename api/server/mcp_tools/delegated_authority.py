"""delegated_authority MCP tool — resolve approver and check authority.

This is the MCP-tool seam for the substrate's delegated-authority matrix.
The matrix data lives in `data/synthetic/authority/matrix.json`; the
in-process governance kernel
([api/server/services/governance/kernel.py](../services/governance/kernel.py))
walks it (Phase 3, TASK-022); this Python wrapper exposes that surface
to agent skills (via `@define_tool`) and to the persona responder (via
the plain `resolve_approver` / `check_authority` callables).

Two operations:
  - `resolve_approver(action, value, category, requester_role, business_unit, geography) -> ApproverResolution`
    Walk the matrix and return the first matching rule. Used by skills
    that produce a HITL routing decision — they surface
    `resolved_approver` in their structured output so the persona
    receives an authoritative threshold/approver in `context.authority`.
  - `check_authority(role, action, value, category, business_unit, geography) -> AuthorityCheck`
    Does the named role have authority to sign off this request? Used
    by personae whose decision_policy needs a yes/no answer rather than
    a routing decision.

Skills that consume this tool (audit list — TASK-012):
  - escalation-advisor (POC1)
  - budget-checker (POC2)
  - fleet-travel-preapproval-policy-fit-checker
  - fleet-vendor-kyc-kyc-diligence-checker
  - fleet-it-access-request-access-risk-assessor
  - fleet-contract-renewal-renewal-terms-drafter
  - fleet-employee-onboarding-access-drafter
  - fleet-perf-review-calibration-drafter

Backend selection (Phase 3, TASK-022):
  - Default: in-process via ``governance.kernel().resolve_approver(...)``
    — sub-millisecond, no network hop, same matrix.json source of
    truth as the compiled policy bundle.
  - Fallback: HTTP round-trip to ``$AUTHORITY_MCP_URL`` (preserves the
    Foundry-IQ engagement-POC swap-in seam, REQ-002 of
    plan/feature-agent-governance-toolkit-1.md). Set the env var to a
    Foundry-backed endpoint; the wire format is unchanged so skill +
    persona code keeps working.
"""
from __future__ import annotations

import json
import os
from typing import Optional

import httpx

from ._http import get_client
from copilot.tools import ToolResult, define_tool
from opentelemetry import trace
from pydantic import BaseModel, Field

from ._otel import traced_tool


# Legacy default — kept so ``_base_url()`` (used by /api/authority/health
# only) still points at the local Node mock when nothing's configured.
# No other callers depend on it; routing of resolve/check goes through
# the kernel by default after TASK-022.
_DEFAULT_URL = "http://127.0.0.1:4108"


def _base_url() -> str:
    """Return the configured authority-MCP URL (default: local Node mock).

    Used by the ``/api/authority/health`` proxy route; resolve/check
    no longer route via this URL by default — they prefer the in-process
    kernel and only fall back to HTTP when ``_http_fallback_enabled()``.
    """
    return os.environ.get("AUTHORITY_MCP_URL", _DEFAULT_URL).rstrip("/")


def _http_fallback_enabled() -> bool:
    """True iff ``AUTHORITY_MCP_URL`` is explicitly set in env.

    The presence of the env var is the operator's signal that they want
    the engagement-POC swap-in path (Foundry-IQ-backed MCP). Absent it,
    the in-process governance kernel handles every resolve/check call.
    """
    return bool(os.environ.get("AUTHORITY_MCP_URL"))


# ---------------------------------------------------------------------------
# Pydantic shapes — the contract surface skills + personae read against.
# Do not change without bumping a version comment here; the engagement-POC
# Foundry IQ swap-in must match these field names.
# ---------------------------------------------------------------------------


class ApproverResolution(BaseModel):
    """Result of a resolve_approver call."""

    matched: bool
    approver_role: Optional[str] = None
    threshold_gbp: Optional[float] = None
    escalation_chain: list[str] = Field(default_factory=list)
    rule_id: Optional[str] = None
    basis: Optional[str] = None
    reason: Optional[str] = None  # populated when matched=False


class AuthorityCheck(BaseModel):
    """Result of a check_authority call."""

    allowed: bool
    reason: str
    governing_rule_id: Optional[str] = None


# ---------------------------------------------------------------------------
# Plain-Python callables. Used by the persona responder and tests; the
# @define_tool wrappers below thin-wrap these for SDK-native invocation.
# ---------------------------------------------------------------------------


@traced_tool("authority.resolve_approver")
def resolve_approver(
    action: str,
    value: float | None = None,
    category: str | None = None,
    requester_role: str | None = None,
    business_unit: str | None = None,
    geography: str | None = None,
) -> ApproverResolution:
    """Walk the matrix and return the first matching rule.

    Default backend (Phase 3 TASK-022): in-process governance kernel
    — sub-millisecond, no network hop. HTTP fallback only when
    ``AUTHORITY_MCP_URL`` is set in env (engagement-POC swap-in seam).
    Returns an ``ApproverResolution`` with ``matched=False`` and ``reason``
    populated when no rule matches.
    """
    span = trace.get_current_span()
    span.set_attribute("apex.authority.action", action)
    if category:
        span.set_attribute("apex.authority.category", category)
    if value is not None:
        span.set_attribute("apex.authority.value_gbp", float(value))

    if _http_fallback_enabled():
        # Engagement-POC swap-in path. Wire format unchanged.
        span.set_attribute("apex.authority.backend", "http")
        payload = {
            "action": action,
            "value": value,
            "category": category,
            "requester_role": requester_role,
            "business_unit": business_unit,
            "geography": geography,
        }
        url = f"{_base_url()}/resolve_approver"
        with get_client() as client:
            resp = client.post(url, json=payload)
        resp.raise_for_status()
        body = resp.json()
        result = ApproverResolution(**body)
    else:
        # Default in-process path.
        from api.server.services.governance import kernel  # local: avoid import cycles
        span.set_attribute("apex.authority.backend", "in_process")
        kernel_result = kernel().resolve_approver(
            action=action,
            value=value,
            category=category,
            requester_role=requester_role,
            business_unit=business_unit,
            geography=geography,
        )
        # Re-shape into the local Pydantic class so callers see a single,
        # stable type regardless of backend.
        result = ApproverResolution(**kernel_result.model_dump())

    span.set_attribute("apex.authority.matched", bool(result.matched))
    if result.matched:
        span.set_attribute("apex.authority.rule_id", str(result.rule_id or ""))
        span.set_attribute("apex.authority.approver_role", str(result.approver_role or ""))
    return result


@traced_tool("authority.check_authority")
def check_authority(
    role: str,
    action: str,
    value: float | None = None,
    category: str | None = None,
    business_unit: str | None = None,
    geography: str | None = None,
    requester_role: str | None = None,
) -> AuthorityCheck:
    """Check whether a specific role is authorised for a given action+value+scope.

    Default backend (Phase 3 TASK-022): in-process governance kernel.
    HTTP fallback only when ``AUTHORITY_MCP_URL`` is set in env.
    """
    span = trace.get_current_span()
    span.set_attribute("apex.authority.role", role)
    span.set_attribute("apex.authority.action", action)

    if _http_fallback_enabled():
        span.set_attribute("apex.authority.backend", "http")
        payload = {
            "role": role,
            "action": action,
            "value": value,
            "category": category,
            "business_unit": business_unit,
            "geography": geography,
            "requester_role": requester_role,
        }
        url = f"{_base_url()}/check_authority"
        with get_client() as client:
            resp = client.post(url, json=payload)
        resp.raise_for_status()
        body = resp.json()
        result = AuthorityCheck(**body)
    else:
        from api.server.services.governance import kernel  # local: avoid import cycles
        span.set_attribute("apex.authority.backend", "in_process")
        kernel_result = kernel().check_authority(
            role=role,
            action=action,
            value=value,
            category=category,
            business_unit=business_unit,
            geography=geography,
            requester_role=requester_role,
        )
        result = AuthorityCheck(**kernel_result.model_dump())

    span.set_attribute("apex.authority.allowed", bool(result.allowed))
    return result


# ---------------------------------------------------------------------------
# SDK-native @define_tool wrappers. Skill SKILL.md frontmatter declares
# `allowed-tools: delegated_authority_resolve_approver` (or the check
# variant); agent executors import the corresponding `*_tool` and pass it
# into `tools=[...]`.
# ---------------------------------------------------------------------------


class _ResolveApproverParams(BaseModel):
    action: str = Field(
        description=(
            "What is being approved (snake_case constant). One of: "
            "expense_claim_approval, travel_preapproval, vendor_kyc_signoff, "
            "contract_renewal_signoff, it_access_grant, employee_onboarding_access, "
            "perf_calibration_signoff, hire_budget_approval, hire_offer_approval, "
            "ap_invoice_approval, purchase_order_approval, contract_review_signoff, "
            "privacy_dpia_signoff, internal_mobility_approval, offboarding_signoff, "
            "incident_triage_signoff, access_recertification_signoff, "
            "pitch_resourcing_approval, treasury_fx_hedge."
        )
    )
    value: float | None = Field(
        default=None,
        description="Monetary value in GBP. Omit for non-monetary actions (e.g. it_access_grant).",
    )
    category: str | None = Field(
        default=None,
        description="Sub-classification of the action (e.g. 'meals', 'high_risk', 'privileged_role').",
    )
    requester_role: str | None = Field(
        default=None,
        description="Optional persona role of the requester, used for scope-narrowed rules.",
    )
    business_unit: str | None = Field(
        default=None,
        description="Optional business unit scope (e.g. 'production', 'media').",
    )
    geography: str | None = Field(
        default=None,
        description="Optional geography scope (e.g. 'EMEA', 'AMER', 'APAC').",
    )


@define_tool(
    name="delegated_authority_resolve_approver",
    description=(
        "Resolve who is authorised to approve a request using the delegated-authority "
        "matrix. Returns the matched rule's approver_role, threshold_gbp, escalation_chain, "
        "rule_id, and basis. Use this whenever your skill is producing a routing decision "
        "or a HITL gate's approver — surface the result as `resolved_approver` in your "
        "structured output so downstream personae receive an authoritative threshold."
    ),
)
def delegated_authority_resolve_approver_tool(params: _ResolveApproverParams) -> ToolResult:
    try:
        resolution = resolve_approver(
            action=params.action,
            value=params.value,
            category=params.category,
            requester_role=params.requester_role,
            business_unit=params.business_unit,
            geography=params.geography,
        )
    except httpx.HTTPError as ex:
        return ToolResult(
            text_result_for_llm=(
                f"authority MCP unreachable at {_base_url()}: {ex}. "
                "Skill should surface this as an exception rather than guessing a threshold."
            ),
            result_type="failure",
            error=str(ex),
        )
    return ToolResult(text_result_for_llm=resolution.model_dump_json())


class _CheckAuthorityParams(BaseModel):
    role: str = Field(description="Persona role to check (e.g. 'finance_bp', 'line_manager').")
    action: str = Field(description="What is being approved (see resolve_approver for the list).")
    value: float | None = Field(default=None, description="Monetary value in GBP, if applicable.")
    category: str | None = Field(default=None, description="Sub-classification of the action.")
    business_unit: str | None = Field(default=None, description="Optional business unit scope.")
    geography: str | None = Field(default=None, description="Optional geography scope.")
    requester_role: str | None = Field(default=None, description="Optional requester role.")


@define_tool(
    name="delegated_authority_check_authority",
    description=(
        "Check whether the named role is authorised to approve a given request. Returns "
        "{allowed, reason, governing_rule_id}. Use this in persona decision_policy blocks "
        "when the persona needs to confirm it has authority before signing off, or in "
        "skills that need a yes/no rather than the full routing decision."
    ),
)
def delegated_authority_check_authority_tool(params: _CheckAuthorityParams) -> ToolResult:
    try:
        check = check_authority(
            role=params.role,
            action=params.action,
            value=params.value,
            category=params.category,
            business_unit=params.business_unit,
            geography=params.geography,
            requester_role=params.requester_role,
        )
    except httpx.HTTPError as ex:
        return ToolResult(
            text_result_for_llm=(
                f"authority MCP unreachable at {_base_url()}: {ex}. "
                "Caller should escalate rather than guess."
            ),
            result_type="failure",
            error=str(ex),
        )
    return ToolResult(text_result_for_llm=check.model_dump_json())


__all__ = [
    "ApproverResolution",
    "AuthorityCheck",
    "resolve_approver",
    "check_authority",
    "delegated_authority_resolve_approver_tool",
    "delegated_authority_check_authority_tool",
]

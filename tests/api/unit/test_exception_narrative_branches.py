"""Coverage tests for exception_narrative._describe_subject + helpers.

The module under test composes the human-readable exception card. The existing
`tests/api/unit/test_exception_narrative.py` covers only the legacy invoice
path — this file covers:

- `_humanize_action` namespace stripping + acronym preservation
- `_agent_tried` for each special-cased action shape
- `_describe_subject` for every payload-shaped fleet/composed domain
- the legacy invoice fallback when `workflow.invoice` is None
- the `category` switch in `compose` (the third "else" branch)
"""
from __future__ import annotations

import time

from api.shared.types import (
    ActionLedgerEntry,
    Exception_ as Exception,
    InvoiceData,
    Vendor,
    Workflow,
)
from api.server.services.exception_narrative import (
    _agent_tried,
    _describe_subject,
    _humanize_action,
    compose,
)


def _wf(**fields) -> Workflow:
    base = dict(
        id="WF-1",
        created_at=time.time(),
        sla_due_at=time.time() + 3600,
        jurisdiction="UK",
        agency="Zava-UK",
        current_phase="Intake",
    )
    base.update(fields)
    return Workflow(**base)


def _exc(category: str = "validator-blocked", *, recommendation: str = "Review") -> Exception:
    return Exception(
        id="EXC-1",
        workflow_id="WF-1",
        composed_by="deterministic",
        severity="high",
        category=category,
        summary="Test exception summary",
        recommendation=recommendation,
        confidence=1.0,
        created_at=time.time(),
    )


# ---------------------------------------------------------------------------
# _humanize_action
# ---------------------------------------------------------------------------


class TestHumanizeAction:
    def test_strips_workflow_namespace(self):
        assert _humanize_action("workflow.started") == "Started"

    def test_strips_durable_namespace(self):
        assert _humanize_action("durable.step.started") == "Step Started"

    def test_replaces_underscores_and_dots(self):
        assert _humanize_action("agent.tool_called") == "Tool Called"

    def test_preserves_all_caps_acronyms(self):
        # KYC and DPIA should stay upper-case, regular words capitalised.
        out = _humanize_action("agent.KYC.review_done")
        assert "KYC" in out
        assert "Review" in out

    def test_handles_colon_separator(self):
        # `phase.completed:Intake` is special-cased in _agent_tried, but the
        # generic path also has to render colon-separated forms gracefully.
        out = _humanize_action("queued:high_priority")
        assert ":" in out  # `:` is preserved with a space


# ---------------------------------------------------------------------------
# _agent_tried
# ---------------------------------------------------------------------------


def _ledger_entry(action: str, *, actor_id: str = "agent:test", details: dict | None = None,
                  actor_kind: str = "agent") -> ActionLedgerEntry:
    return ActionLedgerEntry(
        workflow_id="WF-1",
        timestamp=time.time(),
        actor_kind=actor_kind,  # type: ignore[arg-type]
        actor_id=actor_id,
        action=action,
        revocable=False,
        details=details or {},
    )


class TestAgentTried:
    def test_empty_ledger_returns_orchestration_started_message(self):
        out = _agent_tried([])
        assert out == ["Orchestration started; no executor actions recorded yet."]

    def test_filters_out_human_actions(self):
        ledger = [
            _ledger_entry("workflow.started"),
            _ledger_entry("approved", actor_kind="human"),
        ]
        # Only the agent action is rendered; "approved" by human is dropped.
        out = _agent_tried(ledger)
        assert out == ["Workflow started"]

    def test_renders_phase_started_and_completed(self):
        ledger = [
            _ledger_entry("phase.started:Intake"),
            _ledger_entry("phase.completed:Intake"),
        ]
        assert _agent_tried(ledger) == [
            "Intake phase started",
            "Intake phase completed",
        ]

    def test_renders_validator_blocked_with_reason_and_who(self):
        ledger = [
            _ledger_entry(
                "validator.blocked",
                actor_id="validator:gl_active",
                details={"reason": "GL-9999 not active"},
            )
        ]
        out = _agent_tried(ledger)
        assert out == ["gl_active rejected: GL-9999 not active"]

    def test_renders_validator_blocked_with_default_reason_when_missing(self):
        ledger = [_ledger_entry("validator.blocked", actor_id="validator:x", details={})]
        assert _agent_tried(ledger) == ["x rejected: validation failed"]

    def test_renders_suspended_and_resumed(self):
        ledger = [
            _ledger_entry("suspended", details={"reason": "out-of-envelope"}),
            _ledger_entry("resumed"),
        ]
        out = _agent_tried(ledger)
        assert out[0] == "Workflow suspended for review: out-of-envelope"
        assert out[1] == "Workflow resumed after review"

    def test_renders_workflow_started_and_completed(self):
        ledger = [
            _ledger_entry("workflow.started"),
            _ledger_entry("workflow.completed"),
        ]
        assert _agent_tried(ledger) == ["Workflow started", "Workflow completed"]

    def test_falls_back_to_humanize_for_unknown_actions(self):
        ledger = [_ledger_entry("agent.tool_called")]
        assert _agent_tried(ledger) == ["Tool Called"]

    def test_keeps_only_last_n(self):
        ledger = [_ledger_entry(f"phase.started:Phase{i}") for i in range(10)]
        out = _agent_tried(ledger, limit=3)
        assert len(out) == 3
        # Last 3 should be Phase7..Phase9.
        assert out[-1] == "Phase9 phase started"
        assert out[0] == "Phase7 phase started"


# ---------------------------------------------------------------------------
# _describe_subject — per-domain branches
# ---------------------------------------------------------------------------


class TestDescribeSubjectPayloadDomains:
    def test_vendor_kyc(self):
        w = _wf(
            type="vendor-kyc",
            payload={"vendor": {"name": "Acme Ltd", "country_of_incorporation": "GB"}},
        )
        subject, amount = _describe_subject(w)
        assert "Acme Ltd" in subject and "GB" in subject and "Vendor KYC" in subject
        assert amount == ""

    def test_travel_preapproval(self):
        w = _wf(
            type="travel-preapproval",
            payload={"trip": {"employee_id": "EMP-1", "origin": "LHR", "destination": "JFK"}},
        )
        subject, amount = _describe_subject(w)
        assert "EMP-1" in subject and "LHR" in subject and "JFK" in subject
        assert amount == ""

    def test_employee_onboarding(self):
        w = _wf(
            type="employee-onboarding",
            payload={"joiner": {"employee_id": "NEW-7", "department": "Engineering"}},
        )
        subject, amount = _describe_subject(w)
        assert "NEW-7" in subject and "Engineering" in subject
        assert amount == ""

    def test_it_access_request(self):
        w = _wf(
            type="it-access-request",
            payload={
                "request": {
                    "employee_id": "EMP-2",
                    "requested_role_templates": ["t1", "t2", "t3"],
                }
            },
        )
        subject, amount = _describe_subject(w)
        assert "EMP-2" in subject and "3 role templates" in subject

    def test_contract_renewal(self):
        w = _wf(
            type="contract-renewal",
            payload={"contract": {"contract_id": "CON-99", "vendor_name": "Northwind"}},
        )
        subject, _ = _describe_subject(w)
        assert "CON-99" in subject and "Northwind" in subject

    def test_perf_review(self):
        w = _wf(
            type="perf-review",
            payload={"review": {"employee_id": "EMP-3", "cycle": "FY26-H1"}},
        )
        subject, _ = _describe_subject(w)
        assert "EMP-3" in subject and "FY26-H1" in subject

    def test_ap_invoice_with_amount(self):
        w = _wf(
            type="ap-invoice",
            payload={
                "invoice": {
                    "invoice_id": "INV-77",
                    "vendor_name": "Helios",
                    "amount_gbp": 1234.5,
                    "currency": "GBP",
                }
            },
        )
        subject, amount = _describe_subject(w)
        assert "INV-77" in subject and "Helios" in subject
        assert "1,234.50" in amount and "GBP" in amount

    def test_purchase_order_with_amount(self):
        w = _wf(
            type="purchase-order",
            payload={
                "purchase_order": {
                    "po_id": "PO-1",
                    "vendor_name": "Polaris",
                    "amount_gbp": 999.0,
                }
            },
        )
        subject, amount = _describe_subject(w)
        assert "PO-1" in subject and "Polaris" in subject
        assert "999.00" in amount

    def test_contract_review_uppercases_contract_type(self):
        w = _wf(
            type="contract-review",
            payload={
                "contract_review": {
                    "contract_type": "msa",
                    "contract_id": "CR-1",
                    "vendor_name": "Atlas",
                    "amount_gbp": 50_000.0,
                }
            },
        )
        subject, amount = _describe_subject(w)
        assert subject.startswith("MSA ")  # contract_type uppercased
        assert "CR-1" in subject and "Atlas" in subject
        assert "50,000.00" in amount

    def test_privacy_dpia(self):
        w = _wf(
            type="privacy-dpia",
            payload={
                "dpia": {
                    "dpia_id": "DPIA-5",
                    "system_name": "AnalyticsPlatform",
                    "risk_tier": "high",
                    "geography": "EU",
                }
            },
        )
        subject, _ = _describe_subject(w)
        assert "DPIA-5" in subject and "AnalyticsPlatform" in subject
        assert "high" in subject and "EU" in subject

    def test_treasury_fx_with_notional(self):
        w = _wf(
            type="treasury-fx",
            payload={
                "treasury_op": {
                    "op_kind": "spot",
                    "op_id": "FX-9",
                    "currency_pair": "GBPUSD",
                    "notional_gbp": 250_000.0,
                }
            },
        )
        subject, amount = _describe_subject(w)
        assert "FX spot FX-9" in subject and "GBPUSD" in subject
        assert "250,000.00" in amount


class TestDescribeSubjectLegacyAndDefault:
    def test_legacy_invoice_with_vendor(self):
        w = _wf(
            type="invoice-p2p",  # legacy alias still allowed
            vendor=Vendor(id="V-1", name="Wayne Enterprises", country="US"),
            invoice=InvoiceData(number="INV-9", amount=1000.0, currency="USD",
                                po_ref="PO-1"),
        )
        subject, amount = _describe_subject(w)
        assert "Wayne Enterprises" in subject and "INV-9" in subject
        assert amount == "USD 1,000.00"

    def test_legacy_default_when_invoice_missing(self):
        # No invoice, no payload — falls into the final default branch.
        w = _wf(
            type="invoice-p2p",
            vendor=Vendor(id="V-2", name="Acme", country="GB"),
        )
        subject, amount = _describe_subject(w)
        assert "Workflow" in subject and "Acme" in subject
        assert amount == ""

    def test_legacy_default_with_unknown_vendor(self):
        w = _wf(type="invoice-p2p")
        subject, _ = _describe_subject(w)
        assert "<unknown vendor>" in subject

    def test_hiring_workflow_returns_id_only(self):
        w = _wf(id="HIRE-42", type="hiring")
        subject, amount = _describe_subject(w)
        assert subject == "Hiring workflow HIRE-42"
        assert amount == ""


# ---------------------------------------------------------------------------
# compose — third-category fallback
# ---------------------------------------------------------------------------


def test_compose_other_category_uses_generic_phrasing():
    w = _wf(
        type="vendor-kyc",
        payload={"vendor": {"name": "Acme Ltd", "country_of_incorporation": "GB"}},
        current_phase="Triage",
    )
    exc = _exc(category="compliance")  # neither validator-blocked nor threshold
    out = compose(w, exc, ledger=[])
    assert "exception raised at Triage" in out["whatHappened"]
    assert "Acme Ltd" in out["whatHappened"]
    # Default "agent tried" string when ledger is empty.
    assert out["whatAgentTried"] == [
        "Orchestration started; no executor actions recorded yet."
    ]
    assert out["agentRecommendation"] == "Review"


def test_compose_uses_default_recommendation_when_none():
    w = _wf(
        type="ap-invoice",
        payload={
            "invoice": {
                "invoice_id": "INV-1",
                "vendor_name": "Acme",
                "amount_gbp": 100.0,
            }
        },
    )
    exc = _exc(category="threshold-exceeded", recommendation="")
    out = compose(w, exc, ledger=[])
    assert "requires human approval" in out["whatHappened"]
    assert out["agentRecommendation"].startswith(
        "Review exception and select an Intervention Protocol"
    )

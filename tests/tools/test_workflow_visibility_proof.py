from __future__ import annotations

import copy
import json
from pathlib import Path
from types import SimpleNamespace
from urllib.error import URLError

import pytest

from api.shared.domain_contracts import Domain, HitlGate, Phase, RegionOverlay
from api.shared.vertical_loader import build_runtime
from tools.workflow_visibility_proof import (
    ProofError,
    VisibilityContract,
    WorkflowSnapshot,
    contracts_for_pack,
    fetch_url_details,
    load_snapshot,
    read_url_json,
    save_snapshot,
    verify_details,
    verify_live_and_replay,
)


def _domain(
    workflow_type: str,
    *phases: Phase,
    hitl_gates: tuple[HitlGate, ...] = (),
    stub: bool = False,
    region_overlays: dict[str, RegionOverlay] | None = None,
) -> Domain:
    return Domain(
        workflow_type=workflow_type,
        display_name=workflow_type,
        workflow_id_prefix=workflow_type.upper(),
        orchestrator_name=f"{workflow_type.title()}Orchestrator",
        operator_surface="proof",
        phases=phases,
        hitl_gates=hitl_gates,
        skills=(),
        stub=stub,
        region_overlays=region_overlays or {},
    )


def _contract(
    domain: Domain,
    *persona_roles: str,
) -> VisibilityContract:
    return VisibilityContract(
        domain=domain,
        persona_roles=frozenset(persona_roles),
    )


def _reasoning(
    phase: str | None,
    *,
    covered_phases: list[str] | None = None,
    run_id: str = "ar-1234567890abcdef1234567890abcdef",
) -> dict:
    return {
        "id": f"reasoning:{run_id}",
        "kind": "reasoning",
        "label": "analyst",
        "status": "completed",
        "agent": "analyst",
        "agentRunId": run_id,
        "phase": phase,
        "coveredPhases": covered_phases,
        "model": "test-model",
        "messages": [],
        "toolCalls": [],
        "extractedJson": {"verdict": "clear"},
        "latencyMs": 10,
        "tokensIn": 1,
        "tokensOut": 1,
        "startedAt": 1.0,
        "completedAt": 1.01,
    }


def _detail(
    domain: Domain,
    workflow_id: str,
    *,
    status: str = "completed",
    phase_rows: list[tuple[str, str]] | None = None,
    reasoning_rows: list[dict] | None = None,
    extra_rows: list[dict] | None = None,
) -> dict:
    if phase_rows is None:
        phase_rows = [(phase.name, "completed") for phase in domain.phases]
    if reasoning_rows is None:
        agent_phase = next(
            (phase.name for phase in domain.phases if phase.kind == "agent"),
            None,
        )
        reasoning_rows = [_reasoning(agent_phase)] if agent_phase else []
    terminal_label = f"workflow.{status}"
    return {
        "workflow": {
            "id": workflow_id,
            "type": domain.workflow_type,
            "status": status,
            "jurisdiction": "UK",
        },
        "timeline": [
            {
                "id": f"workflow:{workflow_id}",
                "kind": "workflow",
                "label": "workflow.started",
                "status": "completed",
            },
            *[
                {
                    "id": f"phase:{index}:{name}",
                    "kind": "phase",
                    "label": name,
                    "status": phase_status,
                }
                for index, (name, phase_status) in enumerate(phase_rows)
            ],
            *reasoning_rows,
            *(extra_rows or []),
            {
                "id": f"terminal:{workflow_id}",
                "kind": "ledger",
                "label": terminal_label,
                "status": status,
            },
        ],
        "mcpCalls": [],
    }


def _add_tool_call(detail: dict, call_id: str = "call-1") -> None:
    reasoning = next(row for row in detail["timeline"] if row["kind"] == "reasoning")
    reasoning["toolCalls"].append({
        "toolCallId": call_id,
        "name": "lookup",
        "args": {"id": "1"},
        "result": {"ok": True},
        "success": True,
        "latencyMs": 4,
    })
    detail["mcpCalls"].append({
        "toolCallId": call_id,
        "tool": "lookup",
        "request": {"id": "1"},
        "response": {"ok": True},
        "statusCode": 200,
        "durationMs": 4,
        "timestamp": 1.0,
    })
    detail["timeline"].insert(-1, {
        "id": call_id,
        "toolCallId": call_id,
        "kind": "tool",
        "label": "lookup",
        "tool": "lookup",
        "status": "ok",
        "statusCode": 200,
        "durationMs": 4,
    })


def _snapshot(mode: str, details: list[dict]) -> WorkflowSnapshot:
    return WorkflowSnapshot(mode, tuple(details))


def test_every_active_type_requires_an_inspected_instance() -> None:
    first = _domain("first", Phase("Run", "deterministic"))
    second = _domain("second", Phase("Run", "deterministic"))

    with pytest.raises(ProofError, match="missing required workflow types: second"):
        verify_details(
            [_detail(first, "FIRST-1")],
            {"first": _contract(first), "second": _contract(second)},
            source="live",
        )


def test_empty_active_contract_set_cannot_pass_vacuously() -> None:
    with pytest.raises(ProofError, match="no required workflow contracts"):
        verify_details([], {}, source="live")


def test_active_pack_contracts_exclude_exact_stubs() -> None:
    expected_counts = {"agency": 15, "fashion": 8, "telco": 37}
    for vertical, count in expected_counts.items():
        pack = build_runtime({"ZAVA_VERTICAL": vertical}).pack
        assert len(contracts_for_pack(pack)) == count

    agency = contracts_for_pack(
        build_runtime({"ZAVA_VERTICAL": "agency"}).pack
    )
    assert "hiring" in agency
    assert "creative-campaign" not in agency
    assert {
        "hire-to-productive",
        "vendor-risk-to-pay",
        "lead-to-cash",
        "fy-close",
        "board-prep",
        "media-pitch-to-win",
        "account-onboarding",
        "intercompany-recharge",
        "talent-redeployment",
        "agency-network-roll-up",
        "m-and-a-integration",
        "crisis-response",
        "creative-awards-submission",
        "client-renewal",
        "freelancer-onboarding",
        "data-clean-room-setup",
        "weekly-pitch-review",
        "monthly-client-pnl",
        "quarterly-creative-awards",
        "annual-budget-setting",
        "new-business-pipeline-scrub",
        "intercompany-talent-transfer",
        "policy_set",
    }.isdisjoint(agency)


def test_pack_contract_resolves_dynamic_personas_from_personae_and_authority() -> None:
    domain = _domain("flow", Phase("review", "hitl"))
    pack = SimpleNamespace(
        domains={"flow": domain},
        personas={"reviewer": SimpleNamespace(role="reviewer")},
        authority={"delegate": SimpleNamespace(role="delegate")},
    )

    assert contracts_for_pack(pack)["flow"].persona_roles == {
        "reviewer",
        "delegate",
    }


def test_timeline_must_be_nonempty() -> None:
    domain = _domain("flow", Phase("Run", "deterministic"))
    detail = _detail(domain, "FLOW-EMPTY")
    detail["timeline"] = []

    with pytest.raises(ProofError, match="timeline is empty"):
        verify_details([detail], {"flow": _contract(domain)}, source="live")


@pytest.mark.parametrize("started_count", [0, 2])
def test_timeline_has_exactly_one_workflow_started(started_count: int) -> None:
    domain = _domain("flow", Phase("Run", "deterministic"))
    detail = _detail(domain, "FLOW-START")
    detail["timeline"] = [
        row for row in detail["timeline"] if row["label"] != "workflow.started"
    ]
    for index in range(started_count):
        detail["timeline"].insert(index, {
            "id": f"start:{index}",
            "kind": "workflow",
            "label": "workflow.started",
        })

    with pytest.raises(ProofError, match=rf"expected 1 workflow.started.*found {started_count}"):
        verify_details([detail], {"flow": _contract(domain)}, source="live")


@pytest.mark.parametrize("status", ["completed", "failed", "rejected"])
def test_terminal_lifecycle_matches_exact_final_status(status: str) -> None:
    domain = _domain("flow", Phase("Run", "deterministic"))
    detail = _detail(domain, f"FLOW-{status}", status=status)

    assert verify_details(
        [detail],
        {"flow": _contract(domain)},
        source="live",
    )


def test_endpoint_detail_accepts_failed_status_with_rejected_terminal() -> None:
    domain = _domain("flow", Phase("Run", "deterministic"))
    detail = _detail(domain, "FLOW-FAILED", status="failed")
    detail["timeline"][-1] = {
        "id": "ledger:rejection",
        "kind": "ledger",
        "label": "workflow.rejected",
        "status": None,
        "actor": "manager",
        "details": {"reason": "evidence missing"},
    }

    assert verify_details(
        [detail],
        {"flow": _contract(domain)},
        source="live",
    )


def test_terminal_lifecycle_is_unique() -> None:
    domain = _domain("flow", Phase("Run", "deterministic"))
    detail = _detail(domain, "FLOW-END")
    detail["timeline"].append({
        "id": "terminal:duplicate",
        "kind": "ledger",
        "label": "workflow.failed",
    })

    with pytest.raises(ProofError, match="expected 1 terminal lifecycle row, found 2"):
        verify_details([detail], {"flow": _contract(domain)}, source="live")


def test_observed_conditional_phase_subset_is_valid() -> None:
    domain = _domain(
        "conditional",
        Phase("Intake", "deterministic"),
        Phase("Optional Review", "agent"),
        Phase("Fulfil", "deterministic"),
    )
    detail = _detail(
        domain,
        "COND-1",
        phase_rows=[("Intake", "completed"), ("Fulfil", "completed")],
    )

    assert verify_details(
        [detail],
        {"conditional": _contract(domain)},
        source="live",
    )


def test_observed_phase_rows_must_be_nonempty() -> None:
    domain = _domain("flow", Phase("Run", "deterministic"))
    detail = _detail(domain, "FLOW-NO-PHASES", phase_rows=[])

    with pytest.raises(ProofError, match="phase rows are empty"):
        verify_details([detail], {"flow": _contract(domain)}, source="live")


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("label", "Invented"),
        ("phase", "Invented"),
        ("coveredPhases", ["Invented"]),
    ],
)
def test_every_observed_phase_reference_must_be_declared(
    field: str,
    value,
) -> None:
    domain = _domain("flow", Phase("Run", "deterministic"))
    detail = _detail(domain, "FLOW-BAD-PHASE")
    row = next(row for row in detail["timeline"] if row["kind"] == "phase")
    row[field] = value

    with pytest.raises(ProofError, match="undeclared phase"):
        verify_details([detail], {"flow": _contract(domain)}, source="live")


def test_region_overlay_phase_is_part_of_declared_domain_set() -> None:
    domain = _domain(
        "regional",
        Phase("Run", "deterministic"),
        region_overlays={
            "DE": RegionOverlay(
                extra_phases=(Phase("BaFin Filing", "deterministic"),),
            )
        },
    )
    detail = _detail(
        domain,
        "REGIONAL-DE",
        phase_rows=[("BaFin Filing", "completed")],
    )

    assert verify_details(
        [detail],
        {"regional": _contract(domain)},
        source="live",
    )


@pytest.mark.parametrize("phase_status", ["completed", "failed", "rejected", "skipped"])
def test_observed_phase_rows_accept_terminal_or_skipped_status(
    phase_status: str,
) -> None:
    domain = _domain("flow", Phase("Run", "deterministic"))
    detail = _detail(
        domain,
        f"FLOW-{phase_status}",
        phase_rows=[("Run", phase_status)],
    )

    assert verify_details(
        [detail],
        {"flow": _contract(domain)},
        source="live",
    )


def test_observed_phase_row_rejects_nonterminal_status() -> None:
    domain = _domain("flow", Phase("Run", "deterministic"))
    detail = _detail(
        domain,
        "FLOW-PENDING",
        phase_rows=[("Run", "in_progress")],
    )

    with pytest.raises(ProofError, match="phase 'Run'.*not terminal or skipped"):
        verify_details([detail], {"flow": _contract(domain)}, source="live")


def test_executable_domain_requires_one_canonical_reasoning_row_total() -> None:
    domain = _domain("agent-flow", Phase("Analyse", "agent"))
    detail = _detail(domain, "AGENT-NONE", reasoning_rows=[])

    with pytest.raises(ProofError, match="requires at least 1 canonical reasoning row"):
        verify_details(
            [detail],
            {"agent-flow": _contract(domain)},
            source="live",
        )


def test_one_reasoning_row_is_enough_for_multi_agent_domain() -> None:
    domain = _domain(
        "agent-flow",
        Phase("Discover", "agent"),
        Phase("Assess", "agent"),
    )
    detail = _detail(
        domain,
        "AGENT-ONE",
        reasoning_rows=[_reasoning("Discover")],
    )

    assert verify_details(
        [detail],
        {"agent-flow": _contract(domain)},
        source="live",
    )


def test_reasoning_may_run_inside_deterministic_or_hitl_business_phase() -> None:
    domain = _domain(
        "mixed-flow",
        Phase("Prepare", "deterministic"),
        Phase("Review", "hitl"),
        Phase("Execute", "agent"),
    )
    detail = _detail(
        domain,
        "MIXED-1",
        reasoning_rows=[
            _reasoning("Prepare"),
            _reasoning("Review", run_id="ar-fedcba0987654321fedcba0987654321"),
        ],
    )

    assert verify_details(
        [detail],
        {"mixed-flow": _contract(domain)},
        source="live",
    )


@pytest.mark.parametrize("missing_field", ["agentRunId", "completedAt"])
def test_reasoning_requires_stable_run_id_and_completion(
    missing_field: str,
) -> None:
    domain = _domain("agent-flow", Phase("Analyse", "agent"))
    reasoning = _reasoning("Analyse")
    reasoning.pop(missing_field)
    detail = _detail(domain, "AGENT-INCOMPLETE", reasoning_rows=[reasoning])

    with pytest.raises(ProofError, match=missing_field):
        verify_details(
            [detail],
            {"agent-flow": _contract(domain)},
            source="live",
        )


def test_reasoning_requires_declared_phase_or_covered_phases() -> None:
    domain = _domain("agent-flow", Phase("Analyse", "agent"))
    detail = _detail(
        domain,
        "AGENT-NO-PHASE",
        reasoning_rows=[_reasoning(None, covered_phases=[])],
    )

    with pytest.raises(ProofError, match="declared phase or coveredPhases"):
        verify_details(
            [detail],
            {"agent-flow": _contract(domain)},
            source="live",
        )


def test_declared_allowed_tools_do_not_require_an_actual_call() -> None:
    domain = _domain("agent-flow", Phase("Analyse", "agent"))
    pack = SimpleNamespace(
        domains={"agent-flow": domain},
        personas={},
        authority={},
        agents={"analyst": SimpleNamespace(allowed_tools=("lookup",))},
        skill_roots=(),
    )

    assert verify_details(
        [_detail(domain, "AGENT-NO-TOOL")],
        contracts_for_pack(pack),
        source="live",
    )


def test_actual_tool_call_is_exactly_correlated_across_all_views() -> None:
    domain = _domain("agent-flow", Phase("Analyse", "agent"))
    detail = _detail(domain, "TOOL-1")
    _add_tool_call(detail)

    assert verify_details(
        [detail],
        {"agent-flow": _contract(domain)},
        source="live",
    )


@pytest.mark.parametrize("missing_view", ["reasoning", "mcp", "timeline"])
def test_partial_tool_call_evidence_is_rejected(missing_view: str) -> None:
    domain = _domain("agent-flow", Phase("Analyse", "agent"))
    detail = _detail(domain, "TOOL-PARTIAL")
    _add_tool_call(detail)
    if missing_view == "reasoning":
        next(
            row for row in detail["timeline"] if row["kind"] == "reasoning"
        )["toolCalls"] = []
    elif missing_view == "mcp":
        detail["mcpCalls"] = []
    else:
        detail["timeline"] = [
            row for row in detail["timeline"] if row["kind"] != "tool"
        ]

    with pytest.raises(ProofError, match="tool call ids differ"):
        verify_details(
            [detail],
            {"agent-flow": _contract(domain)},
            source="live",
        )


@pytest.mark.parametrize(
    ("view", "field", "value"),
    [
        ("reasoning", "args", {"id": "other"}),
        ("reasoning", "result", {"ok": False}),
        ("reasoning", "success", False),
        ("reasoning", "latencyMs", 99),
        ("timeline", "statusCode", 503),
        ("timeline", "durationMs", 99),
    ],
)
def test_tool_payload_status_and_duration_must_match(
    view: str,
    field: str,
    value,
) -> None:
    domain = _domain("agent-flow", Phase("Analyse", "agent"))
    detail = _detail(domain, "TOOL-MISMATCH")
    _add_tool_call(detail)
    if view == "reasoning":
        tool = next(
            row for row in detail["timeline"] if row["kind"] == "reasoning"
        )["toolCalls"][0]
    else:
        tool = next(row for row in detail["timeline"] if row["kind"] == "tool")
    tool[field] = value

    with pytest.raises(ProofError, match="tool call 'call-1'.*does not match"):
        verify_details(
            [detail],
            {"agent-flow": _contract(domain)},
            source="live",
        )


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("arguments", {"id": "other"}),
        ("response", {"ok": False}),
        ("latency_ms", 999),
    ],
)
def test_snake_case_reasoning_tool_fields_must_match_canonical_call(
    field: str,
    value,
) -> None:
    domain = _domain("agent-flow", Phase("Analyse", "agent"))
    detail = _detail(domain, "TOOL-SNAKE-MISMATCH")
    _add_tool_call(detail)
    reasoning_call = next(
        row for row in detail["timeline"] if row["kind"] == "reasoning"
    )["toolCalls"][0]
    aliases = {
        "arguments": ("args", "arguments", "request"),
        "response": ("result", "response"),
        "latency_ms": (
            "latency_ms",
            "latencyMs",
            "duration_ms",
            "durationMs",
        ),
    }
    for alias in aliases[field]:
        reasoning_call.pop(alias, None)
    reasoning_call[field] = value

    with pytest.raises(ProofError, match="tool call 'call-1'.*does not match"):
        verify_details(
            [detail],
            {"agent-flow": _contract(domain)},
            source="live",
        )


def test_snake_case_failed_tool_evidence_correlates_with_empty_payloads() -> None:
    domain = _domain("agent-flow", Phase("Analyse", "agent"))
    detail = _detail(domain, "TOOL-SNAKE-PASS")
    reasoning = next(
        row for row in detail["timeline"] if row["kind"] == "reasoning"
    )
    reasoning["toolCalls"] = [{
        "tool_call_id": "call-snake",
        "name": "lookup",
        "arguments": {},
        "result": {},
        "status": "error",
        "latency_ms": 4,
    }]
    detail["mcpCalls"] = [{
        "tool_call_id": "call-snake",
        "tool": "lookup",
        "request": {},
        "response": {},
        "status_code": 503,
        "duration_ms": 4,
        "timestamp": 1.0,
    }]
    detail["timeline"].insert(-1, {
        "id": "call-snake",
        "tool_call_id": "call-snake",
        "kind": "tool",
        "label": "lookup",
        "tool": "lookup",
        "status": "error",
        "status_code": 503,
        "duration_ms": 4,
    })

    assert verify_details(
        [detail],
        {"agent-flow": _contract(domain)},
        source="live",
    )


def test_dynamic_hitl_approver_may_differ_from_static_gate_role() -> None:
    domain = _domain(
        "approval",
        Phase("signoff", "hitl"),
        hitl_gates=(HitlGate("signoff", "approval", "manager"),),
    )
    decision = {
        "id": "decision:1",
        "kind": "decision",
        "label": "signoff",
        "phase": "signoff",
        "personaRole": "delegate",
        "verdict": "approve",
        "reason": "Manager delegated this decision",
    }
    detail = _detail(domain, "APPROVAL-1", extra_rows=[decision])

    assert verify_details(
        [detail],
        {"approval": _contract(domain, "manager", "delegate")},
        source="live",
    )


@pytest.mark.parametrize("field", ["personaRole", "verdict", "reason"])
def test_hitl_decision_requires_persona_verdict_and_reason(field: str) -> None:
    domain = _domain("approval", Phase("signoff", "hitl"))
    decision = {
        "id": "decision:1",
        "kind": "decision",
        "label": "signoff",
        "phase": "signoff",
        "personaRole": "manager",
        "verdict": "approve",
        "reason": "Evidence is complete",
    }
    decision.pop(field)
    detail = _detail(domain, "APPROVAL-BAD", extra_rows=[decision])

    with pytest.raises(ProofError, match=field):
        verify_details(
            [detail],
            {"approval": _contract(domain, "manager")},
            source="live",
        )


def test_hitl_decision_persona_must_resolve_in_active_pack() -> None:
    domain = _domain("approval", Phase("signoff", "hitl"))
    decision = {
        "id": "decision:1",
        "kind": "decision",
        "label": "signoff",
        "phase": "signoff",
        "personaRole": "unknown",
        "verdict": "approve",
        "reason": "Evidence is complete",
    }
    detail = _detail(domain, "APPROVAL-UNKNOWN", extra_rows=[decision])

    with pytest.raises(ProofError, match="persona.*unknown.*active pack"):
        verify_details(
            [detail],
            {"approval": _contract(domain, "manager")},
            source="live",
        )


def test_declared_hitl_branch_without_a_decision_row_is_not_predicted() -> None:
    domain = _domain("approval", Phase("signoff", "hitl"))

    assert verify_details(
        [_detail(domain, "APPROVAL-NO-DECISION")],
        {"approval": _contract(domain, "manager")},
        source="live",
    )


def test_optional_evidence_is_not_required() -> None:
    domain = _domain("flow", Phase("Run", "deterministic"))

    assert verify_details(
        [_detail(domain, "FLOW-MINIMAL")],
        {"flow": _contract(domain)},
        source="live",
    )


@pytest.mark.parametrize(
    "row",
    [
        {
            "id": "lineage:1",
            "kind": "ledger",
            "label": "workflow.sub_spawned",
            "childWorkflowId": "CHILD-1",
        },
        {
            "id": "output:1",
            "kind": "output",
            "label": "workflow.output",
            "details": {},
        },
        {
            "id": "retry:1",
            "kind": "ledger",
            "label": "workflow.retry_scheduled",
            "details": {"attempt": 2},
        },
        {
            "id": "error:1",
            "kind": "ledger",
            "label": "workflow.exception.detected",
            "details": {},
        },
    ],
)
def test_optional_evidence_is_shape_checked_when_present(row: dict) -> None:
    domain = _domain("flow", Phase("Run", "deterministic"))
    detail = _detail(domain, "FLOW-BAD-OPTIONAL", extra_rows=[row])

    with pytest.raises(ProofError, match="missing|empty"):
        verify_details([detail], {"flow": _contract(domain)}, source="live")


def test_well_shaped_optional_evidence_is_valid() -> None:
    domain = _domain("flow", Phase("Run", "deterministic"))
    detail = _detail(
        domain,
        "FLOW-OPTIONAL",
        extra_rows=[
            {
                "id": "lineage:1",
                "kind": "ledger",
                "label": "workflow.sub_spawned",
                "phase": "Run",
                "childWorkflowId": "CHILD-1",
                "childWorkflowType": "child-flow",
            },
            {
                "id": "output:1",
                "kind": "output",
                "label": "workflow.output",
                "details": {"outcome": "recorded"},
            },
            {
                "id": "retry:1",
                "kind": "ledger",
                "label": "workflow.retry_scheduled",
                "details": {"attempt": 2, "error": "timeout"},
            },
            {
                "id": "error:1",
                "kind": "ledger",
                "label": "workflow.exception.detected",
                "details": {"reason": "upstream unavailable"},
            },
        ],
    )

    assert verify_details(
        [detail],
        {"flow": _contract(domain)},
        source="live",
    )


def test_live_and_replay_require_explicit_source_modes() -> None:
    domain = _domain("flow", Phase("Run", "deterministic"))
    details = [_detail(domain, "FLOW-1")]
    contract = {"flow": _contract(domain)}

    with pytest.raises(ProofError, match="live snapshot sourceMode must be 'live'"):
        verify_live_and_replay(
            _snapshot("replay", details),
            _snapshot("replay", details),
            contract,
        )
    with pytest.raises(ProofError, match="replay snapshot sourceMode must be 'replay'"):
        verify_live_and_replay(
            _snapshot("live", details),
            _snapshot("live", details),
            contract,
        )


def test_live_replay_compares_full_user_visible_evidence() -> None:
    domain = _domain("agent-flow", Phase("Analyse", "agent"))
    live = _detail(domain, "AGENT-1")
    _add_tool_call(live)
    replay = copy.deepcopy(live)
    replay["timeline"][1]["status"] = "skipped"

    with pytest.raises(ProofError, match="live/replay evidence differs"):
        verify_live_and_replay(
            _snapshot("live", [live]),
            _snapshot("replay", [replay]),
            {"agent-flow": _contract(domain)},
        )


def test_live_replay_ignores_only_declared_volatile_timing() -> None:
    domain = _domain("agent-flow", Phase("Analyse", "agent"))
    live = _detail(domain, "AGENT-1")
    _add_tool_call(live)
    replay = copy.deepcopy(live)
    replay["workflow"].update({
        "createdAt": 99,
        "updatedAt": 99,
        "startedAt": 99,
        "completedAt": 99,
    })
    live["workflow"].update({
        "createdAt": 1,
        "updatedAt": 1,
        "startedAt": 1,
        "completedAt": 1,
    })
    for row in replay["timeline"]:
        row["ts"] = 99
        row["timestamp"] = 99
        row["startedAt"] = 99
        row["completedAt"] = 99
        if row["kind"] != "tool":
            row["durationMs"] = 99
            row["latencyMs"] = 99
    replay["mcpCalls"][0]["timestamp"] = 99

    assert verify_live_and_replay(
        _snapshot("live", [live]),
        _snapshot("replay", [replay]),
        {"agent-flow": _contract(domain)},
    )


def test_live_replay_keeps_canonical_tool_duration_visible() -> None:
    domain = _domain("agent-flow", Phase("Analyse", "agent"))
    live = _detail(domain, "AGENT-1")
    _add_tool_call(live)
    replay = copy.deepcopy(live)
    replay["mcpCalls"][0]["durationMs"] = 9
    next(row for row in replay["timeline"] if row["kind"] == "tool")[
        "durationMs"
    ] = 9
    next(row for row in replay["timeline"] if row["kind"] == "reasoning")[
        "toolCalls"
    ][0]["latencyMs"] = 9

    with pytest.raises(ProofError, match="live/replay evidence differs"):
        verify_live_and_replay(
            _snapshot("live", [live]),
            _snapshot("replay", [replay]),
            {"agent-flow": _contract(domain)},
        )


def test_snapshot_round_trip_preserves_source_mode(tmp_path: Path) -> None:
    domain = _domain("flow", Phase("Run", "deterministic"))
    details = [_detail(domain, "FLOW-1")]
    live_dir = tmp_path / "live"
    replay_dir = tmp_path / "replay"
    save_snapshot(live_dir, "test", details, source_mode="live")
    save_snapshot(replay_dir, "test", details, source_mode="replay")

    live = load_snapshot(live_dir, "test")
    replay = load_snapshot(replay_dir, "test")

    assert live.source_mode == "live"
    assert replay.source_mode == "replay"
    assert verify_live_and_replay(
        live,
        replay,
        {"flow": _contract(domain)},
    )


def test_url_capture_reads_every_active_instance_and_source_mode() -> None:
    domain = _domain("flow", Phase("Run", "deterministic"))
    details = {
        "FLOW-1": _detail(domain, "FLOW-1"),
        "FLOW/2": _detail(domain, "FLOW/2"),
    }
    requested: list[str] = []

    def read_json(url: str):
        requested.append(url)
        if url.endswith("/api/replay/meta"):
            return {"mode": "live"}
        if url.endswith("/api/workflows"):
            return [
                {"id": workflow_id, "type": "flow"}
                for workflow_id in details
            ]
        workflow_id = url.rsplit("/", 1)[-1].replace("%2F", "/")
        return details[workflow_id]

    captured = fetch_url_details(
        "http://127.0.0.1:3101",
        {"flow": _contract(domain)},
        read_json=read_json,
    )

    assert captured.source_mode == "live"
    assert [detail["workflow"]["id"] for detail in captured] == [
        "FLOW-1",
        "FLOW/2",
    ]
    assert requested[-1].endswith("FLOW%2F2")


def test_url_reader_redacts_credentials_and_query(monkeypatch) -> None:
    secret_url = "https://example.test/api/workflows?token=secret"

    def unavailable(*_args, **_kwargs):
        raise URLError(secret_url)

    monkeypatch.setattr("urllib.request.urlopen", unavailable)

    with pytest.raises(ProofError) as raised:
        read_url_json(secret_url)

    message = str(raised.value)
    assert message == "GET https://example.test/api/workflows failed: connection error"


def test_saved_snapshot_requires_source_provenance(tmp_path: Path) -> None:
    (tmp_path / "workflow-details.json").write_text(
        json.dumps({
            "schemaVersion": 1,
            "vertical": "test",
            "details": [],
        }),
        encoding="utf-8",
    )

    with pytest.raises(ProofError, match="lacks required sourceMode provenance"):
        load_snapshot(tmp_path, "test")

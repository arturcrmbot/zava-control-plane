import json
import time
from fastapi.testclient import TestClient
from api.server.main import app
from api.server.state import app_state
from api.shared.types import (
    ActionLedgerEntry, Exception_ as Exception, InvoiceData, McpCall,
    OtelSpan, Phase, Vendor, Workflow,
)


def _seed(wid: str) -> None:
    app_state.store.upsert_workflow(Workflow(
        id=wid, created_at=time.time(), sla_due_at=time.time() + 3600,
        vendor=Vendor(id="V-1", name="Wayne Enterprises", country="US"),
        invoice=InvoiceData(number="INV-1", amount=12.0, currency="USD", po_ref="P"),
        jurisdiction="US", agency="Ogilvy-US",
    ))
    app_state.store.append_mcp_call(McpCall(
        workflow_id=wid, timestamp=time.time(),
        tool="getVendor", url="http://wd/mcp/call/getVendor",
        method="POST", request={"id": "V-1"}, response={},
        status_code=200, duration_ms=5,
    ))


def test_detail_response_includes_economics_and_mcpcalls() -> None:
    client = TestClient(app)
    _seed("W-DET-1")
    r = client.get("/api/workflows/W-DET-1")
    assert r.status_code == 200
    body = r.json()
    assert "economics" in body
    assert body["economics"]["toolCalls"] >= 1
    assert "mcpCalls" in body
    assert len(body["mcpCalls"]) >= 1
    assert body["mcpCalls"][0]["tool"] == "getVendor"


def test_detail_response_includes_narrative_when_exception_present() -> None:
    client = TestClient(app)
    wid = "W-DET-2"
    _seed(wid)
    exc = Exception(
        id="EXC-N", workflow_id=wid, composed_by="deterministic",
        severity="high", category="validator-blocked",
        summary="blocked test", recommendation="retry",
        confidence=1.0, created_at=time.time(),
    )
    app_state.store.upsert_exception(exc)
    r = client.get(f"/api/workflows/{wid}")
    assert r.status_code == 200
    body = r.json()
    assert "narrative" in body and body["narrative"] is not None
    assert "whatHappened" in body["narrative"]
    assert "whatAgentTried" in body["narrative"]


def test_detail_and_timeline_routes_return_complete_chronological_timeline() -> None:
    wid = "W-DET-TIMELINE"
    workflow = Workflow(
        id=wid,
        status="awaiting_hitl",
        current_phase="Approval",
        created_at=1_000.0,
        sla_due_at=2_000.0,
        jurisdiction="US",
        agency="Ogilvy-US",
        payload={
            "decisions": [{
                "id": "decision-1",
                "phase": "Approval",
                "persona_role": "finance-director",
                "verdict": "approve",
                "reason": "Evidence is complete",
                "decided_at": 1_018.0,
                "evidence": {"invoice": "INV-1"},
            }],
        },
        agent_outputs={
            "risk_reviewer": {
                "completed_at": 1_016.5,
                "verdict": "amber",
                "evidence": ["sanctions-clear"],
            },
        },
        agent_reasoning=[{
            "agent_run_id": "run-1",
            "agent_label": "risk_reviewer",
            "phase": "Validation",
            "model": "gpt-4.1",
            "started_at": 1_015.0,
            "completed_at": 1_016.0,
            "messages": [{"role": "assistant", "content": "Checked evidence"}],
            "tool_calls": [{"tool": "screenVendor", "result": {"clear": True}}],
            "extracted_json": {"verdict": "amber"},
            "latency_ms": 1_000,
            "tokens_in": 120,
            "tokens_out": 30,
        }],
        action_ledger=[
            ActionLedgerEntry(
                workflow_id=wid,
                timestamp=1_000.25,
                actor_kind="agent",
                actor_id="orchestrator",
                action="workflow.started",
                revocable=False,
                details={"source": "durable-event"},
                decision_id="start-1",
                policy_version="2026-07",
                enforcement_mode="enforce",
                prev_hash="previous",
                entry_hash="started",
                actor_jws="signed",
            ),
            ActionLedgerEntry(
                workflow_id=wid,
                timestamp=1_017.0,
                actor_kind="agent",
                actor_id="policy-agent",
                action="workflow.retry_scheduled",
                revocable=True,
                details={"attempt": 2, "error": "upstream timeout"},
                decision_id="gov-1",
                policy_version="2026-07",
                enforcement_mode="enforce",
            ),
            ActionLedgerEntry(
                workflow_id=wid,
                timestamp=1_019.0,
                actor_kind="agent",
                actor_id="fleet-manager",
                action="workflow.sub_spawned",
                revocable=False,
                details={
                    "child_workflow_id": "W-CHILD-1",
                    "child_workflow_type": "vendor-kyc",
                },
            ),
        ],
    )
    app_state.store.upsert_workflow(workflow)
    app_state.store.append_phase(wid, Phase(
        workflow_id=wid,
        name="Validation",
        status="completed",
        started_at=1_010.0,
        completed_at=1_020.0,
        agent_id="deterministic-validator",
        span_ids=["span-1"],
    ))
    app_state.store.append_span(OtelSpan(
        trace_id="trace-1",
        span_id="span-1",
        name="agent.vendor-risk",
        start_ms=1_012_000.0,
        end_ms=1_013_500.0,
        status="ok",
        attributes={
            "workflow.id": wid,
            "agent.name": "risk-reviewer",
            "skill.name": "vendor-risk",
            "gen_ai.request.model": "gpt-4.1",
            "gen_ai.usage.input_tokens": 120,
            "gen_ai.usage.output_tokens": 30,
            "gen_ai.usage.cost_usd": 0.0042,
            "safe.details": {"source": "vendor-master"},
        },
    ))
    app_state.store.append_mcp_call(McpCall(
        workflow_id=wid,
        timestamp=1_014.0,
        tool="screenVendor",
        url="https://mcp.example.test/screen",
        method="POST",
        request={"vendorId": "V-1", "checks": ["sanctions"]},
        response={"clear": True, "matches": []},
        status_code=200,
        duration_ms=25,
    ))

    client = TestClient(app)
    detail = client.get(f"/api/workflows/{wid}")
    timeline_response = client.get(f"/api/workflows/index/timeline/{wid}")

    assert detail.status_code == 200
    assert timeline_response.status_code == 200
    detail_payload = detail.json()
    timeline_payload = timeline_response.json()
    detail_rows = detail_payload["timeline"]
    timeline_rows = timeline_payload["timeline"]
    assert detail_rows == timeline_rows
    assert timeline_payload["mcpCalls"] == detail_payload["mcpCalls"]
    assert [row["ts"] for row in detail_rows] == sorted(row["ts"] for row in detail_rows)
    assert all({"id", "ts", "kind", "label"} <= row.keys() for row in detail_rows)

    lifecycle_rows = [row for row in detail_rows if row["label"] == "workflow.started"]
    assert len(lifecycle_rows) == 1
    lifecycle = lifecycle_rows[0]
    assert lifecycle == {
        "id": f"workflow:{wid}",
        "ts": 1_000.0,
        "kind": "workflow",
        "label": "workflow.started",
        "status": "started",
        "currentPhase": "Approval",
        "startedAt": 1_000.0,
        "actor": "orchestrator",
        "actorKind": "agent",
        "revocable": False,
        "details": {"source": "durable-event"},
        "timestamp": 1_000.25,
        "decisionId": "start-1",
        "policyVersion": "2026-07",
        "enforcementMode": "enforce",
        "prevHash": "previous",
        "entryHash": "started",
        "actorJws": "signed",
    }

    phase = next(row for row in detail_rows if row["kind"] == "phase")
    assert phase["startedAt"] == 1_010.0
    assert phase["completedAt"] == 1_020.0
    assert phase["durationMs"] == 10_000.0
    assert phase["agentId"] == "deterministic-validator"
    assert phase["spanIds"] == ["span-1"]
    legacy_agent_output = next(
        row for row in detail_rows if row["kind"] == "agentOutput"
    )
    assert legacy_agent_output["ts"] == 1_016.5

    span = next(row for row in detail_rows if row["id"] == "span:span-1")
    assert span["label"] == "agent.vendor-risk"
    assert span["agent"] == "risk-reviewer"
    assert span["skill"] == "vendor-risk"
    assert span["model"] == "gpt-4.1"
    assert span["durationMs"] == 1_500.0
    assert span["tokensIn"] == 120
    assert span["tokensOut"] == 30
    assert span["costUsd"] == 0.0042
    assert span["attributes"]["safe.details"] == {"source": "vendor-master"}

    mcp = next(row for row in detail_rows if row["kind"] == "tool")
    assert mcp["tool"] == "screenVendor"
    assert mcp["method"] == "POST"
    assert mcp["url"] == "https://mcp.example.test/screen"
    assert mcp["mcpCallIndex"] == 0
    assert "request" not in mcp
    assert "response" not in mcp
    assert "details" not in mcp
    assert mcp["statusCode"] == 200
    assert mcp["durationMs"] == 25
    assert mcp["timestamp"] == 1_014.0
    assert detail_payload["mcpCalls"][mcp["mcpCallIndex"]]["request"] == {
        "vendorId": "V-1",
        "checks": ["sanctions"],
    }
    assert detail_payload["mcpCalls"][mcp["mcpCallIndex"]]["response"] == {
        "clear": True,
        "matches": [],
    }
    retry = next(row for row in detail_rows if row["label"] == "workflow.retry_scheduled")
    assert retry["details"] == {"attempt": 2, "error": "upstream timeout"}
    assert "ledger" not in retry


def test_timeline_span_skill_uses_production_attribute_name() -> None:
    wid = "W-DET-SPAN-SKILL"
    workflow = Workflow(
        id=wid,
        status="in_progress",
        current_phase="Execution",
        created_at=1_000.0,
        sla_due_at=2_000.0,
        jurisdiction="US",
        agency="Ogilvy-US",
    )
    app_state.store.upsert_workflow(workflow)
    app_state.store.append_span(OtelSpan(
        trace_id="trace-prod-1",
        span_id="span-prod-1",
        name="agent.vendor-risk",
        start_ms=1_012_000.0,
        end_ms=1_013_500.0,
        status="ok",
        attributes={
            "workflow.id": wid,
            "agent.name": "risk-reviewer",
            "zava.skill": "vendor-risk",
            "gen_ai.request.model": "gpt-4.1",
        },
    ))

    client = TestClient(app)
    body = client.get(f"/api/workflows/{wid}").json()
    span = next(row for row in body["timeline"] if row["id"] == "span:span-prod-1")
    assert span["skill"] == "vendor-risk"


def test_timeline_equal_timestamp_orders_phase_boundaries_around_execution() -> None:
    wid = "W-DET-EQUAL-TS"
    app_state.store.upsert_workflow(Workflow(
        id=wid,
        status="in_progress",
        current_phase="Agent work",
        created_at=1_000.0,
        sla_due_at=2_000.0,
        jurisdiction="US",
        agency="Ogilvy-US",
    ))
    app_state.store.append_phase(wid, Phase(
        workflow_id=wid,
        name="Agent work",
        status="in_progress",
        started_at=1_010.0,
    ))
    app_state.store.append_phase(wid, Phase(
        workflow_id=wid,
        name="Previous work",
        status="completed",
        started_at=1_005.0,
        completed_at=1_010.0,
    ))
    app_state.store.append_phase(wid, Phase(
        workflow_id=wid,
        name="Failed work",
        status="failed",
        started_at=1_006.0,
        completed_at=1_010.0,
    ))
    app_state.store.append_span(OtelSpan(
        trace_id=wid,
        span_id="equal-ts-agent",
        name="agent.risk-reviewer",
        start_ms=1_010_000.0,
        end_ms=1_011_000.0,
        status="ok",
        attributes={
            "workflow.id": wid,
            "agent.name": "risk-reviewer",
        },
    ))
    app_state.store.append_mcp_call(McpCall(
        workflow_id=wid,
        timestamp=1_010.0,
        tool="screenVendor",
        url="https://mcp.example.test/screen",
        method="POST",
        request={"vendorId": "V-1"},
        response={"clear": True},
        status_code=200,
        duration_ms=25,
    ))

    rows = TestClient(app).get(f"/api/workflows/{wid}").json()["timeline"]
    equal_ts_ids = [row["id"] for row in rows if row["ts"] == 1_010.0]

    assert equal_ts_ids[0] == "phase:0:Agent work"
    assert equal_ts_ids[-2:] == [
        "phase:1:Previous work",
        "phase:2:Failed work",
    ]
    assert set(equal_ts_ids[1:-2]) == {
        "span:equal-ts-agent",
        "mcp:0:screenVendor:1010.0",
    }


def test_timeline_uses_matching_span_for_legacy_production_reasoning() -> None:
    wid = "W-DET-LEGACY-REASONING"
    app_state.store.upsert_workflow(Workflow(
        id=wid,
        created_at=1_000.0,
        sla_due_at=2_000.0,
        jurisdiction="US",
        agency="Ogilvy-US",
        agent_reasoning=[{
            "agent_label": "risk_reviewer",
            "model": "gpt-4.1",
            "messages": [{"role": "assistant", "content": "Checked evidence"}],
            "tool_calls": [{"tool": "screenVendor", "result": {"clear": True}}],
            "extracted_json": {"verdict": "amber"},
            "latency_ms": 1_500,
            "usage": {"input_tokens": 120, "output_tokens": 30},
        }],
    ))
    app_state.store.append_span(OtelSpan(
        trace_id=wid,
        span_id="legacy-reasoning-span",
        name="gen_ai.generate_content",
        start_ms=1_012_000.0,
        end_ms=1_013_500.0,
        status="ok",
        attributes={
            "workflow.id": wid,
            "gen_ai.agent.name": "risk_reviewer",
            "gen_ai.request.model": "gpt-4.1",
        },
    ))

    response = TestClient(app).get(f"/api/workflows/index/timeline/{wid}")

    assert response.status_code == 200
    reasoning = next(row for row in response.json()["timeline"] if row["kind"] == "reasoning")
    assert reasoning["ts"] == 1_012.0
    assert reasoning["startedAt"] == 1_012.0
    assert reasoning["completedAt"] == 1_013.5


def test_timeline_uses_agent_output_ingestion_timestamp_without_shape_mutation() -> None:
    import asyncio

    wid = "W-DET-AGENT-OUTPUT-TIMESTAMP"
    output = {
        "verdict": "green",
        "profile": {"current_title": "Senior Data Engineer"},
    }
    app_state.store.upsert_workflow(Workflow(
        id=wid,
        created_at=1_000.0,
        sla_due_at=2_000.0,
        jurisdiction="US",
        agency="Ogilvy-US",
    ))

    asyncio.run(app_state.workflow_event_ingestor.ingest(
        wid,
        "instance-output-timestamp",
        "agent_output",
        {"agent": "cv_crystalliser", "output": output},
        at=1_234.5,
    ))

    body = TestClient(app).get(f"/api/workflows/{wid}").json()
    row = next(item for item in body["timeline"] if item["kind"] == "agentOutput")

    assert row["ts"] == 1_234.5
    assert row["details"] == output
    assert body["workflow"]["agentOutputs"]["cv_crystalliser"] == output
    assert "recorded_at" not in row["details"]


def test_complete_agent_sequence_renders_one_customer_agent_row() -> None:
    import asyncio

    wid = "W-DET-CORRELATED-AGENT"
    app_state.store.upsert_workflow(Workflow(
        id=wid,
        status="in_progress",
        current_phase="Validation",
        created_at=2_000.0,
        sla_due_at=3_000.0,
        jurisdiction="US",
        agency="Ogilvy-US",
    ))
    ingestor = app_state.workflow_event_ingestor
    asyncio.run(ingestor.ingest(wid, "instance-correlation", "executor.invoked", {
        "name": "agent_kyc_diligence",
        "type": "agent",
        "stage": "start",
    }, at=2_010.0))
    asyncio.run(ingestor.ingest(wid, "instance-correlation", "executor.invoked", {
        "name": "agent_kyc_diligence",
        "type": "agent",
        "stage": "complete",
        "duration_ms": 1_000,
    }, at=2_011.0))
    asyncio.run(ingestor.ingest(wid, "instance-correlation", "agent.completed", {
        "agent_label": "kyc-diligence",
        "agent_run_id": "run-correlated",
        "model": "gpt-4.1",
        "messages": [{"role": "assistant", "content": '{"verdict":"clear"}'}],
        "tool_calls": [],
        "extracted_json": {"verdict": "clear"},
        "latency_ms": 1_000,
        "usage": {"input_tokens": 20, "output_tokens": 5},
        "response_text": '{"verdict":"clear"}',
    }, at=2_011.0))

    body = TestClient(app).get(f"/api/workflows/{wid}").json()
    agent_rows = [
        row for row in body["timeline"]
        if row["kind"] in {"agent", "reasoning"}
    ]

    assert len(agent_rows) == 1
    assert agent_rows[0]["id"] == "reasoning:run-correlated"
    assert set(agent_rows[0]["spanIds"]) == {
        span["spanId"] for span in body["spans"]
    }
    assert len(body["spans"]) == 2


def test_production_executor_supplies_missing_reasoning_phase_without_matching_other_agent() -> None:
    import asyncio

    wid = "W-DET-PRODUCTION-KYC-CORRELATION"
    app_state.store.upsert_workflow(Workflow(
        id=wid,
        type="vendor-kyc",
        status="in_progress",
        current_phase="KYC Diligence",
        created_at=2_500.0,
        sla_due_at=3_500.0,
        jurisdiction="UK",
        agency="Zava",
    ))
    ingestor = app_state.workflow_event_ingestor
    for name in ("agent_kyc_diligence_checker", "agent_ubo_resolver"):
        asyncio.run(ingestor.ingest(wid, "instance-production-kyc", "executor.invoked", {
            "name": name,
            "type": "agent",
            "stage": "start",
            "phase": "KYC Diligence",
        }, at=2_510.0))
        asyncio.run(ingestor.ingest(wid, "instance-production-kyc", "executor.invoked", {
            "name": name,
            "type": "agent",
            "stage": "complete",
            "phase": "KYC Diligence",
            "duration_ms": 1_000,
        }, at=2_511.0))
    asyncio.run(ingestor.ingest(wid, "instance-production-kyc", "agent.completed", {
        "agent_label": "fleet-vendor-kyc-kyc-diligence-checker",
        "agent_run_id": "ar-production-kyc",
        "model": "gpt-4.1",
        "messages": [{"role": "assistant", "content": '{"verdict":"clear"}'}],
        "tool_calls": [],
        "extracted_json": {"verdict": "clear"},
        "latency_ms": 1_000,
        "usage": {"input_tokens": 20, "output_tokens": 5},
        "response_text": '{"verdict":"clear"}',
        "covered_phases": ["KYC Diligence", "UBO Resolver"],
    }, at=2_511.0))

    body = TestClient(app).get(f"/api/workflows/{wid}").json()
    spans_by_executor = {
        span["attributes"].get("executor.name"): span["spanId"]
        for span in body["spans"]
        if span["attributes"].get("executor.name")
    }
    kyc_executor_span = next(
        span for span in body["spans"]
        if span["attributes"].get("executor.name")
        == "agent_kyc_diligence_checker"
    )
    reasoning = next(
        row for row in body["timeline"]
        if row["id"] == "reasoning:ar-production-kyc"
    )
    customer_agent_rows = [
        row for row in body["timeline"]
        if row["kind"] in {"agent", "reasoning"}
    ]

    assert spans_by_executor["agent_kyc_diligence_checker"] in reasoning["spanIds"]
    assert spans_by_executor["agent_ubo_resolver"] not in reasoning["spanIds"]
    assert kyc_executor_span["attributes"]["workflow.phase"] == "KYC Diligence"
    assert reasoning["phase"] == "KYC Diligence"
    assert reasoning["coveredPhases"] == ["KYC Diligence", "UBO Resolver"]
    model_span = next(
        span for span in body["spans"]
        if span["attributes"].get("gen_ai.agent.run_id") == "ar-production-kyc"
    )
    assert model_span["attributes"]["workflow.covered_phases"] == [
        "KYC Diligence",
        "UBO Resolver",
    ]
    assert {row["id"] for row in customer_agent_rows} == {
        "reasoning:ar-production-kyc",
        f"span:{spans_by_executor['agent_ubo_resolver']}",
    }


def test_reasoning_does_not_inherit_phase_when_correlated_spans_disagree() -> None:
    wid = "W-DET-AMBIGUOUS-CORRELATED-PHASE"
    agent_label = "fleet-vendor-kyc-kyc-diligence-checker"
    app_state.store.upsert_workflow(Workflow(
        id=wid,
        type="vendor-kyc",
        created_at=2_550.0,
        sla_due_at=3_550.0,
        jurisdiction="UK",
        agency="Zava",
        agent_reasoning=[{
            "agent_label": agent_label,
            "agent_run_id": "ar-ambiguous-correlated-phase",
            "started_at": 2_560.0,
            "completed_at": 2_561.0,
            "latency_ms": 1_000,
        }],
    ))
    app_state.store.append_span(OtelSpan(
        trace_id=wid,
        span_id="span-ambiguous-executor-phase",
        name="executor.agent_kyc_diligence_checker",
        start_ms=2_560_000.0,
        end_ms=2_561_000.0,
        status="ok",
        attributes={
            "workflow.id": wid,
            "workflow.phase": "KYC Diligence",
            "executor.type": "agent",
            "executor.name": "agent_kyc_diligence_checker",
        },
    ))
    app_state.store.append_span(OtelSpan(
        trace_id=wid,
        span_id="span-ambiguous-model-phase",
        name="gen_ai.generate_content",
        start_ms=2_560_000.0,
        end_ms=2_561_000.0,
        status="ok",
        attributes={
            "workflow.id": wid,
            "workflow.phase": "UBO Resolution",
            "gen_ai.agent.name": agent_label,
            "gen_ai.agent.run_id": "ar-ambiguous-correlated-phase",
        },
    ))

    rows = TestClient(app).get(f"/api/workflows/{wid}").json()["timeline"]
    reasoning = next(
        row for row in rows
        if row["id"] == "reasoning:ar-ambiguous-correlated-phase"
    )

    assert set(reasoning["spanIds"]) == {
        "span-ambiguous-executor-phase",
        "span-ambiguous-model-phase",
    }
    assert reasoning["phase"] is None


def test_shared_invocation_id_wins_over_same_agent_timing_fallback() -> None:
    wid = "W-DET-SHARED-INVOCATION"
    agent_label = "fleet-vendor-kyc-kyc-diligence-checker"
    app_state.store.upsert_workflow(Workflow(
        id=wid,
        type="vendor-kyc",
        created_at=2_600.0,
        sla_due_at=3_600.0,
        jurisdiction="UK",
        agency="Zava",
        agent_reasoning=[{
            "agent_label": agent_label,
            "agent_run_id": "ar-target",
            "phase": "KYC Diligence",
            "started_at": 2_610.0,
            "completed_at": 2_611.0,
            "latency_ms": 1_000,
        }],
    ))
    for span_id, agent_run_id in (
        ("span-other-invocation", "ar-other"),
        ("span-target-invocation", "ar-target"),
    ):
        app_state.store.append_span(OtelSpan(
            trace_id=wid,
            span_id=span_id,
            name="gen_ai.generate_content",
            start_ms=2_610_000.0,
            end_ms=2_611_000.0,
            status="ok",
            attributes={
                "workflow.id": wid,
                "workflow.phase": "KYC Diligence",
                "gen_ai.agent.name": agent_label,
                "gen_ai.agent.run_id": agent_run_id,
            },
        ))

    rows = TestClient(app).get(f"/api/workflows/{wid}").json()["timeline"]
    reasoning = next(row for row in rows if row["id"] == "reasoning:ar-target")

    assert reasoning["spanId"] == "span-target-invocation"
    assert reasoning["spanIds"] == ["span-target-invocation"]
    assert any(row["id"] == "span:span-other-invocation" for row in rows)


def test_one_executor_correlates_distinct_session_runs_without_crossing_spans() -> None:
    wid = "W-DET-ONE-EXECUTOR-TWO-SESSIONS"
    parent_id = "executor-parent-1"
    agent_label = "fleet-vendor-kyc-kyc-diligence-checker"
    app_state.store.upsert_workflow(Workflow(
        id=wid,
        type="vendor-kyc",
        created_at=2_650.0,
        sla_due_at=3_650.0,
        jurisdiction="UK",
        agency="Zava",
        agent_reasoning=[
            {
                "agent_label": agent_label,
                "agent_run_id": "session-run-2",
                "invocation_id": parent_id,
                "phase": "KYC Diligence",
                "started_at": 2_660.0,
                "completed_at": 2_661.0,
                "latency_ms": 1_000,
            },
            {
                "agent_label": agent_label,
                "agent_run_id": "session-run-1",
                "invocation_id": parent_id,
                "phase": "KYC Diligence",
                "started_at": 2_660.0,
                "completed_at": 2_661.0,
                "latency_ms": 1_000,
            },
        ],
    ))
    app_state.store.append_span(OtelSpan(
        trace_id=wid,
        span_id="span-parent-executor",
        name="executor.agent_kyc_diligence_checker",
        start_ms=2_660_000.0,
        end_ms=2_661_000.0,
        status="ok",
        attributes={
            "workflow.id": wid,
            "workflow.phase": "KYC Diligence",
            "executor.type": "agent",
            "executor.name": "agent_kyc_diligence_checker",
            "zava.invocation.id": parent_id,
        },
    ))
    for run_id in ("session-run-1", "session-run-2"):
        app_state.store.append_span(OtelSpan(
            trace_id=wid,
            span_id=f"span-{run_id}",
            name="gen_ai.generate_content",
            start_ms=2_660_000.0,
            end_ms=2_661_000.0,
            status="ok",
            attributes={
                "workflow.id": wid,
                "workflow.phase": "KYC Diligence",
                "gen_ai.agent.name": agent_label,
                "gen_ai.agent.run.id": run_id,
                "zava.invocation.id": parent_id,
            },
        ))

    rows = TestClient(app).get(f"/api/workflows/{wid}").json()["timeline"]
    reasoning_by_run = {
        row["agentRunId"]: row
        for row in rows
        if row["kind"] == "reasoning"
    }

    assert set(reasoning_by_run) == {"session-run-1", "session-run-2"}
    for run_id, reasoning in reasoning_by_run.items():
        assert reasoning["id"] == f"reasoning:{run_id}"
        assert reasoning["invocationId"] == parent_id
        assert f"span-{run_id}" in reasoning["spanIds"]
        assert "span-parent-executor" in reasoning["spanIds"]
        other_run = "session-run-2" if run_id == "session-run-1" else "session-run-1"
        assert f"span-{other_run}" not in reasoning["spanIds"]


def test_legacy_notification_executor_correlates_by_unique_phase_and_time() -> None:
    wid = "W-DET-LEGACY-NOTIFICATION"
    app_state.store.upsert_workflow(Workflow(
        id=wid,
        type="hiring",
        created_at=2_700.0,
        sla_due_at=3_700.0,
        jurisdiction="UK",
        agency="Zava",
        agent_reasoning=[{
            "agent_label": "notification-composer",
            "phase": "Notify",
            "started_at": 2_710.0,
            "completed_at": 2_711.0,
            "latency_ms": 1_000,
        }],
    ))
    app_state.store.append_span(OtelSpan(
        trace_id=wid,
        span_id="span-legacy-notification",
        name="executor.agent_notification",
        start_ms=2_710_000.0,
        end_ms=2_711_000.0,
        status="ok",
        attributes={
            "workflow.id": wid,
            "workflow.phase": "Notify",
            "executor.type": "agent",
            "executor.name": "agent_notification",
        },
    ))

    rows = TestClient(app).get(f"/api/workflows/{wid}").json()["timeline"]
    customer_agent_rows = [
        row for row in rows if row["kind"] in {"agent", "reasoning"}
    ]

    assert [row["id"] for row in customer_agent_rows] == ["reasoning:0"]
    assert customer_agent_rows[0]["spanIds"] == ["span-legacy-notification"]


def test_phase_less_production_notification_executor_alias_correlates_once() -> None:
    import asyncio

    wid = "W-DET-PHASELESS-NOTIFICATION"
    app_state.store.upsert_workflow(Workflow(
        id=wid,
        type="hiring",
        created_at=2_900.0,
        sla_due_at=3_900.0,
        jurisdiction="UK",
        agency="Zava",
    ))
    ingestor = app_state.workflow_event_ingestor

    asyncio.run(ingestor.ingest(wid, "instance-production-notification", "executor.invoked", {
        "name": "agent_notification",
        "type": "agent",
        "stage": "start",
    }, at=2_910.0))
    asyncio.run(ingestor.ingest(wid, "instance-production-notification", "executor.invoked", {
        "name": "agent_notification",
        "type": "agent",
        "stage": "complete",
        "duration_ms": 1_000,
    }, at=2_911.0))
    asyncio.run(ingestor.ingest(wid, "instance-production-notification", "agent.completed", {
        "agent_label": "notification-composer",
        "agent_run_id": "run-notification-1",
        "invocation_id": "invocation-notification-1",
        "model": "gpt-4.1",
        "messages": [{"role": "assistant", "content": '{"status":"sent"}'}],
        "tool_calls": [],
        "extracted_json": {"status": "sent"},
        "latency_ms": 1_000,
        "usage": {"input_tokens": 20, "output_tokens": 5},
        "response_text": '{"status":"sent"}',
    }, at=2_911.0))

    body = TestClient(app).get(f"/api/workflows/{wid}").json()
    rows = [
        row for row in body["timeline"]
        if row["kind"] in {"agent", "reasoning"}
    ]
    executor = next(row for row in body["spans"] if row["spanId"] and row["spanId"] != "" and row["name"] == "executor.agent_notification")
    reasoning = next(row for row in rows if row["kind"] == "reasoning")
    generated = next(row for row in body["spans"] if row["name"] == "gen_ai.generate_content")

    assert [row["id"] for row in rows] == ["reasoning:run-notification-1"]
    assert reasoning["spanId"] == generated["spanId"]
    assert set(reasoning["spanIds"]) == {executor["spanId"], generated["spanId"]}


def test_phase_less_notification_ambiguity_stays_unmatched() -> None:
    wid = "W-DET-PHASELESS-NOTIFICATION-AMBIGUOUS"
    app_state.store.upsert_workflow(Workflow(
        id=wid,
        type="hiring",
        created_at=2_950.0,
        sla_due_at=3_950.0,
        jurisdiction="UK",
        agency="Zava",
        agent_reasoning=[
            {
                "agent_label": "notification-composer",
                "started_at": 2_960.0,
                "completed_at": 2_961.0,
                "latency_ms": 1_000,
            },
            {
                "agent_label": "notification-summary",
                "started_at": 2_960.0,
                "completed_at": 2_961.0,
                "latency_ms": 1_000,
            },
        ],
    ))
    for span_id, executor_name in (
        ("span-ambiguous-notification-a", "agent_notification"),
        ("span-ambiguous-notification-b", "agent_notification_helper"),
    ):
        app_state.store.append_span(OtelSpan(
            trace_id=wid,
            span_id=span_id,
            name=f"executor.{executor_name}",
            start_ms=2_960_000.0,
            end_ms=2_961_000.0,
            status="ok",
            attributes={
                "workflow.id": wid,
                "executor.type": "agent",
                "executor.name": executor_name,
            },
        ))

    rows = TestClient(app).get(f"/api/workflows/{wid}").json()["timeline"]
    customer_agent_rows = [
        row for row in rows if row["kind"] in {"agent", "reasoning"}
    ]

    assert {row["id"] for row in customer_agent_rows} == {
        "reasoning:0",
        "reasoning:1",
        "span:span-ambiguous-notification-a",
        "span:span-ambiguous-notification-b",
    }
    assert all(
        row["spanIds"] == []
        for row in customer_agent_rows
        if row["kind"] == "reasoning"
    )


def test_legacy_phase_time_fallback_keeps_ambiguous_concurrent_agents_separate() -> None:
    wid = "W-DET-AMBIGUOUS-LEGACY-AGENTS"
    app_state.store.upsert_workflow(Workflow(
        id=wid,
        type="hiring",
        created_at=2_800.0,
        sla_due_at=3_800.0,
        jurisdiction="UK",
        agency="Zava",
        agent_reasoning=[
            {
                "agent_label": "notification-composer",
                "phase": "Notify",
                "started_at": 2_810.0,
                "completed_at": 2_811.0,
            },
            {
                "agent_label": "delivery-composer",
                "phase": "Notify",
                "started_at": 2_810.0,
                "completed_at": 2_811.0,
            },
        ],
    ))
    for span_id, executor_name in (
        ("span-ambiguous-notification", "agent_notification"),
        ("span-ambiguous-delivery", "agent_delivery"),
    ):
        app_state.store.append_span(OtelSpan(
            trace_id=wid,
            span_id=span_id,
            name=f"executor.{executor_name}",
            start_ms=2_810_000.0,
            end_ms=2_811_000.0,
            status="ok",
            attributes={
                "workflow.id": wid,
                "workflow.phase": "Notify",
                "executor.type": "agent",
                "executor.name": executor_name,
            },
        ))

    rows = TestClient(app).get(f"/api/workflows/{wid}").json()["timeline"]
    customer_agent_rows = [
        row for row in rows if row["kind"] in {"agent", "reasoning"}
    ]

    assert {row["id"] for row in customer_agent_rows} == {
        "reasoning:0",
        "reasoning:1",
        "span:span-ambiguous-notification",
        "span:span-ambiguous-delivery",
    }
    assert all(
        row["spanIds"] == []
        for row in customer_agent_rows
        if row["kind"] == "reasoning"
    )


def test_telco_decision_and_outcome_render_as_exact_deterministic_outputs() -> None:
    wid = "CARE-DET-OUTPUT"
    decision = {
        "command": {
            "command_id": "care-cmd-1",
            "type": "apply_customer_remediation",
            "payload": {"account_ids": ["ACC-1"], "credit": 20},
        },
        "reasoning": {
            "summary": "Vulnerable customer entitlement applied",
            "policy": "CARE-17",
        },
    }
    outcome = {
        "status": "resolved",
        "evidence_event_type": "customer.notified",
        "results": {"notified": 1, "credits_applied": 1},
    }
    app_state.store.upsert_workflow(Workflow(
        id=wid,
        type="proactive-customer-care",
        created_at=1_000.0,
        sla_due_at=2_000.0,
        jurisdiction="UK",
        agency="Zava",
        payload={"decision": decision, "outcome": outcome},
        action_ledger=[
            ActionLedgerEntry(
                workflow_id=wid,
                timestamp=1_010.0,
                actor_kind="agent",
                actor_id="world_bridge",
                action="responder.decided",
                revocable=False,
                details={},
            ),
            ActionLedgerEntry(
                workflow_id=wid,
                timestamp=1_020.0,
                actor_kind="agent",
                actor_id="orchestrator",
                action="workflow.completed",
                revocable=False,
                details={},
            ),
        ],
    ))

    rows = TestClient(app).get(f"/api/workflows/{wid}").json()["timeline"]
    outputs = [row for row in rows if row["kind"] == "output"]

    assert [(row["label"], row["details"]) for row in outputs] == [
        ("decision.output", decision),
        ("workflow.outcome", outcome),
    ]
    assert "reasoning" not in outputs[0]
    assert "command" not in outputs[0]
    assert outputs[0]["ts"] == 1_010.0
    assert "results" not in outputs[1]
    assert outputs[1]["ts"] == 1_020.0
    assert not any(row["kind"] == "agent" for row in rows)


def test_telco_outcome_simulation_timestamps_fall_back_to_terminal_ledger() -> None:
    wid = "CARE-DET-SIM-TIMESTAMP"
    app_state.store.upsert_workflow(Workflow(
        id=wid,
        type="proactive-customer-care",
        status="completed",
        created_at=1_000.0,
        sla_due_at=2_000.0,
        jurisdiction="UK",
        agency="Zava",
        payload={
            "decision": {
                "command": {
                    "command_id": "care-cmd-2",
                    "type": "apply_customer_remediation",
                    "payload": {"account_ids": ["ACC-9"], "credit": 10},
                },
                "started_at": 137.0,
                "completed_at": 137.0,
            },
            "outcome": {
                "status": "resolved",
                "evidence_event_type": "customer.notified",
                "results": {"notified": 1, "credits_applied": 1},
                "started_at": 137.0,
                "completed_at": 137.0,
            },
        },
        action_ledger=[
            ActionLedgerEntry(
                workflow_id=wid,
                timestamp=1_010.0,
                actor_kind="agent",
                actor_id="world_bridge",
                action="responder.decided",
                revocable=False,
                details={},
            ),
            ActionLedgerEntry(
                workflow_id=wid,
                timestamp=1_020.0,
                actor_kind="agent",
                actor_id="orchestrator",
                action="workflow.completed",
                revocable=False,
                details={},
            ),
        ],
    ))

    rows = TestClient(app).get(f"/api/workflows/{wid}").json()["timeline"]
    decision = next(row for row in rows if row["label"] == "decision.output")
    outcome = next(row for row in rows if row["label"] == "workflow.outcome")

    assert decision["ts"] == 1_010.0
    assert outcome["ts"] == 1_020.0
    assert outcome["ts"] > 1_000.0
    assert [row["label"] for row in rows if row["ts"] == 1_020.0] == [
        "workflow.outcome",
        "workflow.completed",
    ]


def test_deterministic_outputs_use_latest_real_evidence_timestamp_not_epoch() -> None:
    wid = "CARE-DET-TIMESTAMP"
    app_state.store.upsert_workflow(Workflow(
        id=wid,
        type="proactive-customer-care",
        status="completed",
        created_at=0.0,
        sla_due_at=2_000.0,
        jurisdiction="UK",
        agency="Zava",
        payload={
            "decision": {"command": {"type": "apply_credit"}},
            "outcome": {"status": "resolved"},
        },
        action_ledger=[
            ActionLedgerEntry(
                workflow_id=wid,
                timestamp=1_234.0,
                actor_kind="agent",
                actor_id="system",
                action="phase.completed:Apply remediation",
                revocable=False,
                details={"evidence": "ledger-backed"},
            ),
        ],
    ))
    app_state.store.append_phase(wid, Phase(
        workflow_id=wid,
        name="Apply remediation",
        status="completed",
        started_at=1_200.0,
        completed_at=1_234.0,
    ))

    rows = TestClient(app).get(f"/api/workflows/{wid}").json()["timeline"]
    outputs = [row for row in rows if row["kind"] == "output"]

    assert [row["ts"] for row in outputs] == [1_234.0, 1_234.0]
    assert all(row["ts"] > 0 for row in outputs)
    assert [
        row["label"]
        for row in rows
        if row["ts"] == 1_234.0
    ] == [
        "Apply remediation",
        "decision.output",
        "workflow.outcome",
        "workflow.completed",
    ]
    terminal = next(row for row in rows if row["label"] == "workflow.completed")
    assert terminal["status"] == "completed"


def test_matching_phase_completion_ledger_is_merged_without_losing_evidence() -> None:
    wid = "W-PHASE-MERGE"
    app_state.store.upsert_workflow(Workflow(
        id=wid,
        status="completed",
        created_at=1_000.0,
        sla_due_at=2_000.0,
        jurisdiction="UK",
        agency="Zava",
        action_ledger=[
            ActionLedgerEntry(
                workflow_id=wid,
                timestamp=1_020.0,
                actor_kind="agent",
                actor_id="system",
                action="phase.completed:Validation",
                revocable=False,
                details={"duration_ms": 10_000, "evidence": "validated"},
                decision_id="phase-decision",
                policy_version="2026-07",
            ),
            ActionLedgerEntry(
                workflow_id=wid,
                timestamp=1_021.0,
                actor_kind="human",
                actor_id="reviewer",
                action="governance.attested",
                revocable=False,
                details={"note": "unique"},
            ),
        ],
    ))
    app_state.store.append_phase(wid, Phase(
        workflow_id=wid,
        name="Validation",
        status="completed",
        started_at=1_010.0,
        completed_at=1_020.0,
    ))

    rows = TestClient(app).get(f"/api/workflows/{wid}").json()["timeline"]
    matching = [
        row
        for row in rows
        if (
            row["kind"] == "phase"
            and row["label"] == "Validation"
        ) or row["label"] == "phase.completed:Validation"
    ]

    assert len(matching) == 1
    phase = matching[0]
    assert phase["decisionId"] == "phase-decision"
    assert phase["policyVersion"] == "2026-07"
    assert phase["ledger"]["details"]["evidence"] == "validated"
    assert phase["agentId"] == "system"
    assert "actor" not in phase
    assert any(row["label"] == "governance.attested" for row in rows)


def test_matching_phase_failure_ledger_is_merged_without_losing_evidence() -> None:
    wid = "W-PHASE-FAIL-MERGE"
    app_state.store.upsert_workflow(Workflow(
        id=wid,
        status="failed",
        created_at=1_000.0,
        sla_due_at=2_000.0,
        jurisdiction="UK",
        agency="Zava",
        action_ledger=[
            ActionLedgerEntry(
                workflow_id=wid,
                timestamp=1_030.0,
                actor_kind="agent",
                actor_id="system",
                action="phase.failed:Validation",
                revocable=False,
                details={"reason": "upstream timeout", "evidence": "alerts"},
                decision_id="phase-failure",
                policy_version="2026-07",
            ),
            ActionLedgerEntry(
                workflow_id=wid,
                timestamp=1_031.0,
                actor_kind="human",
                actor_id="reviewer",
                action="governance.attested",
                revocable=False,
                details={"note": "unique"},
            ),
        ],
    ))
    app_state.store.append_phase(wid, Phase(
        workflow_id=wid,
        name="Validation",
        status="failed",
        started_at=1_010.0,
        completed_at=1_030.0,
    ))

    rows = TestClient(app).get(f"/api/workflows/{wid}").json()["timeline"]
    matching = [
        row
        for row in rows
        if (
            row["kind"] == "phase"
            and row["label"] == "Validation"
        ) or row["label"] == "phase.failed:Validation"
    ]

    assert len(matching) == 1
    phase = matching[0]
    assert phase["status"] == "failed"
    assert phase["decisionId"] == "phase-failure"
    assert phase["policyVersion"] == "2026-07"
    assert phase["ledger"]["details"]["reason"] == "upstream timeout"
    assert phase["agentId"] == "system"
    assert "actor" not in phase
    assert any(row["label"] == "governance.attested" for row in rows)


def test_fashion_persisted_command_renders_as_deterministic_output() -> None:
    wid = "FASH-DET-OUTPUT"
    persisted = {
        "command": {
            "command_id": "cmd-fashion-1",
            "type": "transfer_inventory",
            "payload": {
                "source_location_id": "STORE-EU-PAR-01",
                "destination_location_id": "STORE-UK-LON-01",
                "sku_id": "SKU-1",
                "quantity": 24,
            },
        },
        "reasoning": {
            "summary": "Prepared transfer from journal-backed evidence.",
            "authority": {
                "persona": "merchandising_director",
                "decision": "approve",
            },
        },
    }
    app_state.store.upsert_workflow(Workflow(
        id=wid,
        type="inventory-rebalancing",
        created_at=2_000.0,
        sla_due_at=3_000.0,
        jurisdiction="UK",
        agency="Zava",
        payload={"decision": persisted},
    ))

    rows = TestClient(app).get(f"/api/workflows/{wid}").json()["timeline"]
    output = next(row for row in rows if row["kind"] == "output")

    assert output["label"] == "decision.output"
    assert output["details"] == persisted
    assert "command" not in output
    assert "reasoning" not in output
    assert not any(row["kind"] == "agent" for row in rows)


def test_production_agent_completed_and_wrapper_tool_result_remain_represented() -> None:
    wid = "AGENCY-PRODUCTION-EVIDENCE"
    app_state.store.upsert_workflow(Workflow(
        id=wid,
        type="vendor-kyc",
        created_at=3_000.0,
        sla_due_at=4_000.0,
        jurisdiction="UK",
        agency="Zava",
    ))
    ingestor = app_state.workflow_event_ingestor
    messages = [
        {"role": "user", "content": "Screen Acme"},
        {"role": "assistant", "content": '{"verdict":"clear"}'},
    ]
    tool_calls = [{
        "tool_call_id": "call-1",
        "name": "sanctions_api_screen_entity",
        "tool": "sanctions_api_screen_entity",
        "args": '{"name":"Acme"}',
        "result": '{"matches":[]}',
        "success": True,
        "latency_ms": 25,
    }]

    import asyncio

    asyncio.run(ingestor.ingest(wid, "instance-agency-1", "tool.invoked", {
        "tool": "sanctions_api_screen_entity",
        "skill": "kyc-diligence",
        "stage": "complete",
        "tool_call_id": "call-1",
        "args": '{"name":"Acme"}',
        "result": '{"matches":[]}',
        "success": True,
        "duration_ms": 25,
    }, at=3_010.0))
    asyncio.run(ingestor.ingest(wid, "instance-agency-1", "agent.completed", {
        "agent_label": "kyc-diligence",
        "agent_run_id": "agent-run-1",
        "model": "gpt-4.1",
        "messages": messages,
        "tool_calls": tool_calls,
        "extracted_json": {"verdict": "clear"},
        "latency_ms": 100,
        "usage": {"input_tokens": 40, "output_tokens": 10},
        "response_text": '{"verdict":"clear"}',
    }, at=3_011.0))

    body = TestClient(app).get(f"/api/workflows/{wid}").json()
    rows = body["timeline"]
    reasoning = next(row for row in rows if row["id"] == "reasoning:agent-run-1")
    tool = next(
        row for row in rows
        if row["kind"] == "tool" and row["tool"] == "sanctions_api_screen_entity"
    )

    assert reasoning["messages"] == messages
    assert reasoning["toolCalls"] == [{
        "toolCallId": "call-1",
        "name": "sanctions_api_screen_entity",
        "tool": "sanctions_api_screen_entity",
        "success": True,
        "latency_ms": 25,
    }]
    assert reasoning["extractedJson"] == {"verdict": "clear"}
    assert reasoning["latencyMs"] == 100
    assert reasoning["tokensIn"] == 40
    assert reasoning["tokensOut"] == 10
    assert "details" not in reasoning
    assert "request" not in tool
    assert "response" not in tool
    canonical_call = body["mcpCalls"][tool["mcpCallIndex"]]
    assert canonical_call["toolCallId"] == "call-1"
    assert reasoning["toolCalls"][0]["toolCallId"] == canonical_call["toolCallId"]
    assert tool["toolCallId"] == canonical_call["toolCallId"]
    assert tool["id"] == canonical_call["toolCallId"]
    assert canonical_call["request"] == {"name": "Acme"}
    assert canonical_call["response"] == {"matches": []}


def test_large_tool_evidence_has_bounded_detail_response_amplification() -> None:
    wid = "W-DET-LARGE-EVIDENCE"
    unique_evidence = "UNIQUE-LARGE-TOOL-EVIDENCE-" + ("x" * 64_000)
    request = {"query": "all active vendors"}
    response = {
        "records": [{
            "vendor_id": "V-LARGE",
            "evidence": unique_evidence,
        }],
    }
    tool_call = {
        "name": "vendor_registry_lookup",
        "tool": "vendor_registry_lookup",
        "args": json.dumps(request, separators=(",", ":")),
        "result": json.dumps(response, separators=(",", ":")),
        "success": True,
        "latency_ms": 25,
    }
    app_state.store.upsert_workflow(Workflow(
        id=wid,
        type="vendor-kyc",
        created_at=3_500.0,
        sla_due_at=4_500.0,
        jurisdiction="UK",
        agency="Zava",
        agent_reasoning=[{
            "agent_run_id": "run-large-evidence",
            "agent_label": "kyc-diligence",
            "model": "gpt-4.1",
            "started_at": 3_510.0,
            "completed_at": 3_511.0,
            "messages": [{"role": "assistant", "content": '{"verdict":"clear"}'}],
            "tool_calls": [tool_call],
            "extracted_json": {"verdict": "clear"},
            "latency_ms": 1_000,
            "usage": {"input_tokens": 20, "output_tokens": 5},
        }],
    ))
    app_state.store.append_mcp_call(McpCall(
        workflow_id=wid,
        timestamp=3_510.5,
        tool="vendor_registry_lookup",
        url="local://tool/vendor_registry_lookup",
        method="EXEC",
        request=request,
        response=response,
        status_code=200,
        duration_ms=25,
    ))
    app_state.store.append_agent_output(
        wid,
        "kyc-diligence",
        {
            "verdict": "clear",
            "summary": "Vendor evidence is complete.",
            "_raw_tool_calls": [tool_call],
            "profile": {"status": "verified"},
        },
        recorded_at=3_511.0,
    )

    client = TestClient(app)
    detail_response = client.get(f"/api/workflows/{wid}")
    timeline_response = client.get(f"/api/workflows/index/timeline/{wid}")
    body = detail_response.json()
    timeline_body = timeline_response.json()
    tool_row = next(row for row in body["timeline"] if row["kind"] == "tool")
    agent_row = next(row for row in body["timeline"] if row["kind"] == "reasoning")
    output_row = next(row for row in body["timeline"] if row["kind"] == "agentOutput")

    assert "agentReasoning" not in body["workflow"]
    assert tool_row["mcpCallIndex"] == 0
    assert "request" not in tool_row
    assert "response" not in tool_row
    assert "details" not in tool_row
    assert "details" not in agent_row
    assert agent_row["toolCalls"] == [{
        "name": "vendor_registry_lookup",
        "tool": "vendor_registry_lookup",
        "success": True,
        "latency_ms": 25,
    }]
    assert body["mcpCalls"][0]["request"] == request
    assert body["mcpCalls"][0]["response"] == response
    assert body["workflow"]["agentOutputs"]["kyc-diligence"] == {
        "verdict": "clear",
        "summary": "Vendor evidence is complete.",
        "profile": {"status": "verified"},
    }
    assert output_row["details"] == body["workflow"]["agentOutputs"]["kyc-diligence"]
    assert "_raw_tool_calls" not in body["workflow"]["agentOutputs"]["kyc-diligence"]
    assert detail_response.content.count(unique_evidence.encode()) == 1
    assert timeline_body["mcpCalls"] == body["mcpCalls"]
    assert "agentReasoning" not in timeline_body["workflow"]
    standalone_tool_row = next(
        row for row in timeline_body["timeline"] if row["kind"] == "tool"
    )
    assert standalone_tool_row["id"] == tool_row["id"]
    assert standalone_tool_row["mcpCallIndex"] == tool_row["mcpCallIndex"]


def test_deterministic_executor_span_is_system_evidence_not_agent() -> None:
    wid = "DET-SPAN-KIND"
    app_state.store.upsert_workflow(Workflow(
        id=wid,
        type="inventory-rebalancing",
        created_at=4_000.0,
        sla_due_at=5_000.0,
        jurisdiction="UK",
        agency="Zava",
    ))
    app_state.store.append_span(OtelSpan(
        trace_id=wid,
        span_id="det-span-1",
        name="executor.calculate_rebalance",
        start_ms=4_010_000.0,
        end_ms=4_010_010.0,
        status="ok",
        attributes={
            "workflow.id": wid,
            "executor.name": "calculate_rebalance",
            "executor.type": "deterministic",
        },
    ))

    rows = TestClient(app).get(f"/api/workflows/{wid}").json()["timeline"]
    span = next(row for row in rows if row["id"] == "span:det-span-1")

    assert span["kind"] == "system"

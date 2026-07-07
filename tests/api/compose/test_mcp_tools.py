import asyncio
from pathlib import Path

import pytest
from api.server.services.compose import registry, mcp_server
from api.server.services.compose.session import ComposeSession


ROOT = Path(__file__).resolve().parents[3]
BRIEF = ROOT / "docs/superpowers/specs/capex-approval-brief.yaml"


def _fresh_session():
    registry.reset()
    s = ComposeSession("cid")
    registry.register(s)
    return s


def test_report_stage_emits_stage_event():
    s = _fresh_session()
    q = s.subscribe()
    mcp_server._report_stage_impl("composing", "Composing")
    assert q.get_nowait() == {"type": "stage", "stage": "composing", "label": "Composing"}
    assert s.stage == "composing"


def test_composition_complete_emits_done():
    s = _fresh_session()
    q = s.subscribe()
    mcp_server._composition_complete_impl("capex-approval", "Capex Approval")
    assert q.get_nowait() == {
        "type": "done", "workflow_type": "capex-approval", "display_name": "Capex Approval"}


@pytest.mark.asyncio
async def test_ask_operator_blocks_until_answer():
    s = _fresh_session()
    q = s.subscribe()
    task = asyncio.create_task(mcp_server._ask_operator_impl("CFO or committee?", ["CFO", "committee"]))
    await asyncio.sleep(0.05)
    event = q.get_nowait()
    assert event["type"] == "question" and event["options"] == ["CFO", "committee"]
    s.resolve(event["request_id"], "CFO")
    assert await asyncio.wait_for(task, timeout=1) == "CFO"


@pytest.mark.asyncio
async def test_present_brief_blocks_until_review():
    s = _fresh_session()
    q = s.subscribe()
    yaml = BRIEF.read_text()
    task = asyncio.create_task(mcp_server._present_brief_impl(yaml))
    await asyncio.sleep(0.05)
    event = q.get_nowait()
    assert event["type"] == "brief" and event["yaml"] == yaml
    assert event["parsed"]["workflowType"] == "capex-approval"
    assert len(event["parsed"]["steps"]) == 4
    s.resolve(event["request_id"], {"approved": True, "yaml": "domain: x-edited"})
    assert await asyncio.wait_for(task, timeout=1) == {"approved": True, "yaml": "domain: x-edited"}


@pytest.mark.asyncio
async def test_present_brief_emits_none_parsed_for_malformed_yaml():
    s = _fresh_session()
    q = s.subscribe()
    task = asyncio.create_task(mcp_server._present_brief_impl("domain: ["))
    await asyncio.sleep(0.05)
    event = q.get_nowait()
    assert event["type"] == "brief" and event["parsed"] is None
    s.resolve(event["request_id"], {"approved": False, "yaml": "domain: ["})
    assert await asyncio.wait_for(task, timeout=1) == {"approved": False, "yaml": "domain: ["}

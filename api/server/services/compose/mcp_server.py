"""compose-bridge MCP server: the structured HITL + progress channel the
compose agent calls. Mounted at /api/compose/mcp (streamable HTTP) in a later
task. v1 resolves the target session via the registry's `active` pointer
(one run at a time).

The `_impl` functions hold the logic and are unit-tested directly; the FastMCP
`@mcp.tool()` wrappers just delegate to them.
"""
from __future__ import annotations

import uuid

from mcp.server.fastmcp import FastMCP

from . import registry

mcp = FastMCP("compose-bridge")


def _emit(event: dict) -> None:
    session = registry.active()
    if session is not None:
        session.emit(event)


def _report_stage_impl(stage: str, label: str) -> str:
    _emit({"type": "stage", "stage": stage, "label": label})
    return "ok"


def _composition_complete_impl(workflow_type: str, display_name: str) -> str:
    _emit({"type": "done", "workflow_type": workflow_type, "display_name": display_name})
    return "ok"


async def _ask_operator_impl(question: str, options: list[str] | None = None) -> str:
    session = registry.active()
    if session is None:
        return ""
    request_id = uuid.uuid4().hex
    fut = session.new_pending(request_id)
    session.emit({"type": "question", "request_id": request_id,
                  "text": question, "options": options or []})
    return await fut


async def _present_brief_impl(yaml: str) -> dict:
    session = registry.active()
    if session is None:
        return {"approved": True, "yaml": yaml}
    request_id = uuid.uuid4().hex
    fut = session.new_pending(request_id)
    session.emit({"type": "brief", "request_id": request_id, "yaml": yaml})
    return await fut


@mcp.tool()
def report_stage(stage: str, label: str) -> str:
    """Report the current composition stage (intake|understanding|brief|composing|graduating|verifying|ready)."""
    return _report_stage_impl(stage, label)


@mcp.tool()
async def ask_operator(question: str, options: list[str] | None = None) -> str:
    """Ask the operator a clarifying question and wait for the answer. Use ONLY when the document is genuinely ambiguous."""
    return await _ask_operator_impl(question, options)


@mcp.tool()
async def present_brief(yaml: str) -> dict:
    """Present the drafted domain brief for operator review; returns {approved, yaml} (yaml may be operator-edited). Call before composing."""
    return await _present_brief_impl(yaml)


@mcp.tool()
def composition_complete(workflow_type: str, display_name: str) -> str:
    """Signal that the domain is graduated and verified; reveals the Ignite control."""
    return _composition_complete_impl(workflow_type, display_name)

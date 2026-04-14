# src/server/mcp_tools/propose_skill_amp.py
from __future__ import annotations
import json
import time
from typing import Any
from pydantic import BaseModel
from nanoid import generate as nanoid
from copilot.tools import define_tool, ToolInvocation, ToolResult
from src.server.services.state_store import StateStore
from src.shared.types import SkillAmplification, PolicyRef


class ProposeSkillAmpParams(BaseModel):
    workflow_id: str
    policy_context: list[dict[str, Any]] | None = None
    precedents: list[dict[str, Any]] | None = None
    recommended_approach: str


def make_propose_skill_amp_tool(store: StateStore):
    @define_tool(description="Emit a coach card for an operator with policy context and precedents.", skip_permission=True)
    def propose_skill_amplification(params: ProposeSkillAmpParams, invocation: ToolInvocation) -> ToolResult:
        a = SkillAmplification(
            id=f"AMP-{nanoid(size=8)}",
            workflow_id=params.workflow_id,
            policy_context=[PolicyRef(**p) for p in (params.policy_context or [])],
            precedents=params.precedents or [],
            recommended_approach=params.recommended_approach,
            created_at=time.time(),
        )
        store.append_amplification(params.workflow_id, a)
        return ToolResult(text_result_for_llm=json.dumps({"amplification_id": a.id}), result_type="success")

    return propose_skill_amplification

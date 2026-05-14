"""Phase 7 (Audit) graph: agent_audit_summariser → terminal."""
from __future__ import annotations
from unittest.mock import AsyncMock, patch

import pytest

from api.functions.graphs.audit import build_audit_workflow


@pytest.mark.asyncio
async def test_audit_graph_runs_summariser():
    fake = {
        "summary": "Compact narrative covering the workflow.",
        "claim_id": "CLM-0042",
        "workflow_id": "EXP-0001",
    }
    with patch(
        "api.functions.graphs.executors.agents.agent_audit_summariser.execute",
        AsyncMock(return_value={"audit": fake}),
    ):
        wf = build_audit_workflow()
        events = await wf.run({"workflow_id": "EXP-0001", "claim_id": "CLM-0042"})
    out = events.get_outputs()[0]
    assert out["audit"]["summary"]
    assert out["audit"]["workflow_id"] == "EXP-0001"

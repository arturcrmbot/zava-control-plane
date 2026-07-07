# src/functions/graphs/voice.py
"""POC2 Phase 6 (Voice screening) graph.

The orchestration generator in `api/functions/workflows/hiring.py` now
gates Phase 6 on a `voice_complete` external event raced against a 24h
timer (see `VOICE_SCREEN_TIMEOUT`). Before suspending, the orchestrator
issues a `screen`-scope magic link via `issue_screen_link_activity` and
emails the candidate the /screen call URL via
`send_screen_email_activity`. The FastAPI route
`/api/portal/voice/{candidate_id}/transcript` raises the
`voice_complete` event with the final score after the firstcentral s2s
accelerator's frontend POSTs the transcript on call-end.

This graph runs AFTER the suspend resolves: its job is to log a span,
validate the transcript schema against the existing rubric, and emit
the structured verdict downstream phases consume. The score from the
external-event payload is folded into the result by the orchestration
generator. ACS / GPT-Realtime live behind the accelerator black box —
the legacy `acs-mcp` mock is retained only for `VOICE_TRANSPORT=canned`
demo robustness.
"""
from __future__ import annotations
from agent_framework import Workflow

from api.functions.graphs._tracked_executor import build_linear_workflow
from api.functions.graphs.executors.agents import agent_hiring_stub
from api.functions.graphs.executors.validators import validate_hiring_stub


def build_hiring_voice_workflow() -> Workflow:
    return build_linear_workflow([
        ("hiring_voice", "agent_voice_screener", "agent", agent_hiring_stub.execute),
        ("val_voice", "validate_voice_transcript_schema", "validator", validate_hiring_stub.execute),
    ])

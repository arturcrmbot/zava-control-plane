# src/functions/graphs/_common.py
from __future__ import annotations
import os
import time
import httpx


D365_URL = os.getenv("D365_MCP_URL", "http://localhost:4102")


async def call_mcp(
    base_url: str,
    tool: str,
    args: dict,
    workflow_id: str | None = None,
    instance_id: str | None = None,
) -> dict:
    """POST to an MCP endpoint. Emits a durable `mcp.call` event with the
    request, response, status, and duration when `workflow_id` is provided
    so the UI's Execution Timeline can render per-call step cards.

    Governance — TASK-016 of plan/feature-agent-governance-toolkit-1.md:
    every tool call routes through ``GovernanceKernel.evaluate_tool_call``
    BEFORE the network hop. Phase 2 runs in log-only mode (a deny is
    recorded on the ``mcp.call`` event but the call still happens);
    Phase 6 (TASK-047) raises ``GovernanceDenied`` on a deny when
    ``AGT_ENFORCE=1``. The decision_id is propagated onto the event
    payload so the Execution Timeline + audit chain can correlate.
    """
    # Local import: keeps the kernel a soft dep at module-import time
    # so the Functions worker can be loaded for non-MCP graphs even if
    # the kernel is mid-rebuild. Real cost is one dict lookup per call.
    from api.server.services.governance import GovernanceDenied, kernel

    actor = os.environ.get("AGT_DEFAULT_ACTOR", "unknown-agent")
    decision = kernel().evaluate_tool_call(
        actor=actor,
        tool=tool,
        args=args,
        workflow_id=workflow_id,
    )
    # Phase 6 (TASK-047) wires the raise; Phase 2 just records the
    # decision and lets the caller see it on the timeline event.
    if decision.enforcement_mode == "enforce" and not decision.allowed:
        raise GovernanceDenied(decision)

    url = f"{base_url}/mcp/call/{tool}"
    t0 = time.time()
    resp_json: dict
    status_code: int
    async with httpx.AsyncClient() as c:
        try:
            r = await c.post(url, json=args, timeout=10)
            status_code = r.status_code
            resp_json = r.json() if r.is_success else {"error": r.text}
        except Exception as ex:
            resp_json = {"error": str(ex)}
            status_code = 599
    duration_ms = int((time.time() - t0) * 1000)

    if workflow_id is not None:
        # Local import avoids circular deps during module load.
        from api.functions.webhook import emit
        await emit(workflow_id, instance_id, "mcp.call", {
            "tool": tool, "url": url, "method": "POST",
            "request": args, "response": resp_json,
            "status_code": status_code, "duration_ms": duration_ms,
            # Governance attribution (Phase 2+). Surfaced by the
            # Execution Timeline; consumed by the audit chain in Phase 4.
            "governance": {
                "decision_id": decision.decision_id,
                "policy_version": decision.policy_version,
                "allowed": decision.allowed,
                "rule_id": decision.rule_id,
                "action": decision.action,
                "enforcement_mode": decision.enforcement_mode,
                "actor": actor,
            },
        })

    if status_code >= 400:
        raise RuntimeError(f"mcp {tool} failed: {status_code}")
    return resp_json

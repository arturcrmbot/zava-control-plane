# src/functions/graphs/executors/agents/_wrapper.py
"""
Helper for invoking a per-skill agent via the GHCP SDK natively.

Pattern (post-2026-04-28 retrofit):
1. Create an ephemeral CopilotSession with `skill_directories=[skills_dir]`
   and `tools=[Tool, ...]`. The SDK auto-discovers `*.skill.md` files and
   registers the tools natively. The model invokes the tools per the skill's
   `allowed-tools` frontmatter — *no* prompt-stuffing of tool results.
2. Subscribe `session.on(...)` -> OTEL bridge so tool calls appear as child spans.
3. Send the user prompt via `send_and_wait` (with optional `attachments` for
   multimodal). Return the parsed JSON object from the response text.
4. Emit a FleetEvent("agent.completed", ...) so the eval subscriber can score
   the invocation. Wrapped in try/except — eval pipeline failures must never
   propagate up into the caller.

Agent identity: every skill is its own agent. The runtime tags every span
with `gen_ai.agent.name = <skill_label>` (or the skill_dir name as fallback)
so the audit ledger and Foundry Tracing can attribute actions to a specific
agent rather than a single shared identity. This matches the per-skill
Ed25519 keypair design in `api.server.services.governance.identity`.
"""
from __future__ import annotations
import asyncio
import json
import os
import time
import uuid
from pathlib import Path

import httpx
from copilot.generated.session_events import SessionEventType
from copilot.tools import Tool
from opentelemetry import trace
from opentelemetry.trace import Status, StatusCode

from api.server.state import app_state
from api.shared.events import FleetEvent
from api.server.services.governance.permission_handler import AGTPermissionHandler
from api.functions.graphs.executors.agents.runtime import _get_runtime, LLMRuntimeResult


_SKILLS_DIR = Path(__file__).resolve().parents[4] / "server" / "skills"
SKILLS_DIR = _SKILLS_DIR
_tracer = trace.get_tracer("zava.agents.finance")
_MAX_RESPONSE_EVENT_BYTES = 4096


# Skill → dream-pass domain mapping. A skill belongs to at most one
# dream-pass domain; that domain is what /api/memory/lessons/active
# scopes against. Skills not in this dict get no lesson prepend.
# Hiring-tagged skills came from the legacy hiring track (no
# `hiring-` prefix). Future domain additions: vendor_kyc,
# expense_claim, contract_renewal — add their dream-passes/<domain>/
# SKILL.md first, then add entries here.
_SKILL_TO_DOMAIN: dict[str, str] = {
    "cv-crystalliser": "hiring",
    "auto-shortlister": "hiring",
    "interview-recommender": "hiring",
    "jd-drafter": "hiring",
    "voice-screener": "hiring",
    "betrvg-checker": "hiring",
    "sourcing-orchestrator": "hiring",
    "jurisdiction-router": "hiring",
}


# In-process lesson cache. {(domain): (fetched_at, [{id, body}, ...])}.
# 30s TTL so a workflow firing several agents in a row doesn't hammer
# the FastAPI memory route.
_LESSON_CACHE_TTL_S = 30.0
_lesson_cache: dict[str, tuple[float, list[dict]]] = {}


def _memory_recall_url() -> str:
    """POST /api/memory/v2/recall — semantic memory retrieval."""
    base = os.getenv("FASTAPI_WEBHOOK_URL", "http://localhost:3101/internal/durable-event")
    from urllib.parse import urlsplit, urlunsplit
    parts = urlsplit(base)
    return urlunsplit((parts.scheme, parts.netloc, "/api/memory/v2/recall", "", ""))


def _prepend_memories_to_skill_text(skill_text: str | None, memories: list[dict]) -> str | None:
    """Prepend relevant memories to the agent's system prompt."""
    if not memories or not skill_text:
        return skill_text
    header = "## Relevant memories from prior cases\n\n"
    lines = [f"- {m.get('memory', '')}" for m in memories if m.get("memory")]
    if not lines:
        return skill_text
    return header + "\n".join(lines) + "\n\n---\n\n" + skill_text


async def _fetch_memories(*, domain: str, query: str, top_k: int = 5) -> list[dict]:
    """Fetch semantically-relevant memories for this agent invocation.
    30s in-process cache keyed on (domain, query)."""
    now = time.monotonic()
    cache_key = f"{domain}::{query}"
    cached = _lesson_cache.get(cache_key)
    if cached is not None and now - cached[0] < _LESSON_CACHE_TTL_S:
        return cached[1]
    try:
        async with httpx.AsyncClient() as c:
            r = await c.post(
                _memory_recall_url(),
                json={"domain": domain, "query": query, "top_k": top_k},
                timeout=3.0,
            )
            if r.status_code != 200:
                _lesson_cache[cache_key] = (now, [])
                return []
            items = r.json().get("memories") or []
            _lesson_cache[cache_key] = (now, items)
            return items
    except Exception:
        _lesson_cache[cache_key] = (now, [])
        return []


def _skill_to_domain(skill_label: str | None, skill_dir_name: str | None) -> str | None:
    """Return the dream-pass domain for an agent skill, or None.
    Checks skill_label first, then skill_dir name.

    Any skill name containing the substring 'hiring' is treated as the
    hiring domain. This covers the segmented hiring agents
    (hiring-segment-a, hiring-segment-b, ...) plus the legacy
    non-prefixed entries listed in _SKILL_TO_DOMAIN. Generated-domain
    fleet-* skills don't have dream-pass SKILL.md files yet, so we
    return None for them until those exist."""
    for s in (skill_label, skill_dir_name):
        if not s:
            continue
        if s in _SKILL_TO_DOMAIN:
            return _SKILL_TO_DOMAIN[s]
        if "hiring" in s:
            return "hiring"
        if s.startswith("fleet-"):
            return None
    return None


def _load_skill(skill_dir: Path) -> str:
    return (skill_dir / "SKILL.md").read_text(encoding="utf-8")


def _make_session_otel_bridge(
    tool_calls_out: list[dict],
    *,
    workflow_id: str | None = None,
    skill_label: str | None = None,
) -> callable:
    """Build an OTEL bridge callable for GHCP session events.

    Returns the `on_event(event)` callable; the runtime is responsible for
    wiring it into `session.on(...)` and tearing it down. Collects completed
    tool calls into `tool_calls_out` for the eval payload and emits
    `tool.invoked` webhooks so the observatory orbit lights up MCP nodes
    in near-real time.

    TOOL_EXECUTION_START opens a span keyed by tool_call_id, and fires a
    `tool.invoked` (stage=start) webhook so the page can flare the
    skill->tool edge immediately.
    TOOL_EXECUTION_COMPLETE closes the span, appends to `tool_calls_out`,
    and fires a `tool.invoked` (stage=complete) webhook.
    """
    open_spans: dict[str, object] = {}
    open_meta: dict[str, dict] = {}
    parent_ctx = trace.set_span_in_context(trace.get_current_span())
    # Capture the running loop so the synchronous SDK callback can schedule
    # async emits without blocking.
    try:
        _loop = asyncio.get_running_loop()
    except RuntimeError:
        _loop = None

    def _fire_tool_webhook(stage: str, tool_name: str, *, latency_ms: int = 0) -> None:
        if _loop is None or workflow_id is None:
            return
        from api.functions.webhook import emit as _webhook_emit

        async def _send():
            await _webhook_emit(
                workflow_id, workflow_id, "tool.invoked",
                {
                    "tool": tool_name,
                    "skill": skill_label,
                    "stage": stage,
                    "duration_ms": latency_ms,
                },
            )
        try:
            _loop.call_soon_threadsafe(
                lambda: _loop.create_task(_send()),
            )
        except Exception:
            pass

    def on_event(event) -> None:
        try:
            if event.type == SessionEventType.TOOL_EXECUTION_START:
                data = event.data
                name = getattr(data, "tool_name", "unknown")
                call_id = getattr(data, "tool_call_id", None)
                args = getattr(data, "tool_args", None) or getattr(data, "arguments", None) or ""
                if not isinstance(args, str):
                    try:
                        args = json.dumps(args)
                    except Exception:
                        args = str(args)
                span = _tracer.start_span(f"tool.{name}", context=parent_ctx)
                span.set_attribute("zava.tool.name", str(name))
                if call_id:
                    span.set_attribute("zava.tool.call_id", str(call_id))
                    open_spans[call_id] = span
                    open_meta[call_id] = {
                        "name": str(name), "args": args, "started_at": time.monotonic(),
                    }
                # Fire an observatory webhook so the page lights up the
                # skill -> tool edge in near-real-time.
                _fire_tool_webhook("start", str(name))
            elif event.type == SessionEventType.TOOL_EXECUTION_COMPLETE:
                data = event.data
                call_id = getattr(data, "tool_call_id", None)
                span = open_spans.pop(call_id, None) if call_id else None
                meta = open_meta.pop(call_id, None) if call_id else None
                if span is not None:
                    success = getattr(data, "success", None)
                    if success is False:
                        span.set_status(Status(StatusCode.ERROR, "tool reported failure"))
                    span.end()
                if meta is not None:
                    result_text = getattr(data, "result", None) or getattr(data, "output", None) or ""
                    if not isinstance(result_text, str):
                        try:
                            result_text = json.dumps(result_text)
                        except Exception:
                            result_text = str(result_text)
                    latency_ms = int((time.monotonic() - meta["started_at"]) * 1000)
                    tool_calls_out.append({
                        "name": meta["name"],
                        "tool": meta["name"],   # working_memory_capture reads this key; keep "name" for legacy readers.
                        "args": meta["args"],
                        "result": result_text,
                        "success": getattr(data, "success", True) is not False,
                        "latency_ms": latency_ms,
                    })
                    _fire_tool_webhook("complete", meta["name"], latency_ms=latency_ms)
        except Exception:
            pass

    return on_event


def _extract_json(text: str) -> dict:
    obj_start = text.find("{")
    obj_end = text.rfind("}")
    arr_start = text.find("[")
    arr_end = text.rfind("]")

    if obj_start >= 0 and obj_end > obj_start:
        try:
            return json.loads(text[obj_start:obj_end + 1])
        except json.JSONDecodeError:
            pass
    if arr_start >= 0 and arr_end > arr_start:
        try:
            result = json.loads(text[arr_start:arr_end + 1])
            return {"items": result} if isinstance(result, list) else result
        except json.JSONDecodeError:
            pass
    return {"raw": text, "parse_error": True}


async def run_agent_session(
    prompt: str,
    *,
    tools: list[Tool] | None = None,
    skill_dir: Path | None = None,
    skill_directories: list[Path] | None = None,
    skill_label: str | None = None,
    model: str = "gpt-4.1",
    attachments: list[dict] | None = None,
    workflow_id: str | None = None,
) -> dict:
    """Run an ephemeral per-skill agent session and return the parsed JSON response.

    Args:
        prompt: The user prompt — per-call context.
        tools: SDK-native tools registered on the session via `tools=[...]`.
        skill_dir: Path to the skill's directory (containing SKILL.md).
        skill_label: Optional OTEL span tag. Also drives evaluator selection
            in the online subscriber.
        model: Model id (default `gpt-4.1`).
        attachments: Optional multimodal attachments for `send_and_wait`.
        workflow_id: Durable Functions instance_id, plumbed through from the
            executor's input dict, so eval rows can be joined to the workflow
            on the control plane.
    """
    tools = tools or []
    skill_text = _load_skill(skill_dir) if skill_dir else None
    # Phase B: pull active lessons for this skill's domain and prepend them
    # to the system message so the agent benefits from past learning.
    domain = _skill_to_domain(skill_label, skill_dir.name if skill_dir else None)
    if domain:
        query_seed = f"skill={skill_label or '?'} domain={domain} prompt={(prompt or '')[:240]}"
        memories = await _fetch_memories(domain=domain, query=query_seed, top_k=5)
    else:
        memories = []
    skill_text = _prepend_memories_to_skill_text(skill_text, memories)
    used_lesson_ids = [
        (str(m.get("id")), str(m.get("memory") or "")[:80])
        for m in memories
        if m.get("id") and m.get("memory")
    ]
    # SDK skill auto-discovery uses the union of skill_dir (primary,
    # drives SKILL.md system-message loading + span tagging) and any
    # extra skill_directories the caller passes. Dedup preserves order
    # with the primary first.
    all_skill_dirs: list[Path] = []
    if skill_dir:
        all_skill_dirs.append(skill_dir)
    if skill_directories:
        for d in skill_directories:
            if d not in all_skill_dirs:
                all_skill_dirs.append(d)
    # Each skill is its own agent. Prefer the explicit skill_label; fall
    # back to the skill_dir name; only use the legacy shared id when
    # neither is available (e.g. test harness without a skill).
    agent_name = skill_label or (skill_dir.name if skill_dir else "finance-agent")
    tool_calls_collected: list[dict] = []
    started_at = time.monotonic()
    in_tok = out_tok = None

    with _tracer.start_as_current_span("gen_ai.generate_content") as span:
        span.set_attribute("gen_ai.system", "github_copilot")
        span.set_attribute("gen_ai.request.model", model)
        span.set_attribute("gen_ai.agent.name", agent_name)
        if skill_label:
            span.set_attribute("zava.skill", skill_label)
        # 2026-05-05: workflow_id stamped so Foundry Tracing can filter
        # spans by workflow. Span attribute → App Insights customDimensions.
        if workflow_id:
            span.set_attribute("workflow.id", workflow_id)
            span.set_attribute("zava.workflow.id", workflow_id)
        span.set_attribute("zava.tools.count", len(tools))
        if attachments:
            span.set_attribute("gen_ai.attachments.count", len(attachments))

        # AGT pre-tool hook: per-skill capability gate via governance
        # kernel when AGT_ENFORCE=1; rubber-stamp otherwise so dev
        # behaviour is unchanged. See plan/refactor-substrate-
        # agentic-segments-1.md TASK-002.
        if os.environ.get("AGT_ENFORCE", "0").strip() in ("1", "true", "TRUE", "yes"):
            permission_handler = AGTPermissionHandler(
                skill_label=agent_name,
                workflow_id=workflow_id,
            )
        else:
            permission_handler = None  # GHCPRuntime falls back to approve_all

        on_event = _make_session_otel_bridge(
            tool_calls_collected,
            workflow_id=workflow_id,
            skill_label=skill_label,
        )

        runtime = _get_runtime()
        result: LLMRuntimeResult = await runtime.run_session(
            prompt=prompt,
            system_message=skill_text,
            skill_directories=all_skill_dirs or None,
            tools=tools,
            permission_handler=permission_handler,
            attachments=attachments,
            model=model,
            timeout_s=240.0,
            event_subscriber=on_event,
        )

        text = result.text
        in_tok = result.input_tokens
        out_tok = result.output_tokens

        event_text = text[:_MAX_RESPONSE_EVENT_BYTES]
        span.add_event("gen_ai.response", {"gen_ai.response.text": event_text})

        if in_tok is not None:
            span.set_attribute("gen_ai.usage.input_tokens", int(in_tok))
        if out_tok is not None:
            span.set_attribute("gen_ai.usage.output_tokens", int(out_tok))

    # Note: the OTEL span above is recorded in this (Functions host) process.
    # The FastAPI process — which serves /api/fleet/economics — receives the
    # token usage via the `agent.completed` webhook below and persists its own
    # gen_ai.generate_content span there. Don't `app_state.store.append_span`
    # here: it would write to the wrong process's store.
    elapsed_s = time.monotonic() - started_at
    parsed = _extract_json(text)
    elapsed_ms = int(elapsed_s * 1000)

    # Surface collected tool calls on a leading-underscore key so
    # downstream segments (e.g. Segment F's idempotent-only retry
    # gate) can inspect them without spawning a span query. Only
    # added when the parsed payload is a dict AND at least one tool
    # call was collected, keeping the return shape backwards-
    # compatible for non-tool-using callers (Segments B/D/E).
    if isinstance(parsed, dict) and tool_calls_collected:
        parsed["_raw_tool_calls"] = tool_calls_collected

    try:
        from api.server.eval.evaluator_set import extract_context
        context = extract_context(skill_label or "", tool_calls_collected)
    except Exception:
        context = ""

    # Cross-process emit: agent executors normally run in the Azure Functions
    # host process, while the online_subscriber lives in the FastAPI process.
    # Sending via the existing webhook bridge ensures the subscriber sees it.
    # `webhook.emit` is best-effort and swallows errors.
    #
    # Stamp realistic input-side context for the FastAPI-side token estimator:
    # - skill_chars: the SKILL.md system message (often 2-5k chars)
    # - attachment_count: each inline image counts ~1.1k input tokens for
    #   gpt-4.1 vision (low-detail). Without this, estimated_from_chars
    #   underreports multimodal calls by 10x.
    payload = {
        "agent_label": skill_label or "unknown",
        "agent_run_id": f"ar-{uuid.uuid4().hex[:8]}",
        "prompt": prompt,
        "response_text": text,
        "extracted_json": parsed,
        "tool_calls": tool_calls_collected,
        "context": context,
        "model": model,
        "skill_chars": len(skill_text) if skill_text else 0,
        "attachment_count": len(attachments) if attachments else 0,
        "used_lesson_ids": used_lesson_ids,
        "usage": {
            "input_tokens": int(in_tok) if in_tok is not None else None,
            "output_tokens": int(out_tok) if out_tok is not None else None,
        },
        "latency_ms": elapsed_ms,
    }
    try:
        from api.functions.webhook import emit as _webhook_emit
        await _webhook_emit(workflow_id or "?", workflow_id, "agent.completed", payload)
    except Exception:
        pass

    return parsed


# Backwards-compatible alias for legacy agents that pass a skill_name string.
async def run_agent_skill(
    skill_name: str,
    prompt: str,
    model: str = "gpt-4.1",
    attachments: list[dict] | None = None,
    workflow_id: str | None = None,
) -> dict:
    """Deprecated alias — prefer `run_agent_session(skill_dir=..., tools=[...])`."""
    candidate = _SKILLS_DIR / skill_name
    if not candidate.is_dir():
        candidate = _SKILLS_DIR / skill_name.replace("_", "-")
    return await run_agent_session(
        prompt=prompt,
        skill_dir=candidate if candidate.is_dir() else None,
        skill_label=skill_name,
        model=model,
        attachments=attachments,
        workflow_id=workflow_id,
    )

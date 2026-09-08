"""Azure OpenAI implementation of LLMRuntime — with native tool-calling.

Selected via ``LLM_RUNTIME=aoai`` (or the legacy alias ``azure``).

This is the cloud-deploy path used when the container runs in Azure
Container Apps with a managed identity that has ``Cognitive Services
OpenAI User`` on the AOAI account. It calls the AOAI chat completions
endpoint directly with the standard ``tools`` / ``tool_calls`` loop.

Skill directories are accepted for signature compatibility; the wrapper
already loads SKILL.md text into ``system_message`` before calling here.

Required env:
    AZURE_OPENAI_ENDPOINT       e.g. https://my-aoai.cognitiveservices.azure.com/
    AZURE_OPENAI_DEPLOYMENT     chat deployment name (e.g. ``gpt-4``)

Optional env:
    AZURE_OPENAI_API_VERSION    defaults to ``2024-10-21``
    AZURE_CLIENT_ID             when set, the UAMI client id is forwarded
                                to DefaultAzureCredential so the managed
                                identity is picked up unambiguously.
"""
from __future__ import annotations

import asyncio
import inspect
import json
import logging
import os
import random
import time
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Callable

from copilot.generated.session_events import SessionEventType
from copilot.session import PermissionRequest
from copilot.tools import Tool, ToolInvocation, ToolResult

from api.functions.graphs.executors.agents.runtime import LLMRuntimeResult, validate_required_tool_names

log = logging.getLogger(__name__)

_DEFAULT_API_VERSION = "2024-10-21"

# Retry budget for transient 429 (rate-limit) / 500-class errors. The AOAI
# deployment in zava-verify runs with a low per-minute quota (40 RPM / 40K
# TPM) and the simulator can burst above that. Without retry the orchestrator
# bails on the first 429 and the workflow is stuck in Intake forever.
_RETRY_MAX_ATTEMPTS = 6
_RETRY_BASE_DELAY_S = 2.0
_RETRY_MAX_DELAY_S = 30.0

# Bounded agent tool loop — prevents infinite loops if the model keeps
# requesting tool calls without ever producing a final text answer.
_MAX_TOOL_TURNS = 8


def _build_client() -> Any:
    """Construct an ``openai.AzureOpenAI`` client using managed identity."""
    from azure.identity import DefaultAzureCredential, get_bearer_token_provider
    from openai import AzureOpenAI

    endpoint = os.environ.get("AZURE_OPENAI_ENDPOINT")
    if not endpoint:
        raise RuntimeError(
            "AZURE_OPENAI_ENDPOINT is required for LLM_RUNTIME=aoai"
        )

    credential = DefaultAzureCredential(
        managed_identity_client_id=os.environ.get("AZURE_CLIENT_ID") or None,
    )
    token_provider = get_bearer_token_provider(
        credential, "https://cognitiveservices.azure.com/.default"
    )
    return AzureOpenAI(
        azure_endpoint=endpoint,
        azure_ad_token_provider=token_provider,
        api_version=os.environ.get("AZURE_OPENAI_API_VERSION", _DEFAULT_API_VERSION),
    )


def _tools_to_openai_schema(tools: list[Tool]) -> list[dict]:
    """Convert copilot SDK Tool objects to Azure OpenAI function tool dicts."""
    seen: set[str] = set()
    out: list[dict] = []
    for t in tools:
        if t.name in seen:
            raise ValueError(
                f"Duplicate tool name {t.name!r}; each registered tool must "
                f"have a unique name."
            )
        seen.add(t.name)
        out.append({
            "type": "function",
            "function": {
                "name": t.name,
                "description": t.description or "",
                "parameters": t.parameters or {"type": "object", "properties": {}},
            },
        })
    return out


class AOAIRuntime:
    """Azure OpenAI chat-completions runtime with native tool-calling.

    Converts registered ``copilot.tools.Tool`` objects into OpenAI function
    tools, implements the bounded agent tool loop (send ``tools``, inspect
    ``tool_calls``, execute, append messages, repeat), emits canonical
    session events, and aggregates token usage across turns.
    """

    def __init__(self) -> None:
        self._client: Any | None = None
        self._deployment = os.environ.get("AZURE_OPENAI_DEPLOYMENT") or "gpt-4"

    def _client_lazy(self) -> Any:
        if self._client is None:
            self._client = _build_client()
        return self._client

    # ------------------------------------------------------------------
    # Retry wrapper (unchanged from original)
    # ------------------------------------------------------------------
    def _call_with_retry(self, call_fn: Callable[[], Any]) -> Any:
        from openai import APIStatusError, RateLimitError

        attempt = 0
        while True:
            attempt += 1
            try:
                return call_fn()
            except (RateLimitError, APIStatusError) as exc:
                status = getattr(exc, "status_code", None)
                is_retryable = isinstance(exc, RateLimitError) or (
                    status is not None and status >= 500
                )
                if not is_retryable or attempt >= _RETRY_MAX_ATTEMPTS:
                    raise
                retry_after = None
                resp = getattr(exc, "response", None)
                if resp is not None:
                    try:
                        retry_after = float(resp.headers.get("retry-after", "") or 0)
                    except (ValueError, AttributeError):
                        retry_after = None
                if retry_after and retry_after > 0:
                    delay = min(retry_after, _RETRY_MAX_DELAY_S)
                else:
                    delay = min(
                        _RETRY_BASE_DELAY_S * (2 ** (attempt - 1)),
                        _RETRY_MAX_DELAY_S,
                    )
                delay += random.uniform(0, 0.5)
                time.sleep(delay)

    # ------------------------------------------------------------------
    # Main entry point
    # ------------------------------------------------------------------
    async def run_session(
        self,
        *,
        prompt: str,
        system_message: str | None = None,
        skill_directories: list[Path] | None = None,  # noqa: ARG002
        tools: list | None = None,
        required_tool_names: list[str] | None = None,
        permission_handler: Callable | None = None,
        attachments: list[dict] | None = None,
        model: str = "gpt-4.1",  # noqa: ARG002 — deployment from env
        timeout_s: float = 240.0,
        event_subscriber: Callable[[Any], None] | None = None,
    ) -> LLMRuntimeResult:
        # Fail on unsupported attachments
        if attachments:
            raise NotImplementedError(
                "Attachments are not supported by the AOAI runtime. "
                "Use GHCPRuntime for multimodal sessions."
            )

        tools_list: list[Tool] = tools or []
        tool_map: dict[str, Tool] = {}
        openai_tools: list[dict] | None = None
        if tools_list:
            openai_tools = _tools_to_openai_schema(tools_list)
            tool_map = {t.name: t for t in tools_list}
        required_names = validate_required_tool_names(required_tool_names, tool_map)

        # Build initial messages
        messages: list[dict[str, Any]] = []
        if system_message:
            messages.append({"role": "system", "content": system_message})
        messages.append({"role": "user", "content": prompt})

        total_in_tok = 0
        total_out_tok = 0
        canonical_calls: list[dict] = []

        for turn in range(_MAX_TOOL_TURNS + 1):
            successful_tools = {
                call["name"]
                for call in canonical_calls
                if call.get("success") is True
            }
            missing_required = [
                name for name in required_names if name not in successful_tools
            ]
            tool_choice: str | dict[str, Any] | None = None
            if required_names:
                tool_choice = (
                    {
                        "type": "function",
                        "function": {"name": missing_required[0]},
                    }
                    if missing_required
                    else "none"
                )

            # -- API call via thread (sync SDK) with retry --
            def _call(
                msgs=messages,
                ot=openai_tools,
                ts=timeout_s,
                tc=tool_choice,
            ) -> Any:
                client = self._client_lazy()
                kwargs: dict[str, Any] = {
                    "model": self._deployment,
                    "messages": msgs,
                    "timeout": ts,
                }
                if ot:
                    kwargs["tools"] = ot
                    kwargs["temperature"] = 0
                if tc is not None:
                    kwargs["tool_choice"] = tc
                return client.chat.completions.create(**kwargs)

            response = await asyncio.to_thread(self._call_with_retry, _call)

            # -- Accumulate tokens --
            usage = getattr(response, "usage", None)
            if usage is not None:
                total_in_tok += getattr(usage, "prompt_tokens", 0) or 0
                total_out_tok += getattr(usage, "completion_tokens", 0) or 0

            # -- Parse response --
            try:
                msg = response.choices[0].message
            except (AttributeError, IndexError):
                raise RuntimeError("Malformed response from Azure OpenAI: no choices")

            response_tool_calls = getattr(msg, "tool_calls", None)

            # Final text answer — no tool calls
            if not response_tool_calls:
                if missing_required:
                    raise RuntimeError(
                        "Azure OpenAI returned a final response before required "
                        f"tools succeeded: {missing_required}"
                    )
                text = getattr(msg, "content", None) or ""
                return LLMRuntimeResult(
                    text=text,
                    tool_calls=[] if event_subscriber else canonical_calls,
                    input_tokens=total_in_tok or None,
                    output_tokens=total_out_tok or None,
                    raw_event=None,
                )

            # -- Tool-call turn --
            if turn >= _MAX_TOOL_TURNS:
                raise RuntimeError(
                    f"Max tool turns ({_MAX_TOOL_TURNS}) exhausted; model "
                    f"keeps requesting tool calls without a final answer."
                )

            # Append the assistant message with its tool_calls
            assistant_msg: dict[str, Any] = {
                "role": "assistant",
                "content": getattr(msg, "content", None),
                "tool_calls": [
                    {
                        "id": tc.id,
                        "type": "function",
                        "function": {
                            "name": tc.function.name,
                            "arguments": tc.function.arguments,
                        },
                    }
                    for tc in response_tool_calls
                ],
            }
            messages.append(assistant_msg)

            # Process each tool call
            for tc in response_tool_calls:
                call_id = tc.id
                fn_name = tc.function.name
                raw_args = tc.function.arguments
                started_at = time.monotonic()

                # Emit TOOL_EXECUTION_START
                if event_subscriber:
                    event_subscriber(SimpleNamespace(
                        type=SessionEventType.TOOL_EXECUTION_START,
                        data=SimpleNamespace(
                            tool_name=fn_name,
                            tool_call_id=call_id,
                            arguments=raw_args,
                        ),
                    ))

                # Parse arguments
                try:
                    args = json.loads(raw_args) if raw_args else {}
                    if not isinstance(args, dict):
                        raise ValueError("arguments must be a JSON object")
                except (json.JSONDecodeError, ValueError) as e:
                    content = f"ERROR: malformed arguments — {e}"
                    messages.append({"role": "tool", "tool_call_id": call_id, "content": content})
                    latency_ms = int((time.monotonic() - started_at) * 1000)
                    _emit_complete(event_subscriber, call_id, fn_name, content, False, str(e), canonical_calls, raw_args, latency_ms)
                    continue

                # Unknown tool
                if fn_name not in tool_map:
                    content = f"ERROR: unknown tool {fn_name!r}"
                    messages.append({"role": "tool", "tool_call_id": call_id, "content": content})
                    latency_ms = int((time.monotonic() - started_at) * 1000)
                    _emit_complete(event_subscriber, call_id, fn_name, content, False, content, canonical_calls, json.dumps(args), latency_ms)
                    continue

                # Permission check
                if permission_handler:
                    perm_req = PermissionRequest(
                        kind="custom-tool",
                        tool_name=fn_name,
                        args=args,
                        tool_call_id=call_id,
                    )
                    perm_result = permission_handler(
                        perm_req,
                        {
                            "session_id": "aoai",
                            "tool_call_id": call_id,
                            "tool_name": fn_name,
                        },
                    )
                    if inspect.isawaitable(perm_result):
                        perm_result = await perm_result
                    if getattr(perm_result, "kind", None) != "approved":
                        content = f"ERROR: tool {fn_name!r} denied by permission handler"
                        messages.append({"role": "tool", "tool_call_id": call_id, "content": content})
                        latency_ms = int((time.monotonic() - started_at) * 1000)
                        _emit_complete(event_subscriber, call_id, fn_name, content, False, "denied", canonical_calls, json.dumps(args), latency_ms)
                        continue

                # Execute handler
                try:
                    invocation = ToolInvocation(
                        session_id="aoai",
                        tool_call_id=call_id,
                        tool_name=fn_name,
                        arguments=args,
                    )
                    result = tool_map[fn_name].handler(invocation)
                    if inspect.isawaitable(result):
                        result = await result
                    success = result.result_type == "success"
                    error = result.error
                    content = result.text_result_for_llm or ""
                    if not success:
                        content = f"ERROR: {error or 'tool failed'}"
                except Exception as exc:
                    success = False
                    error = str(exc)
                    content = f"ERROR: handler raised — {exc}"

                messages.append({"role": "tool", "tool_call_id": call_id, "content": content})
                latency_ms = int((time.monotonic() - started_at) * 1000)
                _emit_complete(event_subscriber, call_id, fn_name, content, success, error, canonical_calls, json.dumps(args), latency_ms)

        # Should not reach here, but guard
        raise RuntimeError(
            f"Max tool turns ({_MAX_TOOL_TURNS}) exhausted; model "
            f"keeps requesting tool calls without a final answer."
        )


def _emit_complete(
    event_subscriber: Callable | None,
    call_id: str,
    name: str,
    result: str,
    success: bool,
    error: str | None,
    canonical_calls: list[dict],
    args_str: str,
    latency_ms: int,
) -> None:
    """Emit TOOL_EXECUTION_COMPLETE event and append to canonical list."""
    if event_subscriber:
        event_subscriber(SimpleNamespace(
            type=SessionEventType.TOOL_EXECUTION_COMPLETE,
            data=SimpleNamespace(
                tool_call_id=call_id,
                tool_name=name,
                result=result,
                success=success,
                error=error,
            ),
        ))
    canonical_calls.append({
        "tool_call_id": call_id,
        "name": name,
        "tool": name,
        "args": args_str,
        "result": result,
        "success": success,
        "latency_ms": latency_ms,
    })

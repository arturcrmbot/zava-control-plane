"""Tests for AOAIRuntime tool-calling support.

Uses fake Azure OpenAI response objects — no network calls.
"""
from __future__ import annotations

import asyncio
import json
import time
from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from copilot.generated.session_events import SessionEventType
from copilot.tools import Tool, ToolInvocation, ToolResult

from api.functions.graphs.executors.agents.runtime_aoai import AOAIRuntime


# ---------------------------------------------------------------------------
# Helpers — fake Azure OpenAI response objects
# ---------------------------------------------------------------------------

def _usage(prompt_tokens: int = 10, completion_tokens: int = 5):
    return SimpleNamespace(prompt_tokens=prompt_tokens, completion_tokens=completion_tokens)


def _text_response(content: str, usage=None):
    """Single text response, no tool_calls."""
    msg = SimpleNamespace(content=content, tool_calls=None)
    return SimpleNamespace(
        choices=[SimpleNamespace(message=msg, finish_reason="stop")],
        usage=usage or _usage(),
    )


def _tool_call(call_id: str, name: str, arguments: str):
    fn = SimpleNamespace(name=name, arguments=arguments)
    return SimpleNamespace(id=call_id, type="function", function=fn)


def _tool_response(tool_calls: list, usage=None):
    """Response requesting tool calls."""
    msg = SimpleNamespace(content=None, tool_calls=tool_calls)
    return SimpleNamespace(
        choices=[SimpleNamespace(message=msg, finish_reason="tool_calls")],
        usage=usage or _usage(),
    )


def _make_tool(name: str, description: str = "d", params: dict | None = None, handler=None):
    async def _default_handler(inv: ToolInvocation) -> ToolResult:
        return ToolResult(text_result_for_llm="ok")
    return Tool(
        name=name,
        description=description,
        handler=handler or _default_handler,
        parameters=params or {"type": "object", "properties": {}},
    )


def _runtime_with_responses(*responses) -> AOAIRuntime:
    """Create an AOAIRuntime with a fake client returning canned responses."""
    client = MagicMock()
    it = iter(responses)
    client.chat.completions.create = MagicMock(side_effect=lambda **kw: next(it))
    rt = AOAIRuntime()
    rt._client = client
    return rt


# ---------------------------------------------------------------------------
# 1. Legacy no-tool text-only (existing behavior preserved)
# ---------------------------------------------------------------------------

class TestNoToolLegacy:
    @pytest.mark.asyncio
    async def test_text_only_response(self):
        rt = _runtime_with_responses(_text_response("hello world"))
        result = await rt.run_session(prompt="hi", system_message="be helpful")
        assert result.text == "hello world"
        assert result.tool_calls == []
        assert result.input_tokens == 10
        assert result.output_tokens == 5


# ---------------------------------------------------------------------------
# 2. Function schema conversion
# ---------------------------------------------------------------------------

class TestFunctionSchema:
    @pytest.mark.asyncio
    async def test_tools_converted_to_openai_functions(self):
        rt = _runtime_with_responses(_text_response("done"))
        tool = _make_tool("my_tool", "desc", {"type": "object", "properties": {"x": {"type": "string"}}})
        await rt.run_session(prompt="go", tools=[tool])
        call_kw = rt._client.chat.completions.create.call_args
        tools_param = call_kw.kwargs.get("tools") or call_kw[1].get("tools")
        assert tools_param is not None
        assert len(tools_param) == 1
        fn = tools_param[0]
        assert fn["type"] == "function"
        assert fn["function"]["name"] == "my_tool"
        assert fn["function"]["description"] == "desc"
        assert fn["function"]["parameters"]["properties"]["x"]["type"] == "string"

    @pytest.mark.asyncio
    async def test_tool_sessions_use_deterministic_sampling(self):
        rt = _runtime_with_responses(_text_response("done"))
        tool = _make_tool("lookup")

        await rt.run_session(prompt="go", tools=[tool])

        assert rt._client.chat.completions.create.call_args.kwargs["temperature"] == 0


# ---------------------------------------------------------------------------
# 3. Single tool call -> final answer
# ---------------------------------------------------------------------------

class TestSingleToolCall:
    @pytest.mark.asyncio
    async def test_tool_call_then_final_answer(self):
        responses = [
            _tool_response([_tool_call("c1", "lookup", '{"q": "test"}')]),
            _text_response("result is 42"),
        ]
        tool = _make_tool("lookup")
        rt = _runtime_with_responses(*responses)
        result = await rt.run_session(prompt="find it", tools=[tool])
        assert result.text == "result is 42"
        # Two calls to completions.create
        assert rt._client.chat.completions.create.call_count == 2


# ---------------------------------------------------------------------------
# 4. Multiple tool calls in one response
# ---------------------------------------------------------------------------

class TestMultipleToolCalls:
    @pytest.mark.asyncio
    async def test_multiple_tool_calls_in_single_response(self):
        responses = [
            _tool_response([
                _tool_call("c1", "tool_a", '{}'),
                _tool_call("c2", "tool_b", '{}'),
            ]),
            _text_response("combined"),
        ]
        tool_a = _make_tool("tool_a")
        tool_b = _make_tool("tool_b")
        rt = _runtime_with_responses(*responses)
        result = await rt.run_session(prompt="do both", tools=[tool_a, tool_b])
        assert result.text == "combined"

    @pytest.mark.asyncio
    async def test_required_tools_are_forced_in_order_then_text_is_forced(self):
        responses = [
            _tool_response([_tool_call("c1", "tool_a", "{}")]),
            _tool_response([_tool_call("c2", "tool_b", "{}")]),
            _text_response("combined"),
        ]
        rt = _runtime_with_responses(*responses)

        result = await rt.run_session(
            prompt="do both",
            tools=[_make_tool("tool_a"), _make_tool("tool_b")],
            required_tool_names=["tool_a", "tool_b"],
        )

        calls = rt._client.chat.completions.create.call_args_list
        assert calls[0].kwargs["tool_choice"]["function"]["name"] == "tool_a"
        assert calls[1].kwargs["tool_choice"]["function"]["name"] == "tool_b"
        assert calls[2].kwargs["tool_choice"] == "none"
        assert result.text == "combined"


# ---------------------------------------------------------------------------
# 5. Handler receives ToolInvocation with correct fields
# ---------------------------------------------------------------------------

class TestHandlerReceivesToolInvocation:
    @pytest.mark.asyncio
    async def test_handler_gets_correct_invocation(self):
        captured = []

        async def handler(inv: ToolInvocation) -> ToolResult:
            captured.append(inv)
            return ToolResult(text_result_for_llm="ok")

        tool = _make_tool("my_fn", handler=handler)
        responses = [
            _tool_response([_tool_call("c1", "my_fn", '{"a": 1}')]),
            _text_response("done"),
        ]
        rt = _runtime_with_responses(*responses)
        await rt.run_session(prompt="go", tools=[tool])
        assert len(captured) == 1
        inv = captured[0]
        assert inv.tool_name == "my_fn"
        assert inv.tool_call_id == "c1"
        assert inv.arguments == {"a": 1}
        assert inv.session_id == "aoai"


# ---------------------------------------------------------------------------
# 6. Assistant + tool messages fed back to model
# ---------------------------------------------------------------------------

class TestMessagesFedBack:
    @pytest.mark.asyncio
    async def test_messages_contain_assistant_and_tool_roles(self):
        responses = [
            _tool_response([_tool_call("c1", "t", '{}')]),
            _text_response("done"),
        ]
        tool = _make_tool("t")
        rt = _runtime_with_responses(*responses)
        await rt.run_session(prompt="go", tools=[tool])
        # Second call should contain assistant + tool messages
        second_call_kw = rt._client.chat.completions.create.call_args_list[1]
        msgs = second_call_kw.kwargs.get("messages") or second_call_kw[1].get("messages")
        roles = [m["role"] for m in msgs]
        assert "assistant" in roles
        assert "tool" in roles


# ---------------------------------------------------------------------------
# 7. Permission approved and denied
# ---------------------------------------------------------------------------

class TestPermission:
    @pytest.mark.asyncio
    async def test_permission_handler_receives_sdk_two_argument_shape(self):
        captured = []

        def approve(req, invocation):
            captured.append((req, invocation))
            return SimpleNamespace(kind="approved")

        tool = _make_tool("t")
        responses = [
            _tool_response([_tool_call("c1", "t", '{"value": 1}')]),
            _text_response("done"),
        ]
        rt = _runtime_with_responses(*responses)

        await rt.run_session(prompt="go", tools=[tool], permission_handler=approve)

        assert len(captured) == 1
        request, invocation = captured[0]
        assert request.tool_name == "t"
        assert request.tool_call_id == "c1"
        assert request.args == {"value": 1}
        assert invocation == {
            "session_id": "aoai",
            "tool_call_id": "c1",
            "tool_name": "t",
        }

    @pytest.mark.asyncio
    async def test_permission_approved_executes_tool(self):
        async def approve(req, ctx=None):
            return SimpleNamespace(kind="approved")

        tool = _make_tool("t")
        responses = [
            _tool_response([_tool_call("c1", "t", '{}')]),
            _text_response("done"),
        ]
        rt = _runtime_with_responses(*responses)
        result = await rt.run_session(prompt="go", tools=[tool], permission_handler=approve)
        assert result.text == "done"

    @pytest.mark.asyncio
    async def test_permission_denied_returns_failed_tool_message(self):
        async def deny(req, ctx=None):
            return SimpleNamespace(kind="denied")

        executed = []

        async def handler(inv):
            executed.append(inv)
            return ToolResult(text_result_for_llm="ok")

        tool = _make_tool("t", handler=handler)
        responses = [
            _tool_response([_tool_call("c1", "t", '{}')]),
            _text_response("denied path"),
        ]
        rt = _runtime_with_responses(*responses)
        await rt.run_session(prompt="go", tools=[tool], permission_handler=deny)
        # Handler was never called
        assert len(executed) == 0


# ---------------------------------------------------------------------------
# 8. Malformed arguments
# ---------------------------------------------------------------------------

class TestMalformedArgs:
    @pytest.mark.asyncio
    async def test_malformed_json_args_returns_error_to_model(self):
        executed = []

        async def handler(inv):
            executed.append(inv)
            return ToolResult(text_result_for_llm="ok")

        tool = _make_tool("t", handler=handler)
        responses = [
            _tool_response([_tool_call("c1", "t", "not valid json{{{")]),
            _text_response("recovered"),
        ]
        rt = _runtime_with_responses(*responses)
        result = await rt.run_session(prompt="go", tools=[tool])
        assert result.text == "recovered"
        assert len(executed) == 0  # handler never called


# ---------------------------------------------------------------------------
# 9. Unknown tool
# ---------------------------------------------------------------------------

class TestUnknownTool:
    @pytest.mark.asyncio
    async def test_unknown_tool_returns_error_to_model(self):
        tool = _make_tool("known")
        responses = [
            _tool_response([_tool_call("c1", "unknown_fn", '{}')]),
            _text_response("ok"),
        ]
        rt = _runtime_with_responses(*responses)
        result = await rt.run_session(prompt="go", tools=[tool])
        assert result.text == "ok"


# ---------------------------------------------------------------------------
# 10. ToolResult failure
# ---------------------------------------------------------------------------

class TestToolResultFailure:
    @pytest.mark.asyncio
    async def test_handler_returns_failure(self):
        async def handler(inv):
            return ToolResult(text_result_for_llm="", result_type="failure", error="boom")

        tool = _make_tool("t", handler=handler)
        responses = [
            _tool_response([_tool_call("c1", "t", '{}')]),
            _text_response("handled failure"),
        ]
        rt = _runtime_with_responses(*responses)
        result = await rt.run_session(prompt="go", tools=[tool])
        assert result.text == "handled failure"


# ---------------------------------------------------------------------------
# 11. Event subscriber — TOOL_EXECUTION_START / COMPLETE
# ---------------------------------------------------------------------------

class TestEventSubscriber:
    @pytest.mark.asyncio
    async def test_events_emitted_for_tool_calls(self):
        events = []

        def subscriber(event):
            events.append(event)

        tool = _make_tool("my_fn")
        responses = [
            _tool_response([_tool_call("c1", "my_fn", '{"x": 1}')]),
            _text_response("done"),
        ]
        rt = _runtime_with_responses(*responses)
        await rt.run_session(prompt="go", tools=[tool], event_subscriber=subscriber)
        types = [e.type for e in events]
        assert SessionEventType.TOOL_EXECUTION_START in types
        assert SessionEventType.TOOL_EXECUTION_COMPLETE in types
        # START event data
        start_evt = next(e for e in events if e.type == SessionEventType.TOOL_EXECUTION_START)
        assert start_evt.data.tool_name == "my_fn"
        assert start_evt.data.tool_call_id == "c1"
        # COMPLETE event data
        complete_evt = next(e for e in events if e.type == SessionEventType.TOOL_EXECUTION_COMPLETE)
        assert complete_evt.data.tool_call_id == "c1"
        assert complete_evt.data.success is True

    @pytest.mark.asyncio
    async def test_failure_event_has_success_false(self):
        events = []

        async def handler(inv):
            return ToolResult(text_result_for_llm="", result_type="failure", error="boom")

        tool = _make_tool("t", handler=handler)
        responses = [
            _tool_response([_tool_call("c1", "t", '{}')]),
            _text_response("ok"),
        ]
        rt = _runtime_with_responses(*responses)
        await rt.run_session(prompt="go", tools=[tool], event_subscriber=lambda e: events.append(e))
        complete_evt = next(e for e in events if e.type == SessionEventType.TOOL_EXECUTION_COMPLETE)
        assert complete_evt.data.success is False
        assert complete_evt.data.error == "boom"


# ---------------------------------------------------------------------------
# 12. No subscriber — canonical tool_calls in result
# ---------------------------------------------------------------------------

class TestNoSubscriberCanonicalCalls:
    @pytest.mark.asyncio
    async def test_result_tool_calls_when_no_subscriber(self):
        tool = _make_tool("lookup")
        responses = [
            _tool_response([_tool_call("c1", "lookup", '{"q": "x"}')]),
            _text_response("42"),
        ]
        rt = _runtime_with_responses(*responses)
        result = await rt.run_session(prompt="go", tools=[tool])
        assert len(result.tool_calls) == 1
        tc = result.tool_calls[0]
        assert tc["tool_call_id"] == "c1"
        assert tc["name"] == "lookup"
        assert tc["tool"] == "lookup"
        assert tc["success"] is True
        assert "latency_ms" in tc

    @pytest.mark.asyncio
    async def test_result_tool_calls_empty_when_subscriber(self):
        tool = _make_tool("lookup")
        responses = [
            _tool_response([_tool_call("c1", "lookup", '{}')]),
            _text_response("done"),
        ]
        rt = _runtime_with_responses(*responses)
        result = await rt.run_session(prompt="go", tools=[tool], event_subscriber=lambda e: None)
        assert result.tool_calls == []


# ---------------------------------------------------------------------------
# 13. Token aggregation across turns
# ---------------------------------------------------------------------------

class TestTokenAggregation:
    @pytest.mark.asyncio
    async def test_tokens_summed_across_turns(self):
        responses = [
            _tool_response([_tool_call("c1", "t", '{}')], usage=_usage(10, 5)),
            _text_response("done", usage=_usage(20, 8)),
        ]
        tool = _make_tool("t")
        rt = _runtime_with_responses(*responses)
        result = await rt.run_session(prompt="go", tools=[tool])
        assert result.input_tokens == 30
        assert result.output_tokens == 13


# ---------------------------------------------------------------------------
# 14. Duplicate tool names
# ---------------------------------------------------------------------------

class TestDuplicateNames:
    @pytest.mark.asyncio
    async def test_duplicate_tool_names_rejected(self):
        t1 = _make_tool("dup")
        t2 = _make_tool("dup")
        rt = _runtime_with_responses(_text_response("x"))
        with pytest.raises(ValueError, match="[Dd]uplicate"):
            await rt.run_session(prompt="go", tools=[t1, t2])


# ---------------------------------------------------------------------------
# 15. Max turns exhaustion
# ---------------------------------------------------------------------------

class TestMaxTurns:
    @pytest.mark.asyncio
    async def test_max_turns_raises(self):
        # All responses request tool calls — should exhaust max turns
        responses = [_tool_response([_tool_call(f"c{i}", "t", '{}')]) for i in range(20)]
        tool = _make_tool("t")
        rt = _runtime_with_responses(*responses)
        with pytest.raises(RuntimeError, match="[Mm]ax.*turn"):
            await rt.run_session(prompt="go", tools=[tool])


# ---------------------------------------------------------------------------
# 16. Attachments fail
# ---------------------------------------------------------------------------

class TestAttachments:
    @pytest.mark.asyncio
    async def test_attachments_raise(self):
        rt = _runtime_with_responses(_text_response("x"))
        with pytest.raises((ValueError, NotImplementedError), match="[Aa]ttachment"):
            await rt.run_session(prompt="go", attachments=[{"type": "image"}])


# ---------------------------------------------------------------------------
# 17. Retry behavior preserved
# ---------------------------------------------------------------------------

class TestRetry:
    @pytest.mark.asyncio
    async def test_rate_limit_retried(self):
        from openai import RateLimitError
        import httpx

        # Build a fake 429 response
        raw = httpx.Response(429, headers={"retry-after": "0"}, request=httpx.Request("POST", "https://x"))
        exc = RateLimitError("rate limited", response=raw, body=None)
        responses_iter = iter([exc, _text_response("ok")])

        def side_effect(**kw):
            val = next(responses_iter)
            if isinstance(val, Exception):
                raise val
            return val

        rt = AOAIRuntime()
        client = MagicMock()
        client.chat.completions.create = MagicMock(side_effect=side_effect)
        rt._client = client
        result = await rt.run_session(prompt="hi")
        assert result.text == "ok"
        assert client.chat.completions.create.call_count == 2

"""Test/replay double for `LLMRuntime`.

Returns a canned response, increments `call_count`, never opens a
subprocess. Mutable class attributes so tests configure behaviour
before calling `run_session`:

    rt = FakeRuntime()
    rt.canned_text = '{"verdict": "strong"}'
    rt.canned_tool_calls = [{"name": "policy.search", "args": "{}", "result": "[]"}]
"""
from __future__ import annotations

from typing import Any, Callable
from pathlib import Path

from api.functions.graphs.executors.agents.runtime import LLMRuntimeResult


class FakeRuntime:
    canned_text: str = '{"ok": true}'
    canned_tool_calls: list[dict] = []
    canned_input_tokens: int | None = 10
    canned_output_tokens: int | None = 20
    call_count: int = 0
    last_prompt: str | None = None

    async def run_session(
        self,
        *,
        prompt: str,
        system_message: str | None = None,
        skill_directories: list[Path] | None = None,
        tools: list | None = None,
        permission_handler: Callable | None = None,
        attachments: list[dict] | None = None,
        model: str = "gpt-4.1",
        timeout_s: float = 240.0,
        event_subscriber: Callable[[Any], None] | None = None,
    ) -> LLMRuntimeResult:
        FakeRuntime.call_count += 1
        self.last_prompt = prompt
        return LLMRuntimeResult(
            text=self.canned_text,
            tool_calls=list(self.canned_tool_calls),
            input_tokens=self.canned_input_tokens,
            output_tokens=self.canned_output_tokens,
        )

"""Provider-neutral LLM runtime contract.

Phase 2 of plan/refactor-substrate-agentic-segments-1.md.

`_wrapper.py:run_agent_session` obtains an `LLMRuntime` via `_get_runtime()`
and never imports `copilot.CopilotClient` directly. New providers
(Claude, Azure OpenAI) ship as additional `runtime_<name>.py` files
implementing this Protocol, plus one new branch in `_get_runtime()`.

The OTEL session-event bridge stays in `_wrapper.py`; the runtime
accepts an `event_subscriber` callable it invokes with each session
event so the bridge subscribes from the outside without the runtime
needing to know about OpenTelemetry.
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Callable, Protocol, runtime_checkable

from pydantic import BaseModel


class LLMRuntimeResult(BaseModel):
    """Return value of `LLMRuntime.run_session`. The shape `_wrapper.py`
    already produces; lifted to its own model so multiple runtimes can
    agree on it."""

    text: str
    tool_calls: list[dict] = []
    input_tokens: int | None = None
    output_tokens: int | None = None
    raw_event: Any = None


@runtime_checkable
class LLMRuntime(Protocol):
    """Open one LLM session, send one prompt, return the parsed
    response. Implementations: `runtime_ghcp.GHCPRuntime` (production),
    `runtime_fake.FakeRuntime` (tests + replay harness)."""

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
        ...


def _get_runtime() -> LLMRuntime:
    """Dispatch on `LLM_RUNTIME` env var. Defaults to GHCP."""
    name = os.environ.get("LLM_RUNTIME", "ghcp").strip().lower()
    if name == "fake":
        from api.functions.graphs.executors.agents.runtime_fake import FakeRuntime
        return FakeRuntime()
    if name == "ghcp":
        from api.functions.graphs.executors.agents.runtime_ghcp import GHCPRuntime
        return GHCPRuntime()
    if name in ("aoai", "azure", "azure_openai"):
        from api.functions.graphs.executors.agents.runtime_aoai import AOAIRuntime
        return AOAIRuntime()
    raise ValueError(
        f"LLM_RUNTIME={name!r} not recognised. Supported: 'ghcp', 'aoai', 'fake'."
    )

"""GHCP implementation of LLMRuntime — current production path.

Body lifted verbatim from `_wrapper.py:run_agent_session` so behaviour
under `LLM_RUNTIME=ghcp` (the default) is unchanged.
"""
from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Any, Callable

from copilot import CopilotClient
from copilot.client import SubprocessConfig
from copilot.generated.session_events import SessionEventType
from copilot.session import PermissionHandler

from api.functions.graphs.executors.agents.runtime import LLMRuntimeResult, validate_required_tool_names


_gh_token_cache: str | None = None


def _gh_token() -> str:
    """Return the gh CLI auth token, cached for the lifetime of the process."""
    global _gh_token_cache
    if _gh_token_cache is None:
        _gh_token_cache = subprocess.check_output(
            ["gh", "auth", "token"], text=True,
        ).strip()
    return _gh_token_cache


class GHCPRuntime:
    """Wraps copilot.CopilotClient as an LLMRuntime."""

    async def run_session(
        self,
        *,
        prompt: str,
        system_message: str | None = None,
        skill_directories: list[Path] | None = None,
        tools: list | None = None,
        required_tool_names: list[str] | None = None,
        permission_handler: Callable | None = None,
        attachments: list[dict] | None = None,
        model: str = "gpt-4.1",
        timeout_s: float = 240.0,
        event_subscriber: Callable[[Any], None] | None = None,
    ) -> LLMRuntimeResult:
        registered_tools = tools or []
        required_names = validate_required_tool_names(
            required_tool_names, (tool.name for tool in registered_tools),
        )
        pending_tools: dict[str, str] = {}
        successful_tools: set[str] = set()

        def on_event(event: Any) -> None:
            data = event.data
            call_id = getattr(data, "tool_call_id", None) or getattr(data, "call_id", None)
            if event.type == SessionEventType.TOOL_EXECUTION_START:
                name = getattr(data, "tool_name", None)
                if call_id and name:
                    pending_tools[str(call_id)] = str(name)
            elif event.type == SessionEventType.TOOL_EXECUTION_COMPLETE:
                name = pending_tools.pop(str(call_id), None) or getattr(data, "tool_name", None)
                if name and getattr(data, "success", None) is True:
                    successful_tools.add(str(name))
            if event_subscriber is not None:
                event_subscriber(event)

        config = SubprocessConfig(github_token=_gh_token(), log_level="warning")
        client = CopilotClient(config)
        async with client:
            session_kwargs: dict = {
                "on_permission_request": permission_handler or PermissionHandler.approve_all,
                "model": model,
                "tools": registered_tools,
            }
            if system_message:
                session_kwargs["system_message"] = {"mode": "append", "content": system_message}
            if skill_directories:
                session_kwargs["skill_directories"] = [str(p) for p in skill_directories]
            session = await client.create_session(**session_kwargs)
            unsub = None
            if required_names or event_subscriber is not None:
                unsub = session.on(on_event)
            try:
                if attachments:
                    response_event = await session.send_and_wait(
                        prompt, attachments=attachments, timeout=timeout_s,
                    )
                else:
                    response_event = await session.send_and_wait(prompt, timeout=timeout_s)
            finally:
                if unsub is not None:
                    try:
                        unsub()
                    except Exception:
                        pass
                try:
                    await session.disconnect()
                except Exception:
                    pass

        missing_required = [name for name in required_names if name not in successful_tools]
        if missing_required:
            raise RuntimeError(
                "GHCP returned a final response before required tools succeeded: "
                f"{missing_required}"
            )

        text = ""
        in_tok = out_tok = None
        if response_event and getattr(response_event, "data", None):
            text = getattr(response_event.data, "content", "") or ""
            usage = getattr(response_event.data, "usage", None)
            if usage is not None:
                in_tok = getattr(usage, "input_tokens", None) or getattr(usage, "prompt_tokens", None)
                out_tok = getattr(usage, "output_tokens", None) or getattr(usage, "completion_tokens", None)

        return LLMRuntimeResult(
            text=text,
            tool_calls=[],  # collected externally via event_subscriber
            input_tokens=in_tok,
            output_tokens=out_tok,
            raw_event=response_event,
        )

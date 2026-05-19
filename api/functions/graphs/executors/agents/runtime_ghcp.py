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
from copilot.session import PermissionHandler

from api.functions.graphs.executors.agents.runtime import LLMRuntimeResult


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
        permission_handler: Callable | None = None,
        attachments: list[dict] | None = None,
        model: str = "gpt-4.1",
        timeout_s: float = 120.0,
        event_subscriber: Callable[[Any], None] | None = None,
    ) -> LLMRuntimeResult:
        config = SubprocessConfig(github_token=_gh_token(), log_level="warning")
        client = CopilotClient(config)
        async with client:
            session_kwargs: dict = {
                "on_permission_request": permission_handler or PermissionHandler.approve_all,
                "model": model,
                "tools": tools or [],
            }
            if system_message:
                session_kwargs["system_message"] = {"mode": "append", "content": system_message}
            if skill_directories:
                session_kwargs["skill_directories"] = [str(p) for p in skill_directories]
            session = await client.create_session(**session_kwargs)
            unsub = None
            if event_subscriber is not None:
                unsub = session.on(event_subscriber)
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

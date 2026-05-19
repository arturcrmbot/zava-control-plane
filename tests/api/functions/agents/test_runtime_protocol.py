"""Phase 2 of plan/refactor-substrate-agentic-segments-1.md.

Locks the LLMRuntime contract and the env-driven dispatch.
"""
from __future__ import annotations
import os
os.environ["AZURE_STORAGE_CONNECTION_STRING"] = ""

import subprocess
import pytest
from pydantic import ValidationError


def test_llm_runtime_result_shape() -> None:
    from api.functions.graphs.executors.agents.runtime import LLMRuntimeResult
    r = LLMRuntimeResult(text='{"ok":true}', tool_calls=[], input_tokens=10, output_tokens=20)
    assert r.text == '{"ok":true}'
    assert r.tool_calls == []
    assert r.input_tokens == 10
    assert r.output_tokens == 20
    with pytest.raises(ValidationError):
        LLMRuntimeResult()  # text required


def test_runtime_protocol_runtime_checkable() -> None:
    from api.functions.graphs.executors.agents.runtime import LLMRuntime

    class _Stub:
        async def run_session(self, **kw):  # type: ignore[no-untyped-def]
            from api.functions.graphs.executors.agents.runtime import LLMRuntimeResult
            return LLMRuntimeResult(text="x", tool_calls=[])

    assert isinstance(_Stub(), LLMRuntime)

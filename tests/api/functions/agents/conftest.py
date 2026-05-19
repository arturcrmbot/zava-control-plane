import pytest


@pytest.fixture(autouse=True)
def _reset_fake_runtime():
    """FakeRuntime uses class-level mutable state (intentional, so the
    A/B replay harness can read aggregate call counts across instances).
    Reset between tests to keep them independent."""
    from api.functions.graphs.executors.agents.runtime_fake import FakeRuntime
    FakeRuntime.canned_text = '{"ok": true}'
    FakeRuntime.canned_tool_calls = []
    FakeRuntime.canned_input_tokens = 10
    FakeRuntime.canned_output_tokens = 20
    FakeRuntime.call_count = 0
    FakeRuntime.last_prompt = None
    yield
    FakeRuntime.call_count = 0

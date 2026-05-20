"""A1 regression test: tool_calls captured by build_event_handler must
carry BOTH 'name' (legacy) and 'tool' (working_memory_capture) keys."""
import pytest


@pytest.mark.skip(
    reason="placeholder — SessionEventType stream events are awkward to mock in "
    "isolation; consumer-side tests in tests/api/services/lessons/"
    "test_working_memory_capture.py lock down the contract from the other end."
)
def test_tool_calls_carry_both_name_and_tool_keys():
    pass

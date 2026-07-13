"""Unit test for the surge-staffing decision activity — the "agent" that reads
world state and sizes the staffing response. Proves the decision is a genuine
function of world data (not a constant)."""
from api.functions.workflows.surge_staffing_activities import surge_staffing_decide_activity


def test_hires_to_cover_backlog_and_arrival():
    # backlog 50 + arrival 90 at HANDLE 2 -> target 70 agents; already have 20 -> hire 50.
    out = surge_staffing_decide_activity({"world": {"backlog": 50, "arrival": 90, "handle": 2, "agents": 20}})
    assert out["target_agents"] == 70
    assert out["hired"] == 50


def test_no_hire_when_capacity_already_sufficient():
    out = surge_staffing_decide_activity({"world": {"backlog": 0, "arrival": 30, "handle": 2, "agents": 20}})
    assert out["hired"] == 0


def test_decision_scales_with_the_world():
    small = surge_staffing_decide_activity({"world": {"backlog": 20, "arrival": 30, "handle": 2, "agents": 20}})
    big = surge_staffing_decide_activity({"world": {"backlog": 400, "arrival": 90, "handle": 2, "agents": 20}})
    assert big["hired"] > small["hired"]


def test_missing_world_is_safe():
    out = surge_staffing_decide_activity({})
    assert out["hired"] == 0

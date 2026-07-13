from api.functions.workflows.surge_staffing_activities import (
    surge_staffing_decide_activity,
)


def observation(*, technical=30, billing=10, account=0, reserve=True):
    tickets = [
        {"id": f"TKT-T-{i}", "required_skill": "technical"}
        for i in range(technical)
    ]
    tickets += [
        {"id": f"TKT-B-{i}", "required_skill": "billing"}
        for i in range(billing)
    ]
    tickets += [
        {"id": f"TKT-A-{i}", "required_skill": "account"}
        for i in range(account)
    ]
    workers = (
        [
            {"id": "WRK-0031", "skills": ["billing"]},
            {"id": "WRK-0032", "skills": ["technical"]},
            {"id": "WRK-0033", "skills": ["technical", "account"]},
            {"id": "WRK-0034", "skills": ["account"]},
        ]
        if reserve else []
    )
    return {
        "trace_id": "support-pressure-42",
        "observation": {
            "queued_tickets": tickets,
            "support_workers": [],
            "reserve_workers": workers,
            "projection": {"support_backlog": len(tickets)},
            "allowed_commands": ["reallocate_workers"],
        },
    }


def test_selects_workers_covering_the_highest_skill_pressure():
    out = surge_staffing_decide_activity(observation())
    command = out["command"]
    assert command["payload"]["worker_ids"] == ["WRK-0032", "WRK-0033"]
    assert command["type"] == "reallocate_workers"
    assert command["trace_id"] == "support-pressure-42"


def test_selected_worker_count_scales_with_backlog():
    small = surge_staffing_decide_activity(observation(technical=5, billing=0))
    large = surge_staffing_decide_activity(observation(technical=65, billing=0))
    assert len(small["command"]["payload"]["worker_ids"]) == 1
    assert len(large["command"]["payload"]["worker_ids"]) == 4


def test_worker_count_uses_total_projection_not_capped_ticket_sample():
    payload = observation(technical=20, billing=0)
    payload["observation"]["projection"]["support_backlog"] = 65
    out = surge_staffing_decide_activity(payload)
    assert len(out["command"]["payload"]["worker_ids"]) == 4
    assert "backlog=65" in out["reasoning"]


def test_no_queue_or_no_reserve_returns_explicit_noop():
    empty = surge_staffing_decide_activity(
        observation(technical=0, billing=0, account=0)
    )
    no_reserve = surge_staffing_decide_activity(observation(reserve=False))
    assert empty["command"] is None
    assert "no queued tickets" in empty["reasoning"]
    assert no_reserve["command"] is None
    assert "no reserve workers" in no_reserve["reasoning"]

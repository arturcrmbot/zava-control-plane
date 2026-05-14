"""agent_fleet_employee_onboarding_induction_planner — invokes the
fleet-employee-onboarding-induction-planner skill via the GHCP SDK.

Pass *only* the induction-planner skill directory to `skill_directories`
so multiple loaded skills don't fight over the output schema. Tools are
SDK-native (`@define_tool`), registered via `tools=[...]`, and called
autonomously by the model per the skill's `allowed-tools` frontmatter.
No prompt-stuffing.
"""
from __future__ import annotations

from api.server.mcp_tools.calendar_service import (
    calendar_service_find_availability_tool,
    calendar_service_get_room_options_tool,
    calendar_service_book_event_tool,
)

from ._wrapper import SKILLS_DIR, run_agent_session

_SKILL_DIR = SKILLS_DIR / "fleet-employee-onboarding-induction-planner"


async def execute(input: dict) -> dict:
    workflow_id = input.get("workflow_id")
    joiner = input.get("joiner") or {}
    employee_lookup = input.get("employee_lookup") or {}
    it_admin_approval_decision = input.get("it_admin_approval_decision") or {}
    prompt = (
        f"Plan a 90-minute induction for the new joiner below.\n\n"
        f"Joiner: employee_id={joiner.get('employee_id')!r}, "
        f"department={joiner.get('department')!r}, "
        f"buddy_id={joiner.get('buddy_id')!r}, "
        f"start_date={joiner.get('start_date')!r}.\n"
        f"Employee context: grade={employee_lookup.get('grade')!r}, "
        f"agency={employee_lookup.get('agency')!r}, "
        f"home_market={employee_lookup.get('home_market')!r}, "
        f"manager_id={employee_lookup.get('manager_id')!r}.\n"
        f"IT admin approval: decision={it_admin_approval_decision.get('decision')!r}, "
        f"reason={it_admin_approval_decision.get('reason')!r}.\n\n"
        f"Use `calendar_service_find_availability(attendees, "
        f"duration_minutes, window_start, window_days)` to find a "
        f"90-minute slot across joiner + buddy + line manager within "
        f"the first 14 days from start_date. Use "
        f"`calendar_service_get_room_options(market, capacity)` to "
        f"load room candidates in the joiner's home market. Use "
        f"`calendar_service_book_event(slot, room_id, attendees, "
        f"subject)` to book the event. "
        f"Reason about which slot and room to pick per your skill spec. "
        f"Return exactly the JSON object specified in your skill instructions "
        f"— no prose, no markdown."
    )
    result = await run_agent_session(
        prompt=prompt,
        tools=[
            calendar_service_find_availability_tool,
            calendar_service_get_room_options_tool,
            calendar_service_book_event_tool,
        ],
        skill_dir=_SKILL_DIR,
        skill_label="fleet-employee-onboarding-induction-planner",
        workflow_id=workflow_id,
    )
    return {"induction_planner": result}

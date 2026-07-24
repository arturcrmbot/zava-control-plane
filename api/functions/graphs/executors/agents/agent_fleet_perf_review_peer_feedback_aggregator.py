"""agent_fleet_perf_review_peer_feedback_aggregator — invokes the
fleet-perf-review-peer-feedback-aggregator skill via the GHCP SDK.

Pass *only* the peer-feedback-aggregator skill directory to
`skill_directories` so multiple loaded skills don't fight over the
output schema. Tools are SDK-native (`@define_tool`), registered via
`tools=[...]`, and called autonomously by the model per the skill's
`allowed-tools` frontmatter. No prompt-stuffing.
"""
from __future__ import annotations

from api.server.mcp_tools.feedback_collector import (
    feedback_collector_list_360_tool,
    feedback_collector_get_okr_results_tool,
)
from api.server.mcp_tools.workday_hr_employee import workday_hr_employee_get_employee_tool

from ._wrapper import SKILLS_DIR, run_agent_session

_SKILL_DIR = SKILLS_DIR / "fleet-perf-review-peer-feedback-aggregator"


async def execute(input: dict) -> dict:
    workflow_id = input.get("workflow_id")
    review = input.get("review") or {}
    employee_lookup = input.get("employee_lookup") or {}
    prompt = (
        f"Aggregate the 360-degree peer reviews for the cycle below, "
        f"re-confirm the reviewee's reporting line via Workday HR, and "
        f"pull the cycle's OKR results.\n\n"
        f"Review request: employee_id={review.get('employee_id')!r}, "
        f"cycle={review.get('cycle')!r}.\n"
        f"Employee record: employee_id={employee_lookup.get('employee_id')!r}, "
        f"grade={employee_lookup.get('grade')!r}, "
        f"cost_centre={employee_lookup.get('cost_centre')!r}, "
        f"agency={employee_lookup.get('agency')!r}, "
        f"home_market={employee_lookup.get('home_market')!r}, "
        f"manager_id={employee_lookup.get('manager_id')!r}.\n\n"
        f"Use `feedback_collector_list_360(employee_id, cycle)` to load "
        f"every 360-degree peer review for the cycle. Use "
        f"`workday_hr_employee_get_employee(employee_id)` to re-confirm "
        f"the reviewee's reporting line. Use "
        f"`feedback_collector_get_okr_results(employee_id, cycle)` to "
        f"load the cycle's rolled-up OKR result. "
        f"Reason about whether enough peer evidence is in to draft a "
        f"calibration per your skill spec. "
        f"Return exactly the JSON object specified in your skill instructions "
        f"— no prose, no markdown."
    )
    result = await run_agent_session(
        prompt=prompt,
        tools=[
            feedback_collector_list_360_tool,
            feedback_collector_get_okr_results_tool,
            workday_hr_employee_get_employee_tool,
        ],
        skill_dir=_SKILL_DIR,
        skill_label="fleet-perf-review-peer-feedback-aggregator",
        workflow_id=workflow_id,
        instance_id=input.get("instance_id"),
    )
    return {"peer_feedback_aggregator": result}

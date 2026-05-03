"""agent_fleet_perf_review_calibration_drafter — invokes the
fleet-perf-review-calibration-drafter skill via the GHCP SDK.

Pass *only* the calibration-drafter skill directory to `skill_directories`
so multiple loaded skills don't fight over the output schema. Tools are
SDK-native (`@define_tool`), registered via `tools=[...]`, and called
autonomously by the model per the skill's `allowed-tools` frontmatter.
No prompt-stuffing.
"""
from __future__ import annotations

from api.server.mcp_tools.performance_norms import (
    performance_norms_get_grade_distribution_tool,
    performance_norms_get_calibration_history_tool,
)
from api.server.mcp_tools.feedback_collector import (
    feedback_collector_list_360_tool,
    feedback_collector_get_okr_results_tool,
)

from ._wrapper import SKILLS_DIR, run_agent_session

_SKILL_DIR = SKILLS_DIR / "fleet-perf-review-calibration-drafter"


async def execute(input: dict) -> dict:
    workflow_id = input.get("workflow_id")
    review = input.get("review") or {}
    employee_lookup = input.get("employee_lookup") or {}
    peer_feedback_aggregator = input.get("peer_feedback_aggregator") or {}
    prompt = (
        f"Draft a proposed performance rating + narrative for the "
        f"reviewee below. Combine the cycle's OKR results with the "
        f"grade-band distribution norm and the reviewee's calibration "
        f"history.\n\n"
        f"Review request: employee_id={review.get('employee_id')!r}, "
        f"cycle={review.get('cycle')!r}.\n"
        f"Employee record: employee_id={employee_lookup.get('employee_id')!r}, "
        f"grade={employee_lookup.get('grade')!r}, "
        f"agency={employee_lookup.get('agency')!r}, "
        f"home_market={employee_lookup.get('home_market')!r}.\n"
        f"Peer feedback verdict: verdict={peer_feedback_aggregator.get('verdict')!r}, "
        f"peer_review_count={peer_feedback_aggregator.get('peer_review_count')!r}, "
        f"reporting_line={peer_feedback_aggregator.get('reporting_line')!r}, "
        f"okr_results={peer_feedback_aggregator.get('okr_results')!r}.\n\n"
        f"Use `performance_norms_get_grade_distribution(grade, cycle)` "
        f"to load the grade-band rating distribution norm (target percent, "
        f"current percent, headroom per top rating). Use "
        f"`performance_norms_get_calibration_history(employee_id)` to "
        f"load the reviewee's prior cycles. Use "
        f"`feedback_collector_get_okr_results(employee_id, cycle)` if "
        f"you need to re-read the cycle's OKR detail. Use "
        f"`feedback_collector_list_360(employee_id, cycle)` if you need "
        f"to re-read the peer reviews for the narrative. "
        f"Reason about a proposed rating + distribution_fit verdict per "
        f"your skill spec. "
        f"Return exactly the JSON object specified in your skill instructions "
        f"— no prose, no markdown."
    )
    result = await run_agent_session(
        prompt=prompt,
        tools=[
            performance_norms_get_grade_distribution_tool,
            performance_norms_get_calibration_history_tool,
            feedback_collector_list_360_tool,
            feedback_collector_get_okr_results_tool,
        ],
        skill_dir=_SKILL_DIR,
        skill_label="fleet-perf-review-calibration-drafter",
        workflow_id=workflow_id,
    )
    return {"calibration_drafter": result}

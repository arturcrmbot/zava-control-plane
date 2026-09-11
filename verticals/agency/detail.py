from __future__ import annotations

from typing import Any


WORKFLOW_TYPE = "aurora-budget-response"


def workflow_detail(workflow, app_state) -> dict[str, Any] | None:
    if workflow.type != WORKFLOW_TYPE:
        return None
    payload = dict(workflow.payload or {})
    outputs = dict(payload.get("outputs") or {})
    hitl_context = payload.get("hitl_context")
    decisions = list(payload.get("decisions") or [])
    children = list(outputs.get("children") or payload.get("child_workflow_ids") or [])
    synthesis = outputs.get("synthesis")
    child_outcomes = (
        list(synthesis.get("child_outcomes") or [])
        if isinstance(synthesis, dict)
        else []
    )
    if children and child_outcomes:
        children = [
            {
                **(child if isinstance(child, dict) else {"workflow_id": child}),
                "outcome": (
                    child_outcomes[index]
                    if index < len(child_outcomes)
                    else None
                ),
            }
            for index, child in enumerate(children)
        ]
    return {
        "workflow_id": workflow.id,
        "orchestration_instance_id": workflow.orchestration_instance_id,
        "status": workflow.status,
        "current_phase": workflow.current_phase,
        "trigger": {
            "request_id": payload.get("request_id"),
            "brand_id": payload.get("brand_id"),
            "count": payload.get("count"),
        },
        "phases": [
            phase.model_dump(by_alias=True)
            for phase in app_state.store.get_phases(workflow.id)
        ],
        "outputs": {
            "observation": outputs.get("observation"),
            "recommendation": outputs.get("recommendation"),
            "policy": outputs.get("policy"),
            "synthesis": synthesis,
        },
        "hitl": hitl_context if isinstance(hitl_context, dict) else (
            decisions[-1] if decisions else None
        ),
        "decisions": decisions,
        "children": children,
        "agent_reasoning": app_state.store.get_agent_reasoning(workflow.id),
        "events": list(app_state.orchestration_history.get(workflow.id, [])),
    }

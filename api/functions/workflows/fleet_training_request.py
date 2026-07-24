"""
The single Training request generator orchestration — one workflow end-to-end.

4 phases per docs/superpowers/specs/training-request-brief.yaml:
  Request Intake -> Eligibility & Catalogue -> HR Director Approval -> Book

HITL gates:
  - Phase 3 (HR Director Approval) waits for the `hr_director_decision`
    external event (byte-matches api/server/personae/hr_director/SKILL.md
    frontmatter — KR-2).

Sync generator per the Azure Durable Functions Python convention. Phase
activities are registered in `function_app.py` by graduate.sh.
"""
from __future__ import annotations
import os
from collections.abc import Generator
from typing import Any

import azure.durable_functions as df

from api.shared.constants import HR_DIRECTOR_DECISION_TIMEOUT


def fleet_training_request_orchestration(
    context: df.DurableOrchestrationContext,
) -> Generator[Any, Any, dict]:
    """Orchestrate the 4 Training request phases for one workflow.

    Phase 2 (eligibility_and_catalogue) runs as a segment activity
    (segments-by-default for `kind: agent`). SEGMENT_MAX_RETRIES is read
    inside this function so operators can tune retry budget without a
    worker restart.
    """
    segment_max_retries = int(os.environ.get("SEGMENT_MAX_RETRIES", "2"))

    input_dict = context.get_input() or {}
    workflow_id = input_dict.get("workflow_id", "?")
    # v3 substrate-fix contract: stamp workflow_type on every checkpoint
    # payload so internal_durable_event populates its _workflow_types
    # cache and forwards `workflow_type` onto every downstream FleetEvent.
    workflow_type = input_dict.get("type", "training-request")
    enriched = {
        **input_dict,
        "workflow_id": workflow_id,
        "instance_id": context.instance_id,
    }

    yield context.call_activity("checkpoint_activity_trigger", {
        "workflow_id": workflow_id, "instance_id": context.instance_id,
        "kind": "workflow.started",
        "payload": {
            "domain": "fleet-training-request",
            "workflow_type": workflow_type,
        },
    })

    # Phase 1: Request Intake (deterministic)
    request_intake_result = yield context.call_activity(
        "fleet_training_request_request_intake_activity_trigger", enriched
    )
    enriched = {**enriched, "request_intake": request_intake_result}

    # Phase 2: Eligibility & Catalogue (agent segment B) — segments-by-default
    # retry loop. Mirrors api/functions/workflows/hiring.py:120-162.
    segment_input = {
        **enriched,
        "covered_phases": ["Eligibility & Catalogue"],
    }
    segment_b_result = None
    validator_b: dict = {}
    for attempt in range(segment_max_retries + 1):
        segment_b_result = yield context.call_activity(
            "training_request_segment_b_activity_trigger", segment_input,
        )
        validator_b = yield context.call_activity(
            "validate_training_request_segment_b_output_activity_trigger",
            segment_b_result,
        )
        if validator_b.get("ok"):
            segment_b_result = validator_b["output"]
            break
        segment_input = {
            **segment_input,
            "prior_validator_error": repr(validator_b.get("errors")),
        }
    else:
        yield context.call_activity("checkpoint_activity_trigger", {
            "workflow_id": workflow_id, "instance_id": context.instance_id,
            "kind": "segment.failed",
            "payload": {
                "segment": "b",
                "phase": "eligibility_and_catalogue",
                "errors": validator_b.get("errors"),
                "workflow_type": workflow_type,
            },
        })
        raise RuntimeError(
            f"Segment B (eligibility_and_catalogue) validation failed after "
            f"{segment_max_retries + 1} attempts"
        )
    eligibility_and_catalogue_result = segment_b_result
    enriched = {**enriched, "eligibility_and_catalogue": eligibility_and_catalogue_result}

    # Phase 3: HR Director Approval (HITL — hr_director persona)
    yield context.call_activity("checkpoint_activity_trigger", {
        "workflow_id": workflow_id, "instance_id": context.instance_id,
        "kind": "suspended",
        "payload": {
            "reason": "awaiting_hr_director_approval",
            "phase": "hr_director_approval",
            "wait_kind": "operator_review",
            "workflow_type": workflow_type,
            # Persona-responder contract: tell the responder which persona
            # owns this gate, which event resumes it, and the prior-phase
            # context the persona needs to apply its decision policy.
            "persona": "hr_director",
            "external_event": "hr_director_decision",
            "context": {
                "request_intake": enriched.get("request_intake"),
                "eligibility_and_catalogue": enriched.get("eligibility_and_catalogue"),
            },
        },
    })

    director_event = context.wait_for_external_event("hr_director_decision")
    director_timeout = context.create_timer(
        context.current_utc_datetime + HR_DIRECTOR_DECISION_TIMEOUT
    )
    winner = yield context.task_any([director_event, director_timeout])

    if winner == director_timeout:
        yield context.call_activity("checkpoint_activity_trigger", {
            "workflow_id": workflow_id, "instance_id": context.instance_id,
            "kind": "workflow.completed",
            "payload": {
                "status": "timeout",
                "phase": "hr_director_approval",
                "workflow_type": workflow_type,
            },
        })
        return {"status": "timeout", "phase": "hr_director_approval"}
    director_timeout.cancel()

    enriched["hr_director_decision"] = director_event.result

    yield context.call_activity("checkpoint_activity_trigger", {
        "workflow_id": workflow_id, "instance_id": context.instance_id,
        "kind": "resumed",
        "payload": {
            "phase": "hr_director_approval",
            "workflow_type": workflow_type,
        },
    })

    # Phase 4: Book (deterministic) — record the booking on the payload.
    book_result = yield context.call_activity(
        "fleet_training_request_book_activity_trigger", enriched
    )
    enriched = {**enriched, "book": book_result}

    yield context.call_activity("checkpoint_activity_trigger", {
        "workflow_id": workflow_id, "instance_id": context.instance_id,
        "kind": "workflow.completed",
        "payload": {"workflow_type": workflow_type},
    })

    return {
        "status": "completed",
        "request_intake": request_intake_result,
        "eligibility_and_catalogue": eligibility_and_catalogue_result,
        "hr_director_decision": enriched["hr_director_decision"],
        "book": book_result,
    }

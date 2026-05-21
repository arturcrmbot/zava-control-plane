"""
The single Employee transfer between organisations generator orchestration —
one workflow end-to-end.

7 phases per docs/superpowers/specs/employee-transfer-brief.yaml:
  Transfer Intake -> Employee Lookup -> Eligibility Check ->
  Releasing Manager Approval -> Compensation Remap ->
  HR Director Signoff -> Identity Migration

HITL gates:
  - Phase 4 (Releasing Manager Approval) waits for the
    `manager_approval_decision` external event.
  - Phase 6 (HR Director Signoff) waits for the
    `hr_director_decision` external event.

Sync generator per the Azure Durable Functions Python convention. Phase
activities are registered in `function_app.py` by graduate.sh.
"""
from __future__ import annotations
import os
from collections.abc import Generator
from datetime import timedelta
from typing import Any

import azure.durable_functions as df

# Per-phase HITL timeouts. Defined locally pre-graduation; graduate.sh lifts
# them into api/shared/constants.py and rewrites this file's import.
from api.shared.constants import (
    MANAGER_APPROVAL_DECISION_TIMEOUT,
    HR_DIRECTOR_DECISION_TIMEOUT,
)


def fleet_employee_transfer_orchestration(
    context: df.DurableOrchestrationContext,
) -> Generator[Any, Any, dict]:
    """Orchestrate the 7 Employee transfer phases for one workflow.

    Phases 3 (eligibility_check) and 5 (compensation_remap) run as
    segment activities (segments-by-default for `kind: agent`).
    SEGMENT_MAX_RETRIES is read inside this function so operators can
    tune retry budget without a worker restart.
    """
    segment_max_retries = int(os.environ.get("SEGMENT_MAX_RETRIES", "2"))

    input_dict = context.get_input() or {}
    workflow_id = input_dict.get("workflow_id", "?")
    # v3 substrate-fix contract: stamp workflow_type on every checkpoint
    # payload so internal_durable_event populates its _workflow_types
    # cache and forwards `workflow_type` onto every downstream FleetEvent.
    workflow_type = input_dict.get("type", "employee-transfer")
    enriched = {**input_dict, "instance_id": context.instance_id}

    yield context.call_activity("checkpoint_activity_trigger", {
        "workflow_id": workflow_id, "instance_id": context.instance_id,
        "kind": "workflow.started",
        "payload": {
            "domain": "fleet-employee-transfer",
            "workflow_type": workflow_type,
        },
    })

    # Phase 1: Transfer Intake (deterministic)
    transfer_intake_result = yield context.call_activity(
        "fleet_employee_transfer_transfer_intake_activity_trigger", enriched
    )
    enriched = {**enriched, "transfer_intake": transfer_intake_result}

    # Phase 2: Employee Lookup (deterministic)
    employee_lookup_result = yield context.call_activity(
        "fleet_employee_transfer_employee_lookup_activity_trigger", enriched
    )
    enriched = {**enriched, "employee_lookup": employee_lookup_result}

    # Phase 3: Eligibility Check (agent segment B) — segments-by-default
    # retry loop. Mirrors api/functions/workflows/hiring.py:120-162.
    segment_input = {**enriched, "workflow_id": context.instance_id}
    segment_b_result = None
    validator_b: dict = {}
    for attempt in range(segment_max_retries + 1):
        segment_b_result = yield context.call_activity(
            "employee_transfer_segment_b_activity_trigger", segment_input,
        )
        validator_b = yield context.call_activity(
            "validate_employee_transfer_segment_b_output_activity_trigger",
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
                "phase": "eligibility_check",
                "errors": validator_b.get("errors"),
                "workflow_type": workflow_type,
            },
        })
        raise RuntimeError(
            f"Segment B (eligibility_check) validation failed after "
            f"{segment_max_retries + 1} attempts"
        )
    eligibility_check_result = segment_b_result
    enriched = {**enriched, "eligibility_check": eligibility_check_result}

    # Phase 4: Releasing Manager Approval (HITL — line_manager persona)
    yield context.call_activity("checkpoint_activity_trigger", {
        "workflow_id": workflow_id, "instance_id": context.instance_id,
        "kind": "suspended",
        "payload": {
            "reason": "awaiting_releasing_manager_approval",
            "phase": "releasing_manager_approval",
            "wait_kind": "operator_review",
            "workflow_type": workflow_type,
            # Persona-responder contract: tell the responder which persona
            # owns this gate, which event resumes it, and the prior-phase
            # context the persona needs to apply its decision policy.
            "persona": "line_manager",
            "external_event": "manager_approval_decision",
            "context": {
                "employee_lookup": enriched.get("employee_lookup"),
                "eligibility_check": enriched.get("eligibility_check"),
            },
        },
    })

    manager_event = context.wait_for_external_event("manager_approval_decision")
    manager_timeout = context.create_timer(
        context.current_utc_datetime + MANAGER_APPROVAL_DECISION_TIMEOUT
    )
    winner = yield context.task_any([manager_event, manager_timeout])

    if winner == manager_timeout:
        yield context.call_activity("checkpoint_activity_trigger", {
            "workflow_id": workflow_id, "instance_id": context.instance_id,
            "kind": "workflow.completed",
            "payload": {
                "status": "timeout",
                "phase": "releasing_manager_approval",
                "workflow_type": workflow_type,
            },
        })
        return {"status": "timeout", "phase": "releasing_manager_approval"}
    manager_timeout.cancel()

    enriched["manager_approval_decision"] = manager_event.result

    yield context.call_activity("checkpoint_activity_trigger", {
        "workflow_id": workflow_id, "instance_id": context.instance_id,
        "kind": "resumed",
        "payload": {
            "phase": "releasing_manager_approval",
            "workflow_type": workflow_type,
        },
    })

    # Phase 5: Compensation Remap (agent segment D)
    segment_input = {**enriched, "workflow_id": context.instance_id}
    segment_d_result = None
    validator_d: dict = {}
    for attempt in range(segment_max_retries + 1):
        segment_d_result = yield context.call_activity(
            "employee_transfer_segment_d_activity_trigger", segment_input,
        )
        validator_d = yield context.call_activity(
            "validate_employee_transfer_segment_d_output_activity_trigger",
            segment_d_result,
        )
        if validator_d.get("ok"):
            segment_d_result = validator_d["output"]
            break
        segment_input = {
            **segment_input,
            "prior_validator_error": repr(validator_d.get("errors")),
        }
    else:
        yield context.call_activity("checkpoint_activity_trigger", {
            "workflow_id": workflow_id, "instance_id": context.instance_id,
            "kind": "segment.failed",
            "payload": {
                "segment": "d",
                "phase": "compensation_remap",
                "errors": validator_d.get("errors"),
                "workflow_type": workflow_type,
            },
        })
        raise RuntimeError(
            f"Segment D (compensation_remap) validation failed after "
            f"{segment_max_retries + 1} attempts"
        )
    compensation_remap_result = segment_d_result
    enriched = {**enriched, "compensation_remap": compensation_remap_result}

    # Phase 6: HR Director Signoff (HITL — hr_director persona)
    yield context.call_activity("checkpoint_activity_trigger", {
        "workflow_id": workflow_id, "instance_id": context.instance_id,
        "kind": "suspended",
        "payload": {
            "reason": "awaiting_hr_director_signoff",
            "phase": "hr_director_signoff",
            "wait_kind": "operator_review",
            "workflow_type": workflow_type,
            "persona": "hr_director",
            "external_event": "hr_director_decision",
            "context": {
                "eligibility_check": enriched.get("eligibility_check"),
                "compensation_remap": enriched.get("compensation_remap"),
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
                "phase": "hr_director_signoff",
                "workflow_type": workflow_type,
            },
        })
        return {"status": "timeout", "phase": "hr_director_signoff"}
    director_timeout.cancel()

    enriched["hr_director_decision"] = director_event.result

    yield context.call_activity("checkpoint_activity_trigger", {
        "workflow_id": workflow_id, "instance_id": context.instance_id,
        "kind": "resumed",
        "payload": {
            "phase": "hr_director_signoff",
            "workflow_type": workflow_type,
        },
    })

    # Phase 7: Identity Migration (deterministic)
    identity_migration_result = yield context.call_activity(
        "fleet_employee_transfer_identity_migration_activity_trigger", enriched
    )
    enriched = {**enriched, "identity_migration": identity_migration_result}

    yield context.call_activity("checkpoint_activity_trigger", {
        "workflow_id": workflow_id, "instance_id": context.instance_id,
        "kind": "workflow.completed",
        "payload": {"workflow_type": workflow_type},
    })

    return {
        "status": "completed",
        "transfer_intake": transfer_intake_result,
        "employee_lookup": employee_lookup_result,
        "eligibility_check": eligibility_check_result,
        "manager_approval_decision": enriched["manager_approval_decision"],
        "compensation_remap": compensation_remap_result,
        "hr_director_decision": enriched["hr_director_decision"],
        "identity_migration": identity_migration_result,
    }

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

from api.server.services.entity_graph import DecisionWrite, EntityWrite, RelWrite
from api.shared.types import Workflow
from verticals.airline.process_profiles import (
    HITL_PERSONA,
    SCENARIO_ID,
    STORY_ID,
    WORKFLOW_TYPE,
)

_DISRUPTION_ID = "SYN-DISRUPTION-HUB-001"


def _json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, default=str)


def _asset(
    record: dict[str, Any],
    *,
    asset_kind: str,
    workflow_id: str,
) -> EntityWrite | None:
    record_id = record.get("id")
    if not isinstance(record_id, str) or not record_id:
        return None
    return EntityWrite(
        kind="Asset",
        id=record_id,
        attrs={
            "kind": asset_kind,
            "identifier": record_id,
            "status": str(record.get("status") or ""),
            "attributes": _json(record),
        },
        source_workflows=(workflow_id,),
    )


def _append_asset(
    operations: list[EntityWrite | RelWrite | DecisionWrite],
    seen: set[str],
    record: Any,
    *,
    asset_kind: str,
    workflow_id: str,
) -> str | None:
    if not isinstance(record, dict):
        return None
    entity = _asset(
        record,
        asset_kind=asset_kind,
        workflow_id=workflow_id,
    )
    if entity is None:
        return None
    if entity.id not in seen:
        operations.append(entity)
        seen.add(entity.id)
    return entity.id


def _related(
    operations: list[EntityWrite | RelWrite | DecisionWrite],
    source_id: str | None,
    target_id: str | None,
    role: str,
) -> None:
    if source_id and target_id:
        operations.append(
            RelWrite(
                source_id,
                "RELATED_ASSET",
                target_id,
                attrs={"role": role},
            )
        )


def _evidence(workflow: Workflow) -> tuple[dict[str, Any], dict[str, Any]]:
    payload = workflow.payload if isinstance(workflow.payload, dict) else {}
    evidence = payload.get("evidence")
    return payload, evidence if isinstance(evidence, dict) else {}


def project(
    workflow: Workflow,
) -> list[EntityWrite | RelWrite | DecisionWrite]:
    if workflow.type != WORKFLOW_TYPE:
        return []
    payload, evidence = _evidence(workflow)
    observation = payload.get("observation")
    if not isinstance(observation, dict):
        workflow_evidence = evidence.get("workflow_evidence")
        observation = workflow_evidence.get("observation") if isinstance(workflow_evidence, dict) else None
    observation = observation if isinstance(observation, dict) else {}
    workflow_id = workflow.id
    source_workflows = (workflow_id,)
    operations: list[EntityWrite | RelWrite | DecisionWrite] = [
        EntityWrite(
            kind="Workflow",
            id=workflow_id,
            attrs={
                "workflow_type": WORKFLOW_TYPE,
                "status": workflow.status,
                "attributes": _json(
                    {
                        "scenario_id": observation.get(
                            "scenario_id",
                            SCENARIO_ID,
                        ),
                        "story_id": observation.get("story_id", STORY_ID),
                    }
                ),
            },
            source_workflows=source_workflows,
        ),
        EntityWrite(
            kind="Asset",
            id=STORY_ID,
            attrs={
                "kind": "disruption-story",
                "identifier": STORY_ID,
                "status": ("resolved" if evidence.get("command") else "active"),
                "attributes": _json(
                    {
                        "scenario_id": observation.get(
                            "scenario_id",
                            SCENARIO_ID,
                        ),
                        "source_event_id": observation.get("source_event_id"),
                        "sensor_event_id": observation.get("sensor_event_id"),
                        "source_mode": (evidence.get("workflow_evidence") or {}).get(
                            "source_mode", "simulated"
                        ),
                    }
                ),
            },
            source_workflows=source_workflows,
        ),
        EntityWrite(
            kind="Asset",
            id=_DISRUPTION_ID,
            attrs={
                "kind": "hub-disruption",
                "identifier": _DISRUPTION_ID,
                "status": ("resolved" if evidence.get("command") else "active"),
                "attributes": _json(
                    {
                        "story_id": STORY_ID,
                        "scenario_id": SCENARIO_ID,
                    }
                ),
            },
            source_workflows=source_workflows,
        ),
        RelWrite(workflow_id, "TRIGGERED_BY", STORY_ID),
        RelWrite(
            STORY_ID,
            "RELATED_ASSET",
            _DISRUPTION_ID,
            attrs={"role": "disruption"},
        ),
    ]
    seen = {workflow_id, STORY_ID, _DISRUPTION_ID}

    inbound_sector_id = _append_asset(
        operations,
        seen,
        observation.get("sector"),
        asset_kind="sector",
        workflow_id=workflow_id,
    )
    outbound_sector_id = _append_asset(
        operations,
        seen,
        observation.get("outbound_sector"),
        asset_kind="sector",
        workflow_id=workflow_id,
    )
    for sector in observation.get("sectors") or []:
        _append_asset(
            operations,
            seen,
            sector,
            asset_kind="sector",
            workflow_id=workflow_id,
        )
    inbound_aircraft_id = _append_asset(
        operations,
        seen,
        observation.get("aircraft"),
        asset_kind="aircraft",
        workflow_id=workflow_id,
    )
    outbound_aircraft_id = _append_asset(
        operations,
        seen,
        observation.get("outbound_aircraft"),
        asset_kind="aircraft",
        workflow_id=workflow_id,
    )
    candidate_aircraft_id = _append_asset(
        operations,
        seen,
        observation.get("candidate_aircraft"),
        asset_kind="aircraft",
        workflow_id=workflow_id,
    )
    inbound_crew_id = _append_asset(
        operations,
        seen,
        observation.get("crew_duty"),
        asset_kind="crew-duty",
        workflow_id=workflow_id,
    )
    outbound_crew_id = _append_asset(
        operations,
        seen,
        observation.get("outbound_crew_duty"),
        asset_kind="crew-duty",
        workflow_id=workflow_id,
    )
    candidate_crew_id = _append_asset(
        operations,
        seen,
        observation.get("candidate_crew_duty"),
        asset_kind="crew-duty",
        workflow_id=workflow_id,
    )
    inbound_slot_id = _append_asset(
        operations,
        seen,
        observation.get("slot"),
        asset_kind="slot",
        workflow_id=workflow_id,
    )
    outbound_slot_id = _append_asset(
        operations,
        seen,
        observation.get("outbound_slot"),
        asset_kind="slot",
        workflow_id=workflow_id,
    )
    constrained_stand_id = _append_asset(
        operations,
        seen,
        observation.get("stand"),
        asset_kind="stand",
        workflow_id=workflow_id,
    )
    candidate_stand_id = _append_asset(
        operations,
        seen,
        observation.get("candidate_stand"),
        asset_kind="stand",
        workflow_id=workflow_id,
    )

    operations.extend(
        RelWrite(
            workflow_id,
            "AFFECTS_ASSET",
            actor_id,
            attrs={"role": role},
        )
        for actor_id, role in (
            (inbound_sector_id, "inbound-sector"),
            (outbound_sector_id, "outbound-sector"),
            (inbound_aircraft_id, "inbound-aircraft"),
            (inbound_crew_id, "inbound-crew-duty"),
            (outbound_slot_id, "outbound-slot"),
            (constrained_stand_id, "constrained-stand"),
        )
        if actor_id
    )
    _related(
        operations,
        inbound_sector_id,
        inbound_aircraft_id,
        "operated-by-aircraft",
    )
    _related(
        operations,
        inbound_sector_id,
        inbound_crew_id,
        "operated-by-crew-duty",
    )
    _related(
        operations,
        inbound_sector_id,
        inbound_slot_id,
        "uses-slot",
    )
    _related(
        operations,
        inbound_sector_id,
        constrained_stand_id,
        "uses-stand",
    )
    _related(
        operations,
        outbound_sector_id,
        outbound_aircraft_id,
        "baseline-aircraft",
    )
    _related(
        operations,
        outbound_sector_id,
        outbound_crew_id,
        "baseline-crew-duty",
    )
    _related(
        operations,
        outbound_sector_id,
        outbound_slot_id,
        "uses-slot",
    )
    _related(
        operations,
        outbound_sector_id,
        candidate_aircraft_id,
        "recovered-by-aircraft",
    )
    _related(
        operations,
        outbound_sector_id,
        candidate_crew_id,
        "recovered-by-crew-duty",
    )
    _related(
        operations,
        outbound_sector_id,
        candidate_stand_id,
        "recovered-at-stand",
    )

    for cohort in observation.get("connection_cohorts") or []:
        cohort_id = _append_asset(
            operations,
            seen,
            cohort,
            asset_kind="passenger-connection-cohort",
            workflow_id=workflow_id,
        )
        if not cohort_id:
            continue
        operations.append(
            RelWrite(
                workflow_id,
                "AFFECTS_ASSET",
                cohort_id,
                attrs={"role": "passenger-connection-cohort"},
            )
        )
        _related(
            operations,
            cohort_id,
            str(cohort.get("inbound_sector_id") or ""),
            "arrives-on",
        )
        _related(
            operations,
            cohort_id,
            str(cohort.get("outbound_sector_id") or ""),
            "connects-to",
        )

    command = evidence.get("command")
    approval = evidence.get("approval")
    if not isinstance(command, dict) or not isinstance(approval, dict):
        return operations
    command_payload = command.get("payload") if isinstance(command.get("payload"), dict) else {}
    decision_id = str(approval.get("decision_id") or "")
    command_id = str(command.get("command_id") or "")
    option_id = str(command_payload.get("option_id") or approval.get("selected_option_id") or "")
    evaluation_id = f"SYN-EVAL-{workflow_id}"
    if not decision_id or not command_id or not option_id:
        return operations

    selected_option = (
        (evidence.get("hitl_context") or {}).get("selected_option")
        if isinstance(evidence.get("hitl_context"), dict)
        else {}
    )
    selected_option = selected_option if isinstance(selected_option, dict) else {}
    operations.extend(
        [
            EntityWrite(
                kind="Asset",
                id=option_id,
                attrs={
                    "kind": "recovery-option",
                    "identifier": option_id,
                    "status": "admitted",
                    "attributes": _json(selected_option),
                },
                source_workflows=source_workflows,
            ),
            EntityWrite(
                kind="Decision",
                id=decision_id,
                attrs={
                    "workflow_id": workflow_id,
                    "phase": "Approve Recovery Plan",
                    "persona_role": HITL_PERSONA,
                    "verdict": str(approval.get("decision") or "approve"),
                    "reason": str(approval.get("rationale") or ""),
                    "decided_at": datetime.fromtimestamp(
                        workflow.created_at,
                        tz=timezone.utc,
                    ).isoformat(),
                    "source_event": ("duty_operations_manager_decision"),
                    "attributes": _json(
                        {
                            "option_id": option_id,
                            "story_id": STORY_ID,
                        }
                    ),
                },
                source_workflows=source_workflows,
            ),
            EntityWrite(
                kind="Decision",
                id=command_id,
                attrs={
                    "workflow_id": workflow_id,
                    "phase": "Commit Recovery Actions",
                    "persona_role": HITL_PERSONA,
                    "verdict": "issued",
                    "reason": "Typed Airline recovery command accepted.",
                    "decided_at": datetime.fromtimestamp(
                        workflow.created_at,
                        tz=timezone.utc,
                    ).isoformat(),
                    "source_event": str(
                        (evidence.get("gateway_event") or {}).get(
                            "event_id",
                            "",
                        )
                    ),
                    "attributes": _json(
                        {
                            **command_payload,
                            "kind": "recovery-command",
                            "command_type": command.get("type"),
                        }
                    ),
                },
                source_workflows=source_workflows,
            ),
            EntityWrite(
                kind="Decision",
                id=evaluation_id,
                attrs={
                    "workflow_id": workflow_id,
                    "phase": "Verify Recovery Outcome",
                    "persona_role": "deterministic-evaluator",
                    "verdict": "evaluated",
                    "reason": "Airline world invariants evaluated.",
                    "decided_at": datetime.fromtimestamp(
                        workflow.created_at,
                        tz=timezone.utc,
                    ).isoformat(),
                    "source_event": "airline.recovery.evaluation",
                    "attributes": _json(
                        {
                            "kind": "recovery-evaluation",
                            "option_id": option_id,
                            "command_id": command_id,
                        }
                    ),
                },
                source_workflows=source_workflows,
            ),
            DecisionWrite(
                workflow_id=workflow_id,
                phase="Approve Recovery Plan",
                persona_role=HITL_PERSONA,
                verdict=str(approval.get("decision") or "approve"),
                reason=str(approval.get("rationale") or ""),
                decided_at=datetime.fromtimestamp(
                    workflow.created_at,
                    tz=timezone.utc,
                ).isoformat(),
                source_event="duty_operations_manager_decision",
                attributes={
                    "decision_id": decision_id,
                    "option_id": option_id,
                    "command_id": command_id,
                },
                decided_on=(option_id, outbound_sector_id or ""),
            ),
            RelWrite(decision_id, "DECIDED_ASSET", option_id),
            RelWrite(decision_id, "ISSUED_COMMAND", command_id),
            RelWrite(command_id, "APPROVED_BY", decision_id),
            RelWrite(command_id, "EVALUATED_BY", evaluation_id),
            RelWrite(
                evaluation_id,
                "RESOLVED_OBJECTIVE",
                workflow_id,
            ),
        ]
    )
    return operations

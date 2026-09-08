"""Preemptive Schedule Resilience entity projection.

Projects only observed schedule evidence into typed EntityWrite / RelWrite /
DecisionWrite records.  Absent evidence yields a defensible base Workflow node only.
No fabricated data – every record requires grounded evidence.
"""
from __future__ import annotations

import json
from collections.abc import Generator
from datetime import datetime, timezone
from types import SimpleNamespace
from typing import Any

from api.server.services.entity_graph import DecisionWrite, EntityWrite, RelWrite
from verticals.airline.schedule_constants import (
    SCHED_HITL_PERSONA,
    SCHED_WORKFLOW_TYPE,
)

_SCHED_HITL_EVENT = "network_operations_director_decision"


def _json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, default=str)


def _observation(payload: dict) -> dict | None:
    evidence = payload.get("evidence") or {}
    if isinstance(evidence, dict):
        wfe = evidence.get("workflow_evidence") or {}
        if isinstance(wfe, dict):
            obs = wfe.get("observation")
            if isinstance(obs, dict):
                return obs
        obs = evidence.get("observation")
        if isinstance(obs, dict):
            return obs
    obs = payload.get("observation")
    return obs if isinstance(obs, dict) else None


def _evidence(payload: dict) -> dict:
    ev = payload.get("evidence")
    return ev if isinstance(ev, dict) else {}


def _approval(payload: dict) -> dict | None:
    ev = _evidence(payload)
    ap = ev.get("approval")
    return ap if isinstance(ap, dict) else None


def _mutation_records(payload: dict) -> dict[str, Any]:
    gateway = _evidence(payload).get("gateway_event")
    if not isinstance(gateway, dict):
        return {}
    gateway_payload = gateway.get("payload")
    if not isinstance(gateway_payload, dict):
        return {}
    records = gateway_payload.get("mutation_records")
    return records if isinstance(records, dict) else {}


def _world_scenario(app_state: Any) -> Any | None:
    try:
        return app_state.world_service.scenario
    except AttributeError:
        return None


# ---------------------------------------------------------------------------
# Record projectors
# ---------------------------------------------------------------------------


def _project_risk_signal(
    signal: Any,
    workflow_id: str,
) -> Generator[EntityWrite | RelWrite, None, None]:
    yield EntityWrite(
        kind="Asset",
        id=signal.id,
        attrs={
            "kind": "ScheduleRiskSignal",
            "identifier": signal.id,
            "status": str(signal.status),
            "attributes": _json({
                "scenario_id": signal.scenario_id,
                "story_id": signal.story_id,
                "confidence": signal.confidence,
                "horizon_minutes": signal.horizon_minutes,
                "window_start_minutes": signal.window_start_minutes,
                "window_end_minutes": signal.window_end_minutes,
                "max_cancellations_permitted": signal.max_cancellations_permitted,
            }),
        },
        source_workflows=(workflow_id,),
    )
    yield RelWrite(src_id=workflow_id, rel="TRIGGERED_BY", dst_id=signal.id)


def _project_forecast_constraint(
    constraint: Any,
    workflow_id: str,
) -> Generator[EntityWrite | RelWrite, None, None]:
    yield EntityWrite(
        kind="Asset",
        id=constraint.id,
        attrs={
            "kind": "ForecastConstraint",
            "identifier": constraint.id,
            "status": str(constraint.status),
            "attributes": _json({
                "constraint_type": constraint.constraint_type,
                "station_id": constraint.station_id,
                "capacity_reduction_pct": constraint.capacity_reduction_pct,
                "window_start_minutes": constraint.window_start_minutes,
                "window_end_minutes": constraint.window_end_minutes,
            }),
        },
        source_workflows=(workflow_id,),
    )
    yield RelWrite(
        src_id=workflow_id,
        rel="AFFECTS_ASSET",
        dst_id=constraint.id,
        attrs={"role": "forecast-constraint"},
    )


def _project_schedule_adjustment_command(
    command: Any,
    workflow_id: str,
) -> Generator[EntityWrite | RelWrite, None, None]:
    yield EntityWrite(
        kind="Asset",
        id=command.id,
        attrs={
            "kind": "ScheduleAdjustmentCommand",
            "identifier": command.id,
            "status": "committed",
            "attributes": _json({
                "option_id": command.option_id,
                "persona": command.persona,
                "value_gbp": command.value_gbp,
                "action_types": list(command.action_types),
            }),
        },
        source_workflows=(workflow_id,),
    )
    yield RelWrite(
        src_id=workflow_id,
        rel="AFFECTS_ASSET",
        dst_id=command.id,
        attrs={"role": "schedule-adjustment-command"},
    )


def _project_resilience_evaluation(
    evaluation: Any,
    workflow_id: str,
    command_id: str | None,
) -> Generator[EntityWrite | RelWrite, None, None]:
    yield EntityWrite(
        kind="Asset",
        id=evaluation.id,
        attrs={
            "kind": "ScheduleResilienceEvaluation",
            "identifier": evaluation.id,
            "status": str(evaluation.status),
            "attributes": _json({
                "option_id": evaluation.option_id,
                "predicted_delay_reduction_minutes": evaluation.predicted_delay_reduction_minutes,
                "cancellations_reduced": evaluation.cancellations_reduced,
                "aircraft_feasibility_restored": evaluation.aircraft_feasibility_restored,
                "crew_feasibility_restored": evaluation.crew_feasibility_restored,
                "slot_feasibility_restored": evaluation.slot_feasibility_restored,
                "protected_cohorts": evaluation.protected_cohorts,
                "capacity_retained_pct": evaluation.capacity_retained_pct,
                "synthetic_cost_gbp": evaluation.synthetic_cost_gbp,
                "forecast_confidence": evaluation.forecast_confidence,
                "false_positive_exposure": evaluation.false_positive_exposure,
                "selected_action": evaluation.selected_action,
            }),
        },
        source_workflows=(workflow_id,),
    )
    yield RelWrite(
        src_id=workflow_id,
        rel="AFFECTS_ASSET",
        dst_id=evaluation.id,
        attrs={"role": "schedule-resilience-evaluation"},
    )
    if command_id:
        yield RelWrite(
            src_id=evaluation.id,
            rel="RELATED_ASSET",
            dst_id=command_id,
            attrs={"role": "evaluates-command"},
        )


def _project_sector(
    sector_dict: dict,
    workflow_id: str,
) -> Generator[EntityWrite | RelWrite, None, None]:
    sector_id = sector_dict.get("id")
    if not sector_id:
        return
    yield EntityWrite(
        kind="Asset",
        id=sector_id,
        attrs={
            "kind": "Sector",
            "identifier": sector_id,
            "status": str(sector_dict.get("status") or ""),
            "attributes": _json({
                "origin_id": sector_dict.get("origin_id"),
                "destination_id": sector_dict.get("destination_id"),
                "aircraft_id": sector_dict.get("aircraft_id"),
                "crew_duty_id": sector_dict.get("crew_duty_id"),
                "slot_id": sector_dict.get("slot_id"),
                "delay_minutes": sector_dict.get("delay_minutes"),
            }),
        },
        source_workflows=(workflow_id,),
    )
    yield RelWrite(
        src_id=workflow_id,
        rel="AFFECTS_ASSET",
        dst_id=sector_id,
        attrs={"role": "affected-sector"},
    )


def _project_asset(
    asset_id: str,
    kind: str,
    attrs: dict,
    workflow_id: str,
) -> Generator[EntityWrite | RelWrite, None, None]:
    yield EntityWrite(
        kind="Asset",
        id=asset_id,
        attrs={
            "kind": kind,
            "identifier": asset_id,
            "status": str(attrs.get("status") or ""),
            "attributes": _json(attrs),
        },
        source_workflows=(workflow_id,),
    )
    yield RelWrite(
        src_id=workflow_id,
        rel="AFFECTS_ASSET",
        dst_id=asset_id,
        attrs={"role": kind.lower()},
    )


# ---------------------------------------------------------------------------
# Main projection entry point
# ---------------------------------------------------------------------------


def project(
    workflow: Any,
    app_state: Any = None,
) -> Generator[EntityWrite | RelWrite | DecisionWrite, None, None]:
    """Yield entity graph writes grounded in observed schedule evidence."""
    payload = workflow.payload if isinstance(workflow.payload, dict) else {}
    workflow_id = workflow.id

    # Always emit a Workflow node.
    yield EntityWrite(
        kind="Workflow",
        id=workflow_id,
        attrs={
            "workflow_type": SCHED_WORKFLOW_TYPE,
            "status": str(getattr(workflow, "status", "unknown")),
        },
        source_workflows=(workflow_id,),
    )

    obs = _observation(payload)
    if obs is None:
        # No observation evidence – still check world scenario below.
        pass
    else:
        # Risk signal
        risk_signal = obs.get("risk_signal")
        if isinstance(risk_signal, dict) and risk_signal.get("id"):
            sig_id = risk_signal["id"]
            yield EntityWrite(
                kind="Asset",
                id=sig_id,
                attrs={
                    "kind": "ScheduleRiskSignal",
                    "identifier": sig_id,
                    "status": str(risk_signal.get("status") or "detected"),
                    "attributes": _json({
                        "story_id": risk_signal.get("story_id"),
                        "confidence": risk_signal.get("confidence"),
                        "horizon_minutes": risk_signal.get("horizon_minutes"),
                        "window_start_minutes": risk_signal.get("window_start_minutes"),
                        "window_end_minutes": risk_signal.get("window_end_minutes"),
                        "max_cancellations_permitted": risk_signal.get("max_cancellations_permitted"),
                    }),
                },
                source_workflows=(workflow_id,),
            )
            yield RelWrite(src_id=workflow_id, rel="TRIGGERED_BY", dst_id=sig_id)

        # Forecast constraints
        for fc in obs.get("forecast_constraints") or []:
            if not isinstance(fc, dict) or not fc.get("id"):
                continue
            fc_id = fc["id"]
            yield EntityWrite(
                kind="Asset",
                id=fc_id,
                attrs={
                    "kind": "ForecastConstraint",
                    "identifier": fc_id,
                    "status": str(fc.get("status") or "forecast"),
                    "attributes": _json({
                        "constraint_type": fc.get("constraint_type"),
                        "station_id": fc.get("station_id"),
                        "capacity_reduction_pct": fc.get("capacity_reduction_pct"),
                    }),
                },
                source_workflows=(workflow_id,),
            )
            yield RelWrite(
                src_id=workflow_id,
                rel="AFFECTS_ASSET",
                dst_id=fc_id,
                attrs={"role": "forecast-constraint"},
            )

        # Affected sectors
        for sector in obs.get("affected_sectors") or []:
            yield from _project_sector(sector, workflow_id)

        # Affected crew
        for crew in obs.get("affected_crew") or []:
            if not isinstance(crew, dict) or not crew.get("id"):
                continue
            yield from _project_asset(
                crew["id"], "CrewDuty",
                {"status": crew.get("status")},
                workflow_id,
            )

        # Affected aircraft
        for aircraft in obs.get("affected_aircraft") or []:
            if not isinstance(aircraft, dict) or not aircraft.get("id"):
                continue
            yield from _project_asset(
                aircraft["id"], "Aircraft",
                {"status": aircraft.get("status"), "configuration": aircraft.get("configuration")},
                workflow_id,
            )

        # Reserve aircraft
        reserve_ac = obs.get("reserve_aircraft")
        if isinstance(reserve_ac, dict) and reserve_ac.get("id"):
            yield from _project_asset(
                reserve_ac["id"], "Aircraft",
                {"status": reserve_ac.get("status"), "kind": "reserve"},
                workflow_id,
            )

        # Reserve crew
        reserve_crew = obs.get("reserve_crew")
        if isinstance(reserve_crew, dict) and reserve_crew.get("id"):
            yield from _project_asset(
                reserve_crew["id"], "CrewDuty",
                {"status": reserve_crew.get("status"), "kind": "reserve"},
                workflow_id,
            )

    # ------------------------------------------------------------------
    # Payload-level evidence: command node
    # ------------------------------------------------------------------
    ev = _evidence(payload)
    mutation_records = _mutation_records(payload)
    cmd = ev.get("command")
    command_id: str | None = None
    persisted_command = mutation_records.get("schedule_command")
    if isinstance(persisted_command, dict) and persisted_command.get("id"):
        command_id = str(persisted_command["id"])
        yield from _project_schedule_adjustment_command(
            SimpleNamespace(**persisted_command),
            workflow_id,
        )
    elif isinstance(cmd, dict) and cmd.get("command_id"):
        command_id = cmd["command_id"]
        command_payload = (
            cmd.get("payload")
            if isinstance(cmd.get("payload"), dict)
            else {}
        )
        yield EntityWrite(
            kind="Asset",
            id=command_id,
            attrs={
                "kind": "ScheduleAdjustmentCommand",
                "identifier": command_id,
                "status": "committed",
                "attributes": _json({
                    "command_type": cmd.get("type"),
                    "option_id": command_payload.get("option_id"),
                    "value_gbp": command_payload.get("value_gbp"),
                    "workflow_id": workflow_id,
                }),
            },
            source_workflows=(workflow_id,),
        )
        yield RelWrite(
            src_id=workflow_id,
            rel="AFFECTS_ASSET",
            dst_id=command_id,
            attrs={"role": "schedule-adjustment-command"},
        )

    persisted_evaluation = mutation_records.get("evaluation")
    if isinstance(persisted_evaluation, dict) and persisted_evaluation.get("id"):
        yield from _project_resilience_evaluation(
            SimpleNamespace(**persisted_evaluation),
            workflow_id,
            command_id,
        )

    # ------------------------------------------------------------------
    # World-record projection: live AirlineWorld state
    # ------------------------------------------------------------------
    scenario = _world_scenario(app_state)
    if not mutation_records and scenario is not None:
        # ScheduleAdjustmentCommands for this workflow
        for sac in getattr(scenario, "schedule_adjustment_commands", {}).values():
            if sac.workflow_id != workflow_id:
                continue
            yield from _project_schedule_adjustment_command(sac, workflow_id)

        # ScheduleResilienceEvaluations for this workflow
        for evaluation in getattr(scenario, "schedule_resilience_evaluations", {}).values():
            if evaluation.workflow_id != workflow_id:
                continue
            cmd_id = evaluation.command_id if evaluation.command_id else command_id
            yield from _project_resilience_evaluation(evaluation, workflow_id, cmd_id)

    # ------------------------------------------------------------------
    # Decision record from approval evidence in payload
    # ------------------------------------------------------------------
    approval = _approval(payload)
    if approval and approval.get("decision"):
        yield DecisionWrite(
            workflow_id=workflow_id,
            phase="Approve Schedule Adjustment",
            persona_role=approval.get("persona") or SCHED_HITL_PERSONA,
            verdict=str(approval["decision"]),
            reason=str(approval.get("rationale") or ""),
            decided_at=str(
                approval.get("decided_at")
                or datetime.fromtimestamp(
                    float(getattr(workflow, "created_at", 0.0)),
                    tz=timezone.utc,
                ).isoformat()
            ),
            source_event=_SCHED_HITL_EVENT,
            attributes={"decision_id": approval.get("decision_id") or ""},
        )

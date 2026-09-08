"""AOG Engineering Recovery entity projection.

Projects only observed AOG evidence into typed EntityWrite / RelWrite /
DecisionWrite records.  Absent evidence yields defensible base records only.
No fabricated data – every record requires grounded evidence.
"""
from __future__ import annotations

import dataclasses
import json
from collections.abc import Generator
from datetime import datetime, timezone
from types import SimpleNamespace
from typing import Any

from api.server.services.entity_graph import DecisionWrite, EntityWrite, RelWrite
from verticals.airline.aog_constants import AOG_HITL_EVENT, AOG_HITL_PERSONA, AOG_WORKFLOW_TYPE


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


def _approval(payload: dict) -> dict | None:
    evidence = payload.get("evidence") or {}
    if isinstance(evidence, dict):
        ap = evidence.get("approval")
        if isinstance(ap, dict):
            return ap
    return None


def _mutation_records(payload: dict) -> dict[str, Any]:
    evidence = payload.get("evidence")
    if not isinstance(evidence, dict):
        return {}
    gateway = evidence.get("gateway_event")
    if not isinstance(gateway, dict):
        return {}
    gateway_payload = gateway.get("payload")
    if not isinstance(gateway_payload, dict):
        return {}
    records = gateway_payload.get("mutation_records")
    return records if isinstance(records, dict) else {}


def _world_scenario(app_state: Any) -> Any | None:
    """Return the AirlineWorld scenario from app_state, or None if unavailable."""
    try:
        return app_state.world_service.scenario
    except AttributeError:
        return None


# ---------------------------------------------------------------------------
# World-record projectors
# ---------------------------------------------------------------------------

def _project_spare(
    spare: Any,
    workflow_id: str,
) -> Generator[EntityWrite | RelWrite, None, None]:
    """Yield EntityWrite for a Spare model record."""
    yield EntityWrite(
        kind="Asset",
        id=spare.id,
        attrs={
            "kind": "Spare",
            "identifier": spare.id,
            "status": str(spare.status),
            "attributes": _json({
                "part_number": spare.part_number,
                "traceable": spare.traceable,
                "station_id": spare.station_id,
                "lead_time_minutes": spare.lead_time_minutes,
            }),
        },
        source_workflows=(workflow_id,),
    )


def _project_spare_movement(
    movement: Any,
    workflow_id: str,
) -> Generator[EntityWrite | RelWrite, None, None]:
    """Yield EntityWrite + rels for a SpareMovement model record."""
    yield EntityWrite(
        kind="Asset",
        id=movement.id,
        attrs={
            "kind": "SpareMovement",
            "identifier": movement.id,
            "status": str(movement.status),
            "attributes": _json({
                "spare_id": movement.spare_id,
                "from_station_id": movement.from_station_id,
                "to_station_id": movement.to_station_id,
            }),
        },
        source_workflows=(workflow_id,),
    )
    yield RelWrite(
        src_id=workflow_id,
        rel="AFFECTS_ASSET",
        dst_id=movement.id,
        attrs={"role": "spare-movement"},
    )
    if movement.spare_id:
        yield RelWrite(
            src_id=movement.id,
            rel="RELATED_ASSET",
            dst_id=movement.spare_id,
            attrs={"role": "moves-spare"},
        )


def _project_engineering_work_order(
    wo: Any,
    workflow_id: str,
) -> Generator[EntityWrite | RelWrite, None, None]:
    """Yield EntityWrite + rels for an EngineeringWorkOrder model record."""
    yield EntityWrite(
        kind="Asset",
        id=wo.id,
        attrs={
            "kind": "EngineeringWorkOrder",
            "identifier": wo.id,
            "status": str(wo.status),
            "attributes": _json({
                "provider_id": wo.provider_id,
                "maintenance_task_id": wo.maintenance_task_id,
                "technical_status_id": wo.technical_status_id,
                "spare_id": wo.spare_id,
            }),
        },
        source_workflows=(workflow_id,),
    )
    yield RelWrite(
        src_id=workflow_id,
        rel="AFFECTS_ASSET",
        dst_id=wo.id,
        attrs={"role": "engineering-work-order"},
    )
    if wo.spare_id:
        yield RelWrite(
            src_id=wo.spare_id,
            rel="RELATED_ASSET",
            dst_id=wo.id,
            attrs={"role": "fulfils-work-order"},
        )


def _project_aog_recovery_evaluation(
    evaluation: Any,
    workflow_id: str,
    command_id: str | None,
) -> Generator[EntityWrite | RelWrite, None, None]:
    """Yield EntityWrite + rels for an AogRecoveryEvaluation model record."""
    yield EntityWrite(
        kind="Asset",
        id=evaluation.id,
        attrs={
            "kind": "AogRecoveryEvaluation",
            "identifier": evaluation.id,
            "status": str(evaluation.status),
            "attributes": _json({
                "option_id": evaluation.option_id,
                "invariant_results": list(evaluation.invariant_results),
                "sectors_protected": evaluation.sectors_protected,
                "projected_aog_duration_minutes": evaluation.projected_aog_duration_minutes,
                "spare_lead_time_minutes": evaluation.spare_lead_time_minutes,
                "approved_provider_coverage": evaluation.approved_provider_coverage,
                "synthetic_recovery_cost_gbp": evaluation.synthetic_recovery_cost_gbp,
                "aircraft_released_by_ai": evaluation.aircraft_released_by_ai,
            }),
        },
        source_workflows=(workflow_id,),
    )
    yield RelWrite(
        src_id=workflow_id,
        rel="AFFECTS_ASSET",
        dst_id=evaluation.id,
        attrs={"role": "recovery-evaluation"},
    )
    if command_id:
        yield RelWrite(
            src_id=evaluation.id,
            rel="RELATED_ASSET",
            dst_id=command_id,
            attrs={"role": "evaluates-command"},
        )


# ---------------------------------------------------------------------------
# Main projection entry point
# ---------------------------------------------------------------------------

def project(
    workflow: Any,
    _app_state: Any = None,
) -> Generator[EntityWrite | RelWrite | DecisionWrite, None, None]:
    """Yield entity graph writes grounded in observed workflow evidence."""
    payload = workflow.payload if isinstance(workflow.payload, dict) else {}
    workflow_id = workflow.id

    # Always emit a Workflow node.
    yield EntityWrite(
        kind="Workflow",
        id=workflow_id,
        attrs={
            "workflow_type": AOG_WORKFLOW_TYPE,
            "status": str(getattr(workflow, "status", "unknown")),
        },
        source_workflows=(workflow_id,),
    )

    obs = _observation(payload)
    if obs is None:
        # No observation evidence – still check for world records below.
        pass
    else:
        tail_id = obs.get("affected_tail_id")
        if tail_id:
            yield EntityWrite(
                kind="Asset",
                id=tail_id,
                attrs={
                    "kind": "Aircraft",
                    "identifier": tail_id,
                    "status": "aog",
                    "attributes": _json({"tail_id": tail_id}),
                },
                source_workflows=(workflow_id,),
            )
            yield RelWrite(
                src_id=workflow_id,
                rel="AFFECTS_ASSET",
                dst_id=tail_id,
                attrs={"role": "affected-aircraft"},
            )

        tech = obs.get("technical_status")
        if isinstance(tech, dict) and tech.get("id"):
            tech_id = tech["id"]
            yield EntityWrite(
                kind="Asset",
                id=tech_id,
                attrs={
                    "kind": "TechnicalStatus",
                    "identifier": tech_id,
                    "status": str(tech.get("status") or ""),
                    "attributes": _json(tech),
                },
                source_workflows=(workflow_id,),
            )
            if tail_id:
                yield RelWrite(
                    src_id=tail_id,
                    rel="RELATED_ASSET",
                    dst_id=tech_id,
                    attrs={"role": "technical-status"},
                )

        task = obs.get("maintenance_task")
        if isinstance(task, dict) and task.get("id"):
            task_id = task["id"]
            yield EntityWrite(
                kind="Asset",
                id=task_id,
                attrs={
                    "kind": "MaintenanceTask",
                    "identifier": task_id,
                    "status": str(task.get("status") or ""),
                    "attributes": _json(task),
                },
                source_workflows=(workflow_id,),
            )
            if tail_id:
                yield RelWrite(
                    src_id=tail_id,
                    rel="RELATED_ASSET",
                    dst_id=task_id,
                    attrs={"role": "requires-maintenance-task"},
                )

        for provider in obs.get("approved_providers") or []:
            if not isinstance(provider, dict) or not provider.get("id"):
                continue
            prov_id = provider["id"]
            yield EntityWrite(
                kind="Asset",
                id=prov_id,
                attrs={
                    "kind": "ApprovedProvider",
                    "identifier": prov_id,
                    "status": str(provider.get("status") or ""),
                    "attributes": _json(provider),
                },
                source_workflows=(workflow_id,),
            )
            yield RelWrite(
                src_id=workflow_id,
                rel="AFFECTS_ASSET",
                dst_id=prov_id,
                attrs={"role": "engineering-provider"},
            )

    # ------------------------------------------------------------------
    # World-record projection: prefer live AirlineWorld state keyed by
    # workflow_id; do NOT fabricate records that are absent.
    # ------------------------------------------------------------------
    mutation_records = _mutation_records(payload)
    if mutation_records:
        command_data = mutation_records.get("aog_command")
        command_id = None
        if isinstance(command_data, dict) and command_data.get("id"):
            command_id = str(command_data["id"])
            yield EntityWrite(
                kind="Asset",
                id=command_id,
                attrs={
                    "kind": "AogRecoveryCommand",
                    "identifier": command_id,
                    "status": "accepted",
                    "attributes": _json(command_data),
                },
                source_workflows=(workflow_id,),
            )
            yield RelWrite(
                src_id=workflow_id,
                rel="AFFECTS_ASSET",
                dst_id=command_id,
                attrs={"role": "recovery-command"},
            )

        work_order_data = mutation_records.get("work_order")
        spare_data = mutation_records.get("spare")
        if isinstance(spare_data, dict) and spare_data.get("id"):
            spare = SimpleNamespace(**spare_data)
            yield from _project_spare(spare, workflow_id)
        if isinstance(work_order_data, dict) and work_order_data.get("id"):
            yield from _project_engineering_work_order(
                SimpleNamespace(**work_order_data),
                workflow_id,
            )
        if isinstance(spare_data, dict) and spare_data.get("id"):
            task_id = (
                work_order_data.get("maintenance_task_id")
                if isinstance(work_order_data, dict)
                else None
            )
            if task_id and obs is not None:
                yield RelWrite(
                    src_id=spare.id,
                    rel="RELATED_ASSET",
                    dst_id=task_id,
                    attrs={"role": "spare-for-maintenance-task"},
                )

        movement_data = mutation_records.get("spare_movement")
        if isinstance(movement_data, dict) and movement_data.get("id"):
            yield from _project_spare_movement(
                SimpleNamespace(**movement_data),
                workflow_id,
            )

        evaluation_data = mutation_records.get("evaluation")
        if isinstance(evaluation_data, dict) and evaluation_data.get("id"):
            yield from _project_aog_recovery_evaluation(
                SimpleNamespace(**evaluation_data),
                workflow_id,
                command_id,
            )

    scenario = _world_scenario(_app_state)
    if not mutation_records and scenario is not None:
        for command in scenario.aog_recovery_commands.values():
            if command.workflow_id != workflow_id:
                continue
            yield EntityWrite(
                kind="Asset",
                id=command.id,
                attrs={
                    "kind": "AogRecoveryCommand",
                    "identifier": command.id,
                    "status": "accepted",
                    "attributes": _json(dataclasses.asdict(command)),
                },
                source_workflows=(workflow_id,),
            )
            yield RelWrite(
                src_id=workflow_id,
                rel="AFFECTS_ASSET",
                dst_id=command.id,
                attrs={"role": "recovery-command"},
            )

        # EngineeringWorkOrders for this workflow
        for wo in scenario.engineering_work_orders.values():
            if wo.workflow_id != workflow_id:
                continue
            # Spare used by this work order
            if wo.spare_id and wo.spare_id in scenario.spares:
                spare = scenario.spares[wo.spare_id]
                yield from _project_spare(spare, workflow_id)
            yield from _project_engineering_work_order(wo, workflow_id)
            if wo.spare_id and wo.spare_id in scenario.spares:
                # Relate spare to its work order (defensible: spare fulfils the task)
                task_id_from_obs = (
                    (obs.get("maintenance_task") or {}).get("id") if obs else None
                )
                if task_id_from_obs:
                    yield RelWrite(
                        src_id=spare.id,
                        rel="RELATED_ASSET",
                        dst_id=task_id_from_obs,
                        attrs={"role": "spare-for-maintenance-task"},
                    )

        # SpareMovements for this workflow
        for movement in scenario.spare_movements.values():
            if movement.workflow_id != workflow_id:
                continue
            yield from _project_spare_movement(movement, workflow_id)

        # AogRecoveryEvaluations for this workflow
        for evaluation in scenario.aog_recovery_evaluations.values():
            if evaluation.workflow_id != workflow_id:
                continue
            command_id = evaluation.command_id if evaluation.command_id else None
            yield from _project_aog_recovery_evaluation(evaluation, workflow_id, command_id)

    # ------------------------------------------------------------------
    # Decision record from approval evidence in payload
    # ------------------------------------------------------------------
    evidence = payload.get("evidence") or {}
    if isinstance(evidence, dict):
        approval = evidence.get("approval")
        if isinstance(approval, dict) and approval.get("decision"):
            yield DecisionWrite(
                workflow_id=workflow_id,
                phase="Approve Engineering Recovery",
                persona_role=approval.get("persona") or AOG_HITL_PERSONA,
                verdict=str(approval["decision"]),
                reason=str(approval.get("rationale") or ""),
                decided_at=str(
                    approval.get("decided_at")
                    or datetime.fromtimestamp(
                        float(getattr(workflow, "created_at", 0.0)),
                        tz=timezone.utc,
                    ).isoformat()
                ),
                source_event=AOG_HITL_EVENT,
                attributes={"decision_id": approval.get("decision_id") or ""},
            )

from __future__ import annotations

import asyncio
import json
import math
import os
from pathlib import Path
from typing import Any


_SKILL_ROOT = Path(__file__).resolve().parents[3] / "verticals" / "telco" / "skills"
_SKILL_BY_WORKFLOW = {
    "outage-risk-management": "outage-risk-planning",
    "predictive-site-maintenance": "site-failure-diagnosis",
    "field-repair-dispatch": "field-resource-matching",
    "capacity-optimization": "capacity-action-planner",
    "service-ticket-resolution": "ticket-root-cause-correlation",
    "retention-orchestration": "retention-offer-selection",
}


async def run_agent_session(prompt: str, **kwargs) -> dict[str, Any]:
    from api.functions.graphs.executors.agents._wrapper import (
        run_agent_session as run,
    )

    return await run(prompt, **kwargs)


def _require_dict(value: Any, *, label: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ValueError(f"{label} must be an object")
    return value


def _require_choice(value: Any, choices: set[str], *, label: str) -> str:
    if not isinstance(value, str) or value not in choices:
        raise ValueError(f"{label} must be one of {sorted(choices)}")
    return value


def _require_selection(
    values: Any,
    available: set[str],
    *,
    label: str,
) -> list[str]:
    if not isinstance(values, list) or not values:
        raise ValueError(f"{label} must be a non-empty list")
    selected = [str(value) for value in values]
    invalid = sorted(set(selected) - available)
    if invalid:
        raise ValueError(f"{label} contains unavailable values: {invalid}")
    return selected


def _deterministic_selection(payload: dict[str, Any]) -> dict[str, Any]:
    workflow_type = str(payload.get("type") or "")
    observation = _require_dict(payload.get("observation"), label="observation")
    if workflow_type == "outage-risk-management":
        technician_ids = sorted(
            str(item["id"])
            for item in observation.get("available_technicians") or []
            if isinstance(item, dict) and item.get("id")
        )[:2]
        spare_part_kinds = sorted(
            str(item["part_kind"])
            for item in observation.get("spare_stocks") or []
            if isinstance(item, dict)
            and item.get("part_kind")
            and int(item.get("quantity") or 0) > 0
        )[:2]
        return {
            "technician_ids": technician_ids,
            "spare_part_kinds": spare_part_kinds,
            "reasoning": "Pre-stage the smallest available regional resource set.",
        }
    if workflow_type == "predictive-site-maintenance":
        asset = _require_dict(observation.get("asset"), label="asset")
        critical = asset.get("risk_band") == "critical" or float(
            asset.get("failure_probability") or 0.0
        ) >= 0.8
        return {
            "kind": "replace" if critical else "repair",
            "priority": 1 if critical else 2,
            "reasoning": "Use risk severity to choose repair urgency and scope.",
        }
    if workflow_type == "field-repair-dispatch":
        technicians = sorted(
            str(item["id"])
            for item in observation.get("dispatchable_technicians") or []
            if isinstance(item, dict) and item.get("id")
        )
        work_order = _require_dict(
            observation.get("work_order"),
            label="work_order",
        )
        required_spare = str(work_order.get("required_spare") or "")
        local_stock = _require_dict(
            observation.get("spare_stock"),
            label="spare_stock",
        )
        source_stock_id = None
        if (
            local_stock.get("part_kind") == required_spare
            and int(local_stock.get("quantity") or 0) > 0
        ):
            source_stock_id = local_stock.get("id")
        else:
            alternatives = sorted(
                (
                    item
                    for item in observation.get("alternate_spare_stocks") or []
                    if isinstance(item, dict)
                    and item.get("part_kind") == required_spare
                    and int(item.get("quantity") or 0) > 0
                ),
                key=lambda item: str(item.get("id")),
            )
            if alternatives:
                source_stock_id = alternatives[0].get("id")
        return {
            "technician_id": technicians[0] if technicians else None,
            "source_stock_id": source_stock_id,
            "action": work_order.get("kind"),
            "reasoning": "Dispatch the first feasible technician and nearest stocked part.",
        }
    if workflow_type == "capacity-optimization":
        site = _require_dict(observation.get("site"), label="site")
        return {
            "action": (
                "capital_augmentation"
                if float(site.get("utilization") or 0.0) >= 0.98
                else "temporary_capacity"
            ),
            "reasoning": "Restore safe headroom with the least permanent action.",
        }
    raise ValueError(f"unsupported Telco cascade workflow: {workflow_type!r}")


async def _live_selection(payload: dict[str, Any]) -> dict[str, Any]:
    workflow_type = str(payload.get("type") or "")
    skill = _SKILL_BY_WORKFLOW.get(workflow_type)
    if skill is None:
        raise ValueError(f"unsupported Telco cascade workflow: {workflow_type!r}")
    prompt = (
        "Return one JSON object only. Select a feasible action using only the "
        "supplied simulated observation. Do not invent actor IDs.\n"
        f"workflow_type={workflow_type}\n"
        f"phase={payload.get('phase')}\n"
        f"observation={json.dumps(payload.get('observation') or {}, sort_keys=True)}"
    )
    result = await run_agent_session(
        prompt,
        skill_dir=_SKILL_ROOT / skill,
        skill_label=skill,
        workflow_id=payload.get("workflow_id"),
    )
    return _require_dict(result, label="agent response")


def _outage_response(
    payload: dict[str, Any],
    selection: dict[str, Any],
) -> dict[str, Any]:
    observation = _require_dict(payload.get("observation"), label="observation")
    weather = _require_dict(observation.get("weather_event"), label="weather_event")
    available_technicians = {
        str(item["id"])
        for item in observation.get("available_technicians") or []
        if isinstance(item, dict) and item.get("id")
    }
    available_spares = {
        str(item["part_kind"])
        for item in observation.get("spare_stocks") or []
        if isinstance(item, dict)
        and item.get("part_kind")
        and int(item.get("quantity") or 0) > 0
    }
    technician_ids = _require_selection(
        selection.get("technician_ids"),
        available_technicians,
        label="technician_ids",
    )
    spare_part_kinds = _require_selection(
        selection.get("spare_part_kinds"),
        available_spares,
        label="spare_part_kinds",
    )
    estimated_cost = 1_500.0 * len(technician_ids) + 2_500.0 * len(
        spare_part_kinds
    )
    if float(weather.get("severity") or 0.0) >= 1.5:
        estimated_cost += 5_000.0
    return _response(
        payload,
        command_type="prestage_field_resources",
        issued_by="network_operations",
        command_payload={
            "region": weather["region"],
            "technician_ids": technician_ids,
            "spare_part_kinds": spare_part_kinds,
            "estimated_cost_gbp": estimated_cost,
        },
        reasoning=str(selection.get("reasoning") or "Regional resources selected."),
        requires_approval=estimated_cost > 10_000.0,
        approval_amount=estimated_cost,
        approval_action="delivery_lead_decision",
    )


def _maintenance_response(
    payload: dict[str, Any],
    selection: dict[str, Any],
) -> dict[str, Any]:
    observation = _require_dict(payload.get("observation"), label="observation")
    asset = _require_dict(observation.get("asset"), label="asset")
    kind = _require_choice(
        selection.get("kind"),
        {"repair", "replace"},
        label="kind",
    )
    priority = selection.get("priority")
    if isinstance(priority, bool) or not isinstance(priority, int):
        raise ValueError("priority must be an integer")
    if not 1 <= priority <= 5:
        raise ValueError("priority must be between 1 and 5")
    estimated_cost = 12_000.0 if kind == "replace" else 2_500.0
    return _response(
        payload,
        command_type="create_maintenance_work_order",
        issued_by="network_operations",
        command_payload={
            "asset_id": asset["id"],
            "kind": kind,
            "priority": priority,
            "estimated_cost_gbp": estimated_cost,
        },
        reasoning=str(selection.get("reasoning") or "Maintenance action selected."),
        requires_approval=kind == "replace",
        approval_amount=estimated_cost,
        approval_action="delivery_lead_decision",
    )


def _field_response(
    payload: dict[str, Any],
    selection: dict[str, Any],
) -> dict[str, Any]:
    observation = _require_dict(payload.get("observation"), label="observation")
    work_order = _require_dict(
        observation.get("work_order"),
        label="work_order",
    )
    site = _require_dict(observation.get("site"), label="site")
    technician_ids = {
        str(item["id"])
        for item in observation.get("dispatchable_technicians") or []
        if isinstance(item, dict) and item.get("id")
    }
    technician_id = _require_choice(
        selection.get("technician_id"),
        technician_ids,
        label="technician_id",
    )
    stock_options = [
        observation.get("spare_stock"),
        *(observation.get("alternate_spare_stocks") or []),
    ]
    stocks_by_id = {
        str(item["id"]): item
        for item in stock_options
        if isinstance(item, dict)
        and item.get("id")
        and int(item.get("quantity") or 0) > 0
    }
    source_stock_id = _require_choice(
        selection.get("source_stock_id"),
        set(stocks_by_id),
        label="source_stock_id",
    )
    action = _require_choice(
        selection.get("action"),
        {"repair", "replace"},
        label="action",
    )
    cross_region = stocks_by_id[source_stock_id].get("region") != site.get("region")
    return _response(
        payload,
        command_type="dispatch_field_repair",
        issued_by="network_operations",
        command_payload={
            "work_order_id": work_order["id"],
            "technician_id": technician_id,
            "source_stock_id": source_stock_id,
            "action": action,
            "cross_region_exception": cross_region,
        },
        reasoning=str(selection.get("reasoning") or "Field resources matched."),
        requires_approval=cross_region,
        approval_amount=3_500.0 if cross_region else 0.0,
        approval_action="delivery_lead_decision",
    )


def _capacity_response(
    payload: dict[str, Any],
    selection: dict[str, Any],
) -> dict[str, Any]:
    observation = _require_dict(payload.get("observation"), label="observation")
    site = _require_dict(observation.get("site"), label="site")
    action = _require_choice(
        selection.get("action"),
        {
            "traffic_rebalance",
            "temporary_capacity",
            "capital_augmentation",
        },
        label="action",
    )
    traffic = float(site["traffic_mbps"])
    capacity = float(site["capacity_mbps"])
    increase = max(1.0, traffic / 0.8 - capacity)
    increase = math.ceil(increase * 1_000.0) / 1_000.0
    estimated_cost = 40_000.0 if action == "capital_augmentation" else 8_000.0
    return _response(
        payload,
        command_type="apply_capacity_action",
        issued_by="network_operations",
        command_payload={
            "site_id": site["id"],
            "action": action,
            "capacity_increase_mbps": increase,
            "estimated_cost_gbp": estimated_cost,
        },
        reasoning=str(selection.get("reasoning") or "Capacity action selected."),
        requires_approval=action == "capital_augmentation",
        approval_amount=estimated_cost,
        approval_action="network_ops_director_decision",
    )


def _response(
    payload: dict[str, Any],
    *,
    command_type: str,
    issued_by: str,
    command_payload: dict[str, Any],
    reasoning: str,
    requires_approval: bool,
    approval_amount: float,
    approval_action: str,
) -> dict[str, Any]:
    trace_id = str(payload.get("trace_id") or "unknown")
    return {
        "command": {
            "command_id": f"cmd-{trace_id}-{command_type}",
            "trace_id": trace_id,
            "issued_by": issued_by,
            "type": command_type,
            "payload": command_payload,
        },
        "requires_approval": requires_approval,
        "approval_context": {
            "action": approval_action,
            "request": {
                "amount": approval_amount,
                "category": command_type,
            },
        },
        "reasoning": reasoning,
    }


_RESPONSE_BUILDERS = {
    "outage-risk-management": _outage_response,
    "predictive-site-maintenance": _maintenance_response,
    "field-repair-dispatch": _field_response,
    "capacity-optimization": _capacity_response,
}


def telco_cascade_decision(payload: dict[str, Any]) -> dict[str, Any]:
    workflow_type = str(payload.get("type") or "")
    mode = payload.get("agent_mode") or os.environ.get(
        "ZAVA_TELCO_AGENT_MODE",
        "live",
    )
    if mode == "deterministic":
        selection = _deterministic_selection(payload)
    elif mode == "live":
        selection = asyncio.run(_live_selection(payload))
    else:
        raise ValueError(f"unsupported agent_mode: {mode!r}")
    builder = _RESPONSE_BUILDERS.get(workflow_type)
    if builder is None:
        raise ValueError(f"unsupported Telco cascade workflow: {workflow_type!r}")
    return builder(payload, selection)

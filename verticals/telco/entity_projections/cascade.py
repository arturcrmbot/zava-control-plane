from __future__ import annotations

import json
from typing import Any

from api.server.services.entity_projections import EntityWrite, RelWrite, slug
from api.shared.types import Workflow


_OBSERVATION_KEYS = {
    "outage-risk-management": "weather_risk",
    "predictive-site-maintenance": "asset_failure_risk",
    "field-repair-dispatch": "work_order",
    "capacity-optimization": "site_congestion",
    "service-ticket-resolution": "ticket_pressure",
    "retention-orchestration": "churn_risk",
}


def _asset(
    workflow: Workflow,
    raw_id: str,
    kind: str,
    attributes: dict[str, Any] | None = None,
) -> EntityWrite:
    return EntityWrite(
        kind="Asset",
        id=f"ASSET-{kind}-{slug(raw_id)}",
        attrs={
            "kind": kind,
            "identifier": raw_id,
            "attributes": json.dumps(
                attributes or {},
                sort_keys=True,
                default=str,
            ),
        },
        source_workflows=(workflow.id,),
    )


def _site(workflow: Workflow, site: dict[str, Any] | str) -> EntityWrite:
    if isinstance(site, dict):
        site_id = str(site.get("id") or "unknown")
        attributes = site
    else:
        site_id = str(site or "unknown")
        attributes = {}
    return _asset(workflow, site_id, "cell-site", attributes)


def _account(workflow: Workflow, account: dict[str, Any]) -> EntityWrite:
    account_id = str(account.get("id") or "unknown")
    return EntityWrite(
        kind="Account",
        id=account_id,
        attrs={
            "code": account_id,
            "name": account_id,
            "type": str(account.get("segment") or "customer"),
        },
        source_workflows=(workflow.id,),
    )


def _base(workflow: Workflow) -> list[EntityWrite | RelWrite]:
    return [
        EntityWrite(
            kind="Workflow",
            id=workflow.id,
            attrs={
                "workflow_type": workflow.type,
                "status": workflow.status,
            },
            source_workflows=(workflow.id,),
        )
    ]


def _asset_at_site(
    workflow: Workflow,
    asset: dict[str, Any],
    site: dict[str, Any] | str,
) -> tuple[EntityWrite, EntityWrite, RelWrite]:
    asset_id = str(asset.get("id") or workflow.id)
    asset_node = _asset(
        workflow,
        asset_id,
        "network-asset",
        asset,
    )
    site_node = _site(workflow, site)
    return (
        asset_node,
        site_node,
        RelWrite(
            src_id=asset_node.id,
            rel="ASSET_AT_SITE",
            dst_id=site_node.id,
        ),
    )


def _project_outage(
    workflow: Workflow,
    observation: dict[str, Any],
) -> list[EntityWrite | RelWrite]:
    ops = _base(workflow)
    for asset in observation.get("at_risk_assets") or []:
        if isinstance(asset, dict):
            ops.extend(
                _asset_at_site(
                    workflow,
                    asset,
                    str(asset.get("site_id") or "unknown"),
                )
            )
    return ops


def _project_maintenance(
    workflow: Workflow,
    observation: dict[str, Any],
) -> list[EntityWrite | RelWrite]:
    asset = observation.get("asset") or {}
    site = observation.get("site") or str(asset.get("site_id") or "unknown")
    return [*_base(workflow), *_asset_at_site(workflow, asset, site)]


def _project_field(
    workflow: Workflow,
    observation: dict[str, Any],
) -> list[EntityWrite | RelWrite]:
    work_order = observation.get("work_order") or {}
    asset = observation.get("asset") or {}
    site = observation.get("site") or {}
    decision = (workflow.payload or {}).get("decision") or {}
    command = decision.get("command") or {}
    command_payload = command.get("payload") or {}
    technicians = observation.get("dispatchable_technicians") or []
    technician_id = str(
        command_payload.get("technician_id")
        or (technicians[0].get("id") if technicians else "unassigned")
    )
    stock = observation.get("spare_stock") or {}
    stock_id = str(
        command_payload.get("source_stock_id")
        or stock.get("id")
        or "unassigned"
    )
    order_node = _asset(
        workflow,
        str(work_order.get("id") or workflow.id),
        "field-work-order",
        work_order,
    )
    technician_node = EntityWrite(
        kind="Person",
        id=f"PERSON-{slug(technician_id)}",
        attrs={
            "name": technician_id,
            "role": "field-technician",
            "attributes": json.dumps({"technician_id": technician_id}),
        },
        source_workflows=(workflow.id,),
    )
    stock_node = _asset(
        workflow,
        stock_id,
        "spare-stock",
        {"required_spare": work_order.get("required_spare")},
    )
    site_ops = _asset_at_site(workflow, asset, site)
    asset_node = site_ops[0]
    return [
        *_base(workflow),
        *site_ops,
        order_node,
        technician_node,
        stock_node,
        RelWrite(order_node.id, "WORK_FOR_ASSET", asset_node.id),
        RelWrite(order_node.id, "ASSIGNED_TO", technician_node.id),
        RelWrite(order_node.id, "REQUIRES_SPARE", stock_node.id),
    ]


def _project_capacity(
    workflow: Workflow,
    observation: dict[str, Any],
) -> list[EntityWrite | RelWrite]:
    return [*_base(workflow), _site(workflow, observation.get("site") or {})]


def _project_tickets(
    workflow: Workflow,
    observation: dict[str, Any],
) -> list[EntityWrite | RelWrite]:
    ops = _base(workflow)
    for account in observation.get("accounts") or []:
        if isinstance(account, dict):
            ops.append(_account(workflow, account))
    for ticket in observation.get("tickets") or []:
        if not isinstance(ticket, dict):
            continue
        ticket_node = _asset(
            workflow,
            str(ticket.get("id") or workflow.id),
            "care-ticket",
            ticket,
        )
        subscription_node = _asset(
            workflow,
            str(ticket.get("subscription_id") or "unknown"),
            "service-subscription",
        )
        ops.extend(
            [
                ticket_node,
                subscription_node,
                RelWrite(
                    ticket_node.id,
                    "TICKET_FOR_SERVICE",
                    subscription_node.id,
                ),
            ]
        )
    return ops


def _project_retention(
    workflow: Workflow,
    observation: dict[str, Any],
) -> list[EntityWrite | RelWrite]:
    account = observation.get("account") or {}
    account_node = _account(workflow, account)
    decision = (workflow.payload or {}).get("decision") or {}
    command = decision.get("command") or {}
    offer = command.get("payload") or {}
    offer_node = _asset(
        workflow,
        workflow.id,
        "retention-offer",
        offer,
    )
    return [
        *_base(workflow),
        account_node,
        offer_node,
        RelWrite(
            offer_node.id,
            "OFFER_FOR_ACCOUNT",
            account_node.id,
        ),
    ]


_PROJECTORS = {
    "outage-risk-management": _project_outage,
    "predictive-site-maintenance": _project_maintenance,
    "field-repair-dispatch": _project_field,
    "capacity-optimization": _project_capacity,
    "service-ticket-resolution": _project_tickets,
    "retention-orchestration": _project_retention,
}


def project(workflow: Workflow) -> list[EntityWrite | RelWrite]:
    observation_key = _OBSERVATION_KEYS[workflow.type]
    observation = (workflow.payload or {}).get(observation_key) or {}
    return _PROJECTORS[workflow.type](workflow, observation)

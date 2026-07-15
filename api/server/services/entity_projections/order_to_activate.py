"""Projection for Telco service-order activation."""
from __future__ import annotations

import json

from api.server.services.entity_projections import EntityWrite, RelWrite, slug
from api.shared.types import Workflow

WORKFLOW_TYPE = "order-to-activate"


def project(workflow: Workflow) -> list[EntityWrite | RelWrite]:
    observation = (workflow.payload or {}).get("service_order") or {}
    order = observation.get("order") or {}
    account = observation.get("account") or {}
    site = observation.get("requested_site") or {}
    order_id = str(order.get("id") or workflow.id)
    account_id = str(account.get("id") or order.get("account_id") or "unknown")
    site_id = str(site.get("id") or order.get("requested_site_id") or "unknown")
    order_asset_id = f"ASSET-order-{slug(order_id)}"
    site_asset_id = f"ASSET-site-{slug(site_id)}"
    sw = (workflow.id,)
    return [
        EntityWrite(
            kind="Workflow",
            id=workflow.id,
            attrs={"workflow_type": WORKFLOW_TYPE, "status": workflow.status},
            source_workflows=sw,
        ),
        EntityWrite(
            kind="Account",
            id=account_id,
            attrs={"code": account_id, "name": account_id, "type": "customer"},
            source_workflows=sw,
        ),
        EntityWrite(
            kind="Asset",
            id=site_asset_id,
            attrs={"kind": "cell-site", "identifier": site_id},
            source_workflows=sw,
        ),
        EntityWrite(
            kind="Asset",
            id=order_asset_id,
            attrs={
                "kind": "service-order",
                "identifier": order_id,
                "status": str(order.get("status") or ""),
                "attributes": json.dumps(
                    {"product": order.get("product"), "account_id": account_id},
                    sort_keys=True,
                ),
            },
            source_workflows=sw,
        ),
        RelWrite(
            src_id=order_asset_id,
            rel="HOSTED_ON",
            dst_id=site_asset_id,
        ),
        RelWrite(
            src_id=account_id,
            rel="PLACED_ORDER",
            dst_id=order_asset_id,
        ),
    ]

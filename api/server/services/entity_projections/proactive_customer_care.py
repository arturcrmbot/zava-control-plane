"""Projection for proactive customer care in the Telco actor world."""
from __future__ import annotations

import json

from api.server.services.entity_projections import (
    DecisionWrite,
    EntityWrite,
    RelWrite,
    build_decision,
    slug,
)
from api.shared.types import Workflow

WORKFLOW_TYPE = "proactive-customer-care"


def project(workflow: Workflow) -> list[EntityWrite | RelWrite | DecisionWrite]:
    payload = workflow.payload or {}
    impact = payload.get("customer_impact") or {}
    sw = (workflow.id,)
    site_id = str(impact.get("incident_site_id") or "unknown")
    site_asset_id = f"ASSET-site-{slug(site_id)}"
    ops: list[EntityWrite | RelWrite | DecisionWrite] = [
        EntityWrite(
            kind="Workflow",
            id=workflow.id,
            attrs={"workflow_type": WORKFLOW_TYPE, "status": workflow.status},
            source_workflows=sw,
        ),
        EntityWrite(
            kind="Asset",
            id=site_asset_id,
            attrs={"kind": "cell-site", "identifier": site_id},
            source_workflows=sw,
        ),
    ]

    subscriptions_by_account = {
        str(item.get("account_id")): item
        for item in impact.get("subscriptions") or []
        if item.get("account_id")
    }
    account_ids: list[str] = []
    for account in impact.get("impacted_accounts") or []:
        account_id = str(account.get("id") or "")
        subscriber_id = str(account.get("subscriber_id") or "")
        if not account_id or not subscriber_id:
            continue
        account_ids.append(account_id)
        person_id = f"PERSON-{slug(subscriber_id)}"
        subscription = subscriptions_by_account.get(account_id) or {}
        subscription_id = str(subscription.get("id") or f"subscription-{account_id}")
        subscription_asset_id = f"ASSET-subscription-{slug(subscription_id)}"
        ops.extend(
            [
                EntityWrite(
                    kind="Person",
                    id=person_id,
                    attrs={
                        "attributes": json.dumps(
                            {"subscriber_id": subscriber_id}, sort_keys=True
                        )
                    },
                    source_workflows=sw,
                ),
                EntityWrite(
                    kind="Account",
                    id=account_id,
                    attrs={
                        "code": account_id,
                        "name": account_id,
                        "type": str(account.get("segment") or "customer"),
                    },
                    source_workflows=sw,
                ),
                EntityWrite(
                    kind="Asset",
                    id=subscription_asset_id,
                    attrs={
                        "kind": "service-subscription",
                        "identifier": subscription_id,
                        "attributes": json.dumps(
                            {
                                "product": subscription.get("product"),
                                "status": subscription.get("status"),
                            },
                            sort_keys=True,
                            default=str,
                        ),
                    },
                    source_workflows=sw,
                ),
                RelWrite(
                    src_id=person_id,
                    rel="HOLDS_ACCOUNT",
                    dst_id=account_id,
                ),
                RelWrite(
                    src_id=person_id,
                    rel="SUBSCRIBED_TO",
                    dst_id=subscription_asset_id,
                ),
                RelWrite(
                    src_id=subscription_asset_id,
                    rel="HOSTED_ON",
                    dst_id=site_asset_id,
                ),
            ]
        )

    decision = build_decision(
        workflow,
        gate_phase="entitlement_decision",
        persona_role="customer_care",
        source_event="world.responder.decided",
        decided_on=tuple(account_ids),
        attributes={"incident_site_id": site_id},
    )
    if decision is not None:
        ops.append(decision)
    return ops

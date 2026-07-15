from __future__ import annotations

from api.server.services.entity_graph import DecisionWrite, EntityWrite, RelWrite
from api.server.services.entity_projections.proactive_customer_care import (
    WORKFLOW_TYPE,
    project,
)

from ._helpers import make_workflow


def _workflow():
    return make_workflow(
        "CARE-T1",
        WORKFLOW_TYPE,
        {
            "incident_site_id": "SITE-03",
            "impacted_accounts": [
                {
                    "id": "ACC-00001",
                    "subscriber_id": "SUB-00001",
                    "segment": "consumer",
                }
            ],
            "subscriptions": [
                {
                    "id": "SUBS-00001",
                    "account_id": "ACC-00001",
                    "subscriber_id": "SUB-00001",
                    "site_id": "SITE-03",
                    "product": "5g-premium",
                }
            ],
        },
        nest_under="customer_impact",
        decisions=[
            {
                "phase": "entitlement_decision",
                "verdict": "approve",
                "reason": "service impact confirmed",
                "decided_at": "2026-07-15T12:00:00Z",
            }
        ],
    )


def test_projection_connects_customer_account_subscription_and_site():
    ops = project(_workflow())

    entities = {
        (op.kind, op.id)
        for op in ops
        if isinstance(op, EntityWrite)
    }
    assert ("Person", "PERSON-sub-00001") in entities
    assert ("Account", "ACC-00001") in entities
    assert ("Asset", "ASSET-subscription-subs-00001") in entities
    assert ("Asset", "ASSET-site-site-03") in entities

    relationships = [op for op in ops if isinstance(op, RelWrite)]
    assert RelWrite(
        src_id="PERSON-sub-00001",
        rel="HOLDS_ACCOUNT",
        dst_id="ACC-00001",
    ) in relationships
    assert RelWrite(
        src_id="PERSON-sub-00001",
        rel="SUBSCRIBED_TO",
        dst_id="ASSET-subscription-subs-00001",
    ) in relationships
    assert RelWrite(
        src_id="ASSET-subscription-subs-00001",
        rel="HOSTED_ON",
        dst_id="ASSET-site-site-03",
    ) in relationships


def test_projection_targets_entitlement_decision_at_account():
    decisions = [
        op for op in project(_workflow()) if isinstance(op, DecisionWrite)
    ]

    assert len(decisions) == 1
    assert decisions[0].phase == "entitlement_decision"
    assert decisions[0].decided_on == ("ACC-00001",)

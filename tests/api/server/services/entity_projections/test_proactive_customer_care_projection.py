from __future__ import annotations

import json
from pathlib import Path

import pytest

from api.server.services.entity_graph import DecisionWrite, EntityGraph, EntityWrite, RelWrite
from verticals.telco.entity_projections.proactive_customer_care import (
    WORKFLOW_TYPE,
    project,
)
from verticals.telco.entity_projections.network_incident import (
    WORKFLOW_TYPE as NETWORK_WORKFLOW_TYPE,
    project as network_project,
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


def _workflow_with_accounts(count: int):
    return make_workflow(
        "CARE-CAP",
        WORKFLOW_TYPE,
        {
            "incident_site_id": "SITE-03",
            "impacted_accounts": [
                {
                    "id": f"ACC-{index:05d}",
                    "subscriber_id": f"SUB-{index:05d}",
                    "segment": "consumer",
                }
                for index in range(1, count + 1)
            ],
            "subscriptions": [
                {
                    "id": f"SUBS-{index:05d}",
                    "account_id": f"ACC-{index:05d}",
                    "subscriber_id": f"SUB-{index:05d}",
                    "site_id": "SITE-03",
                    "product": "5g-premium",
                }
                for index in range(1, count + 1)
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
    impact_asset = next(
        op
        for op in ops
        if isinstance(op, EntityWrite) and op.attrs.get("kind") == "customer-impact-summary"
    )
    assert impact_asset.id == "ASSET-customer-impact-care-t1-site-03"
    assert json.loads(impact_asset.attrs["attributes"])["affected_account_count"] == 1
    assert RelWrite(
        src_id="ASSET-customer-impact-care-t1-site-03",
        rel="HOSTED_ON",
        dst_id="ASSET-site-site-03",
    ) in relationships
    site = next(
        op
        for op in ops
        if isinstance(op, EntityWrite) and op.id == "ASSET-site-site-03"
    )
    assert "attributes" not in site.attrs


def test_projection_targets_entitlement_decision_at_account():
    decisions = [
        op for op in project(_workflow()) if isinstance(op, DecisionWrite)
    ]

    assert len(decisions) == 1
    assert decisions[0].phase == "entitlement_decision"
    assert decisions[0].decided_on == ("ACC-00001",)


def test_projection_caps_accounts_and_subscriptions_to_deterministic_prefix(
    monkeypatch: pytest.MonkeyPatch,
):
    monkeypatch.setenv("TELCO_GRAPH_DETAIL_CAP", "2")
    workflow = _workflow_with_accounts(4)

    first = project(workflow)
    second = project(workflow)

    accounts = [
        op.id for op in first if isinstance(op, EntityWrite) and op.kind == "Account"
    ]
    subscriptions = [
        op.id
        for op in first
        if isinstance(op, EntityWrite)
        and op.attrs.get("kind") == "service-subscription"
    ]
    assert accounts == ["ACC-00001", "ACC-00002"]
    assert subscriptions == [
        "ASSET-subscription-subs-00001",
        "ASSET-subscription-subs-00002",
    ]
    assert first == second

    summary = next(
        op
        for op in first
        if isinstance(op, EntityWrite)
        and op.attrs.get("kind") == "customer-impact-summary"
    )
    assert json.loads(summary.attrs["attributes"])["affected_account_count"] == 4

    decisions = [op for op in first if isinstance(op, DecisionWrite)]
    assert len(decisions) == 1
    assert decisions[0].decided_on == ("ACC-00001", "ACC-00002")


def test_projection_defaults_to_25_account_and_subscription_details(
    monkeypatch: pytest.MonkeyPatch,
):
    monkeypatch.delenv("TELCO_GRAPH_DETAIL_CAP", raising=False)

    ops = project(_workflow_with_accounts(30))

    assert sum(
        isinstance(op, EntityWrite) and op.kind == "Account"
        for op in ops
    ) == 25
    assert sum(
        isinstance(op, EntityWrite)
        and op.attrs.get("kind") == "service-subscription"
        for op in ops
    ) == 25


def test_projection_rejects_invalid_graph_detail_cap(
    monkeypatch: pytest.MonkeyPatch,
):
    monkeypatch.setenv("TELCO_GRAPH_DETAIL_CAP", "not-an-integer")

    with pytest.raises(ValueError, match="TELCO_GRAPH_DETAIL_CAP.*positive integer"):
        project(_workflow())


def test_projections_apply_sequentially_without_colliding_site_attributes(
    tmp_path: Path,
):
    graph = EntityGraph(tmp_path / "g.kuzu")

    incident_wf = make_workflow(
        "NI-SHARED",
        NETWORK_WORKFLOW_TYPE,
        {
            "incident_site": {
                "id": "SITE-03",
                "region": "north",
                "status": "failed",
                "capacity_mbps": 600.0,
            },
            "affected_sessions": [
                {
                    "id": "SESS-00001",
                    "subscriber_id": "SUB-00001",
                    "kind": "voice",
                }
            ],
        },
        nest_under="incident",
    )
    care_wf = _workflow()

    for op in network_project(incident_wf):
        if isinstance(op, EntityWrite):
            graph.upsert(op)
        elif isinstance(op, RelWrite):
            graph.link(op.src_id, op.rel, op.dst_id, **op.attrs)

    for op in project(care_wf):
        if isinstance(op, EntityWrite):
            graph.upsert(op)
        elif isinstance(op, RelWrite):
            graph.link(op.src_id, op.rel, op.dst_id, **op.attrs)

    site = graph.get("ASSET-site-site-03")
    assert site is not None
    assert site["kind"] == "cell-site"
    assert json.loads(site["attributes"]) == {
        "capacity_mbps": 600.0,
        "affected_session_count": 1,
        "region": "north",
        "status": "failed",
    }

    summary = graph.get("ASSET-customer-impact-care-t1-site-03")
    assert summary is not None
    assert summary["kind"] == "customer-impact-summary"
    assert json.loads(summary["attributes"]) == {"affected_account_count": 1}
    summary_links = graph.linked("ASSET-customer-impact-care-t1-site-03", "HOSTED_ON")
    assert any(link["node"]["id"] == "ASSET-site-site-03" for link in summary_links)

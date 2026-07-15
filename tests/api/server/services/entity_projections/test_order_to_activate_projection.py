from api.server.services.entity_graph import EntityWrite, RelWrite
from api.server.services.entity_projections.order_to_activate import (
    WORKFLOW_TYPE,
    project,
)

from ._helpers import make_workflow


def test_projection_connects_service_order_account_and_site():
    workflow = make_workflow(
        "ORDER-T1",
        WORKFLOW_TYPE,
        {
            "order": {
                "id": "ORD-00002",
                "account_id": "ACC-00001",
                "product": "fiber-1gb",
                "requested_site_id": "SITE-02",
                "status": "pending",
            },
            "account": {"id": "ACC-00001"},
            "requested_site": {"id": "SITE-02"},
        },
        nest_under="service_order",
    )

    ops = project(workflow)

    assert any(
        isinstance(op, EntityWrite)
        and op.kind == "Asset"
        and op.id == "ASSET-order-ord-00002"
        for op in ops
    )
    assert RelWrite(
        src_id="ASSET-order-ord-00002",
        rel="HOSTED_ON",
        dst_id="ASSET-site-site-02",
    ) in ops
    assert RelWrite(
        src_id="ACC-00001",
        rel="PLACED_ORDER",
        dst_id="ASSET-order-ord-00002",
    ) in ops

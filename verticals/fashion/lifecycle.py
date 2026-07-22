from __future__ import annotations

from api.server.services.entity_graph import EntityWrite


def bootstrap(state) -> None:
    graph = getattr(state, "entities", None)
    if graph is None:
        return
    for operation in (
        EntityWrite(
            "Asset",
            "STORE-UK-LON-01",
            {
                "kind": "retail-store",
                "identifier": "Oxford Street Flagship",
                "status": "open",
            },
        ),
        EntityWrite(
            "Asset",
            "STORE-EU-PAR-01",
            {
                "kind": "retail-store",
                "identifier": "Paris Rivoli",
                "status": "open",
            },
        ),
        EntityWrite(
            "Asset",
            "SKU-STYLE-01-BLK-M",
            {"kind": "fashion-sku", "identifier": "STYLE-01 / black / M"},
        ),
        EntityWrite(
            "Person",
            "STAFF-LON-01",
            {"name": "Maya Patel", "role": "style-advisor", "market": "GB"},
        ),
    ):
        graph.upsert(operation)


async def start(_state):
    return ()

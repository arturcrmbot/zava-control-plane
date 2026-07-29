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
                "identifier": "London Central",
                "status": "open",
            },
        ),
        EntityWrite(
            "Asset",
            "DC-UK-MID-01",
            {
                "kind": "distribution-centre",
                "identifier": "Midlands Fulfilment Hub",
                "status": "open",
            },
        ),
        EntityWrite(
            "Asset",
            "SKU-APEX-X1-GRAPHITE-16",
            {
                "kind": "electronics-sku",
                "identifier": "Apex X1 / graphite / 16GB",
            },
        ),
        EntityWrite(
            "Person",
            "STAFF-UK-01-01",
            {"name": "Maya Patel", "role": "gaming-specialist", "market": "GB"},
        ),
    ):
        graph.upsert(operation)


async def start(_state):
    return ()

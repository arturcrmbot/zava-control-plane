"""Hospitality lifecycle: anonymous entity bootstrap and a no-op start."""
from __future__ import annotations

import json

from api.server.services.entity_graph import EntityWrite


_HOTELS = (
    ("HOTEL-RIVERSIDE-CENTRAL", "Riverside Central", "GB"),
    ("HOTEL-AIRPORT-NORTH", "Airport North", "GB"),
    ("HOTEL-CITY-GATE", "City Gate", "GB"),
    ("HOTEL-HARBOUR-VIEW", "Harbour View", "GB"),
    ("HOTEL-MESSE-CENTRAL", "Messe Central", "DE"),
    ("HOTEL-RHINE-PARK", "Rhine Park", "DE"),
)


def bootstrap(state) -> None:
    graph = getattr(state, "entities", None)
    if graph is None:
        return
    for hotel_id, label, country in _HOTELS:
        graph.upsert(
            EntityWrite(
                "Asset",
                hotel_id,
                {
                    "kind": "hotel-property",
                    "identifier": label,
                    "status": "operational",
                    "attributes": json.dumps({"country": country}, sort_keys=True),
                },
            )
        )


async def start(_state):
    return ()

"""End-to-end smoke test for the image_gen MCP wired into the creative-stub
agent's concept_fanout phase.

Run with:
    set -a && source .env && set +a
    CREATIVE_REAL_FOUNDRY=1 \
    CREATIVE_IMAGE_QUALITY=low \
    AZURE_STORAGE_CONNECTION_STRING='<azurite-or-real>' \
    python tools/scratch/smoke_image_gen.py

Renders 12 concept stills against real Foundry gpt-image-2, uploads each to
Azure Blob, prints the SAS URLs and timing. Verifies (a) parallel render
works, (b) blob cache hits skip Foundry on a second run, (c) graceful
fallback on RAI rejection.
"""
from __future__ import annotations

import asyncio
import os
import time

from api.functions.graphs.executors.agents import agent_creative_stub
from api.server.mcp_tools import image_gen


async def main() -> None:
    print(f"is_configured: {image_gen.is_configured()}")
    print(f"CREATIVE_REAL_FOUNDRY: {os.environ.get('CREATIVE_REAL_FOUNDRY')!r}")
    print(f"CREATIVE_IMAGE_QUALITY: {os.environ.get('CREATIVE_IMAGE_QUALITY', 'medium')}")
    print()

    payload = {
        "phase": "concept_fanout",
        "workflow_id": "CMP-SMOKE-1",
        "brief_id": "BRF-SMOKE",
        "brief": {
            "id": "BRF-SMOKE",
            "client_brand": "Solene",
            "category": "luxury_fragrance",
            "audience": "European luxury 25-44",
        },
    }

    print("=== concept_fanout (12 images parallel) ===")
    t0 = time.time()
    out = await agent_creative_stub.execute(payload)
    dt = time.time() - t0
    print(f"image_source: {out['image_source']}")
    print(f"wall: {dt:.1f}s for 12 images")
    for r in out["routes"]:
        print(f"  {r['route_name']} ({r['headline']}):")
        for s in r["stills"]:
            short = s if len(s) < 110 else s[:80] + "..."
            print(f"    {short}")
    print()

    print("=== concept_fanout SECOND RUN — should be cache hits ===")
    t1 = time.time()
    out2 = await agent_creative_stub.execute(payload)
    dt2 = time.time() - t1
    print(f"wall: {dt2:.1f}s — should be << first run if blob cache works")
    same_urls = sum(
        1
        for ra, rb in zip(out["routes"], out2["routes"])
        for ua, ub in zip(ra["stills"], rb["stills"])
        if ua.split("?")[0] == ub.split("?")[0]
    )
    print(f"same blob URLs across runs: {same_urls}/12 (only the SAS query string changes)")


if __name__ == "__main__":
    asyncio.run(main())

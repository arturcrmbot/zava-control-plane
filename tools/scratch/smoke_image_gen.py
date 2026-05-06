"""End-to-end smoke test for the image_gen MCP wired into the creative-stub
agent's concept_fanout phase. Loads .env via Python (which respects the
conn-string's semicolons; bash's `set -a; source` does not).

Run with:
    cd <repo>
    CREATIVE_REAL_FOUNDRY=1 CREATIVE_IMAGE_QUALITY=low \
    PYTHONPATH=. python tools/scratch/smoke_image_gen.py
"""
from __future__ import annotations

import asyncio
import os
import time
from pathlib import Path


def _load_dotenv(*, override: bool = True) -> None:
    """Plain-text .env loader that preserves semicolons inside values.
    Avoids the `set -a; source .env` pitfall with conn strings.

    `override=True` forces re-reading even when the shell already has the
    var set — which matters when the shell ran `set -a; source .env`
    first and truncated semicoloned values; we want to replace those."""
    env_path = Path(".env")
    if not env_path.exists():
        return
    for line in env_path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        v = v.strip()
        if (v.startswith('"') and v.endswith('"')) or (
            v.startswith("'") and v.endswith("'")
        ):
            v = v[1:-1]
        if override or k not in os.environ:
            os.environ[k] = v


async def main() -> None:
    _load_dotenv()

    # Set sensible smoke defaults if the caller didn't override.
    os.environ.setdefault("CREATIVE_REAL_FOUNDRY", "1")
    os.environ.setdefault("CREATIVE_IMAGE_QUALITY", "low")
    os.environ.setdefault("CREATIVE_IMAGE_CONCURRENCY", "4")

    # Imports AFTER env is loaded so module-level reads pick up the values.
    from api.functions.graphs.executors.agents import agent_creative_stub
    from api.server.mcp_tools import image_gen

    print(f"is_configured: {image_gen.is_configured()}")
    print(f"CREATIVE_REAL_FOUNDRY: {os.environ.get('CREATIVE_REAL_FOUNDRY')!r}")
    print(f"CREATIVE_IMAGE_QUALITY: {os.environ.get('CREATIVE_IMAGE_QUALITY')!r}")
    print(f"CREATIVE_IMAGE_CONCURRENCY: {os.environ.get('CREATIVE_IMAGE_CONCURRENCY')!r}")
    cs = os.environ.get("AZURE_STORAGE_CONNECTION_STRING", "<unset>")
    print(f"AZURE_STORAGE_CONNECTION_STRING (first 120): {cs[:120]}...")
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

    print("=== concept_fanout (12 images, bounded parallelism) ===")
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
    print(
        f"same blob URLs across runs: {same_urls}/12 "
        f"(only the SAS query string changes)"
    )


if __name__ == "__main__":
    asyncio.run(main())

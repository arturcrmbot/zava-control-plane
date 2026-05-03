"""Lean FastAPI entry point for the blueprint microsite deployment.

Only what the deployed page needs:

  - The blueprint composition tree (read from disk).
  - The blueprint observatory SSE stream.
  - The recorder + always-on demo trickle.
  - The static-mounted React bundle.

Critically, this entry point does NOT import:

  - api.server.state                  (BlobStore + EmailSender + GHCP/MAF)
  - api.server.services.fleet_manager_service  (github-copilot-sdk)
  - the other 18 routers               (workflows, portal, evals, etc.)

That's why the deploy's container image can omit the heavy deps
(github-copilot-sdk, agent-framework, sentence-transformers, weasyprint, …)
and stay small + fast to start.

For local dev or the full demo stack, use `api.server.main:app` instead.
"""

from __future__ import annotations

import asyncio
import os
from contextlib import asynccontextmanager

from dotenv import load_dotenv

load_dotenv()

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# Tiny in-process EventBus shim so the blueprint route + recorder + stream
# loop work without pulling in the full app_state graph. The page never
# subscribes to anything else here, so a self-contained bus is enough.
from api.server.services.event_bus import EventBus
from api.shared.events import FleetEvent  # noqa: F401 (re-exported via routes)


class _BlueprintAppState:
    """Minimal state object that satisfies what the blueprint route
    expects from app_state: a `bus`. Other attributes are unused."""

    def __init__(self) -> None:
        self.bus = EventBus()


# We have to monkey-patch api.server.state.app_state BEFORE importing the
# blueprint route module — the route reads `from api.server.state import
# app_state` at module load. The tiny shim above is enough; we never
# reach any code path that uses anything other than `.bus`.
import api.server.state as _state_module  # type: ignore

_state_module.app_state = _BlueprintAppState()

# Now safe to import the route — it picks up the shim.
from api.server.routes.blueprint import router as blueprint_router  # noqa: E402


@asynccontextmanager
async def lifespan(app: FastAPI):
    print("[blueprint] startup")
    if os.environ.get("BLUEPRINT_AUTOSTART_STREAM") == "1":
        try:
            from api.server.routes.blueprint import demo_stream_start
            await demo_stream_start()
            print("[blueprint] demo trickle auto-started")
        except Exception as ex:
            print(f"[blueprint] autostart failed: {ex}")
    yield
    # Best-effort shutdown of the trickle so the asyncio loop doesn't warn.
    try:
        from api.server.routes.blueprint import demo_stream_stop
        await demo_stream_stop()
    except Exception:
        pass
    print("[blueprint] shutdown")


app = FastAPI(title="Blueprint", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], allow_credentials=True,
    allow_methods=["*"], allow_headers=["*"],
)


@app.get("/api/health")
async def health() -> dict:
    return {"ok": True, "service": "blueprint"}


app.include_router(blueprint_router)

# Static-mount the built React bundle (production). No-op when dist absent.
from api.server.static_blueprint import mount_blueprint_static  # noqa: E402

_mounted = mount_blueprint_static(app)
if _mounted:
    print("[blueprint] mounted Vite bundle from web/blueprint/dist/")

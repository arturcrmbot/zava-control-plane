from __future__ import annotations
import asyncio
from contextlib import asynccontextmanager
from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.server.state import app_state
from api.server.services.fleet_manager_service import FleetManagerService
from api.server.services import simulator_orchestrator
from api.shared.otel import init_otel

load_dotenv()


def _on_live(ev: dict):
    app_state.hub.broadcast("fleet-manager", ev)


app_state.fm = FleetManagerService(
    bus=app_state.bus, store=app_state.store, audit=app_state.audit,
    on_live=_on_live,
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_otel("control-plane-server")
    try:
        await app_state.fm.start()
    except Exception as ex:
        print(f"[server] Fleet Manager failed to start: {ex}")
    # Start the simulator ramp loop (spawns workflows via the AF Durable host)
    ramp_task = asyncio.create_task(simulator_orchestrator.ramp_loop())
    yield
    ramp_task.cancel()
    try:
        await app_state.fm.stop()
    except Exception:
        pass


app = FastAPI(title="WPP Control Plane (Python POC1)", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], allow_credentials=True,
    allow_methods=["*"], allow_headers=["*"],
)


@app.get("/api/health")
async def health():
    return {"ok": True}


# Wire bus -> hub fan-out: every bus event broadcast on "fleet" topic
app_state.bus.on_any(lambda e: app_state.hub.broadcast("fleet", e.model_dump()))


from api.server.routes.stream import router as stream_router
from api.server.routes.workflows import router as workflows_router
from api.server.routes.exceptions import router as exceptions_router
from api.server.routes.policy import router as policy_router
from api.server.routes.simulator import router as simulator_router
from api.server.routes.audit import router as audit_router
from api.server.routes.evals import router as evals_router
from api.server.routes.orchestration import router as orchestration_router
from api.server.routes.internal_durable_event import router as durable_event_router
from api.server.routes.fleet import router as fleet_router
from api.server.routes.accuracy import router as accuracy_router
from api.server.routes.policy_md import router as policy_md_router

for r in (stream_router, workflows_router, exceptions_router, policy_router,
          simulator_router, audit_router, evals_router, orchestration_router,
          durable_event_router, fleet_router, accuracy_router, policy_md_router):
    app.include_router(r)

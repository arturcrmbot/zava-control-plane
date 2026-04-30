from __future__ import annotations
import asyncio
from contextlib import asynccontextmanager
from dotenv import load_dotenv

# load_dotenv MUST run before any module that reads os.environ at import time.
# api.server.state constructs MagicLinkStore + EmailSender + BlobStore eagerly
# using env vars; if .env hasn't been parsed yet, BlobStore comes back as None
# and /api/portal/apply 503s with "AZURE_STORAGE_CONNECTION_STRING not set".
load_dotenv()

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.server.state import app_state
from api.server.services.fleet_manager_service import FleetManagerService
from api.server.services import simulator_orchestrator
from api.shared.otel import init_otel


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
    from api.server.eval.online_subscriber import lifespan_register, lifespan_shutdown
    await lifespan_register(app)
    # Candidate-portal: subscribe the cv_crystalliser → magic-link + email
    # bridge. Returns an unsubscribe callable that we hold for teardown.
    from api.server.services.portal_orchestration import attach as _attach_portal_orch
    _portal_orch_off = _attach_portal_orch(app_state)
    # Seed three demo HiringOrchestrator workflows so the candidate portal's
    # /apply form always has a workflow to attach to (one per req in
    # data/synthetic/hiring/reqs.json). Idempotent — safe to re-run.
    from api.server.services.portal_seed import seed_demo_reqs
    try:
        seeded = seed_demo_reqs(app_state)
        if seeded:
            print(f"[server] seeded {len(seeded)} demo hiring reqs: {seeded}")
    except Exception as ex:
        print(f"[server] portal demo-req seeding failed: {ex}")
    try:
        yield
    finally:
        ramp_task.cancel()
        try:
            _portal_orch_off()
        except Exception:
            pass
        try:
            await app_state.fm.stop()
        except Exception:
            pass
        await lifespan_shutdown(app)


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
from api.server.routes.receipts import router as receipts_router
# POC2 multi-surface + frontier endpoints (§4.6, §4.14, §4.19)
from api.server.routes.webhooks_servicenow import router as webhooks_servicenow_router
from api.server.routes.webhooks_finance_bp import router as webhooks_finance_bp_router
from api.server.routes.a2a import router as a2a_router
# Candidate portal (demo-ready scope) — public /apply + token-authed surfaces
from api.server.routes.portal import router as portal_router
from api.server.routes.portal_voice import router as portal_voice_router

for r in (stream_router, workflows_router, exceptions_router, policy_router,
          simulator_router, audit_router, evals_router, orchestration_router,
          durable_event_router, fleet_router, accuracy_router, policy_md_router,
          receipts_router,
          webhooks_servicenow_router, webhooks_finance_bp_router,
          a2a_router,
          portal_router, portal_voice_router):
    app.include_router(r)

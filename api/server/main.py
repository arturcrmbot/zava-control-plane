from __future__ import annotations
import asyncio
from contextlib import asynccontextmanager

# .env is loaded by api.server.state at its module top before any stores
# are constructed; importing app_state below triggers that. The Functions
# worker also imports state directly, so keeping the load_dotenv() call
# inside state.py is the single canonical entry point.

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
    # Governance kernel — see plan/feature-agent-governance-toolkit-1.md
    # (TASK-004). Idempotent. Logs AGT version + policy_version +
    # enforcement_mode at boot. Phase 1: returns ALLOW for everything;
    # call sites are wired in Phase 2.
    from api.server.services.governance import init_governance
    init_governance()
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
    # Persona responder: closes generated-domain HITL gates by applying the
    # persona's decision policy deterministically against the parked context
    # and raising the resolving external event back to Durable. Hand-built
    # domains (expense / hiring) omit the persona/external_event fields from
    # their suspended payloads, so this subscriber ignores them.
    from api.server.services.persona_responder import attach as _attach_persona_responder
    _persona_responder_off = _attach_persona_responder(app_state.bus)

    # Blueprint deployment: when BLUEPRINT_AUTOSTART_STREAM=1 is set
    # (production container), kick the demo trickle so the page is alive
    # without anyone clicking "Wake the observatory". Local dev leaves
    # this off so real workflow events on the bus aren't drowned by the
    # synthetic playback.
    import os as _os
    if _os.environ.get("BLUEPRINT_AUTOSTART_STREAM") == "1":
        try:
            from api.server.routes.blueprint import demo_stream_start as _bp_start
            await _bp_start()
            print("[server] blueprint demo trickle auto-started")
        except Exception as ex:
            print(f"[server] blueprint demo trickle autostart failed: {ex}")
    # Seed three demo HiringOrchestrator workflows so the candidate portal's
    # /apply form always has a workflow to attach to (one per req in
    # data/synthetic/hiring/reqs.json). Idempotent — safe to re-run.
    # Run as a background task so FastAPI startup is not blocked while
    # seed_demo_reqs waits for the Functions host to bind.
    # Gated by PORTAL_SEED_REQS=1; off by default so the POC2 demo can
    # walk a real apply → triage → screen flow without three pre-existing
    # HIRE-DEMO-* workflows in the queue.
    if _os.environ.get("PORTAL_SEED_REQS") == "1":
        from api.server.services.portal_seed import seed_demo_reqs
        async def _seed_in_background():
            try:
                seeded = await seed_demo_reqs(app_state)
                if seeded:
                    print(f"[server] seeded {len(seeded)} demo hiring reqs: {seeded}")
            except Exception as ex:
                print(f"[server] portal demo-req seeding failed: {ex}")
        seed_task = asyncio.create_task(_seed_in_background())
    else:
        seed_task = asyncio.create_task(asyncio.sleep(0))

    # Wire bus -> hub fan-out inside the lifespan so each app instance owns
    # exactly one subscription. Previously this lived at module import time,
    # which under uvicorn --reload accumulated a fresh subscription per
    # reload — every event then fanned out N× and old AppState references
    # leaked. Capturing the unsubscribe and calling it on teardown closes
    # that loop.
    _bus_to_hub_off = app_state.bus.on_any(
        lambda e: app_state.hub.broadcast("fleet", e.model_dump())
    )

    try:
        yield
    finally:
        try:
            _bus_to_hub_off()
        except Exception:
            pass
        ramp_task.cancel()
        seed_task.cancel()
        # Await the cancelled tasks so their teardown actually completes
        # before the lifespan returns. Without this, a partially-running
        # seed (which calls into the Functions host over HTTP) can leave
        # an open httpx connection or a half-scheduled orchestration.
        for t in (ramp_task, seed_task):
            try:
                await t
            except (asyncio.CancelledError, Exception):
                pass
        try:
            _portal_orch_off()
        except Exception:
            pass
        try:
            _persona_responder_off()
        except Exception:
            pass
        try:
            await app_state.fm.stop()
        except Exception:
            pass
        try:
            await app_state.aclose()
        except Exception:
            pass
        await lifespan_shutdown(app)


app = FastAPI(title="Zava Control Plane (Python POC1)", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], allow_credentials=True,
    allow_methods=["*"], allow_headers=["*"],
)


@app.get("/api/health")
async def health():
    return {"ok": True}


# Bus -> hub fan-out is wired inside the lifespan (see above) so each app
# instance owns exactly one subscription. Do not subscribe at import time;
# under uvicorn --reload that accumulates one extra listener per reload.


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
from api.server.routes.creative_campaign_assets import router as creative_campaign_assets_router
from api.server.routes.foundry import router as foundry_router
# POC2 multi-surface + frontier endpoints (§4.6, §4.14, §4.19)
from api.server.routes.webhooks_servicenow import router as webhooks_servicenow_router
from api.server.routes.webhooks_finance_bp import router as webhooks_finance_bp_router
from api.server.routes.a2a import router as a2a_router
# Candidate portal (demo-ready scope) — public /apply + token-authed surfaces
from api.server.routes.portal import router as portal_router
from api.server.routes.portal_voice import router as portal_voice_router
from api.server.routes.portal_interview import router as portal_interview_router
from api.server.routes.portal_admin_decisions import router as portal_admin_decisions_router
# Blueprint microsite — composition tree + live observatory SSE
from api.server.routes.blueprint import router as blueprint_router
# Substrate registry surfaces (Phase 7 of feature-authority-and-personae-1).
from api.server.routes.personas import router as personas_router
from api.server.routes.authority import router as authority_router
# Governance kernel surface (Phase 4 of feature-agent-governance-toolkit-1).
from api.server.routes.governance import router as governance_router
# Entity-graph plane read API (Phase 1 TASK-030..-035).
from api.server.routes.entities import router as entities_router

for r in (stream_router, workflows_router, exceptions_router, policy_router,
          simulator_router, audit_router, evals_router, orchestration_router,
          durable_event_router, fleet_router, accuracy_router, policy_md_router,
          receipts_router, creative_campaign_assets_router,
          webhooks_servicenow_router, webhooks_finance_bp_router,
          a2a_router,
          portal_router, portal_voice_router, portal_interview_router,
          portal_admin_decisions_router,
          blueprint_router,
          personas_router, authority_router,
          governance_router,
          entities_router,
          foundry_router):
    app.include_router(r)

# Mount the built blueprint Vite bundle if present (production deploy).
# No-op in dev when web/blueprint/dist/ doesn't exist (Vite serves the
# page directly on :5175 and proxies /api back here).
from api.server.static_blueprint import mount_blueprint_static
_blueprint_mounted = mount_blueprint_static(app)
if _blueprint_mounted:
    print("[server] mounted blueprint bundle from web/blueprint/dist/")

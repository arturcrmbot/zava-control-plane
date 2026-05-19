from __future__ import annotations
import asyncio
from contextlib import asynccontextmanager

# .env is loaded by api.server.state at its module top before any stores
# are constructed; importing app_state below triggers that. The Functions
# worker also imports state directly, so keeping the load_dotenv() call
# inside state.py is the single canonical entry point.

import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.server.state import app_state


def _cors_allowed_origins() -> list[str]:
    # CORS_ALLOWED_ORIGINS: comma-separated allowlist. Default covers the
    # local vite dev servers (portal:5274, blueprint:5275) and the FastAPI
    # host port itself (3101) for same-origin tooling.
    raw = os.getenv(
        "CORS_ALLOWED_ORIGINS",
        "http://localhost:5274,http://localhost:5275,http://localhost:3101",
    )
    return [o.strip() for o in raw.split(",") if o.strip()]
from api.server.services.fleet_manager_service import FleetManagerService
from api.server.services import simulator_orchestrator
from api.shared.otel import init_otel


def _on_live(ev: dict):
    app_state.hub.broadcast("fleet-manager", ev)


app_state.fm = FleetManagerService(
    bus=app_state.bus, store=app_state.store, audit=app_state.audit,
    on_live=_on_live,
)
# Phase 3 (TASK-028) — instantiate per-non-legacy-function FMs once
# ``app_state`` is module-bound. Done here (not in AppState.__init__)
# because the mcp_tools package eagerly imports submodules that
# themselves do ``from api.server.state import app_state``; populating
# function_fms inside __init__ would race the binding.
app_state.init_function_fms()


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
    # Phase 3 IP6 — start the ambient dispatcher inside the lifespan so
    # cypher sweep loops are scheduled on the running event loop.
    try:
        if hasattr(app_state, "ambient_dispatcher"):
            app_state.ambient_dispatcher.start()
    except Exception as ex:
        print(f"[server] Ambient dispatcher failed to start: {ex}")
    # pitch-h1 / pitch-h2 cross-domain entanglement watchers — see
    # plan/feature-enterprise-pitch-readiness-1.md Track H. They need the
    # entity graph (vendor / brand lookups) so we skip wiring when the
    # entity plane is disabled (e.g. the Functions worker side of a
    # multi-process boot).
    from api.server.services.ambient_agents import (
        brand_budget_watcher,
        vendor_block_watcher,
        subsidiary_capacity_watcher,
        trend_cadence_watcher,
        auto_block_rule_learner,
        kpi_history_recorder,
    )
    try:
        if hasattr(app_state, "entities"):
            vendor_block_watcher.start(app_state.bus, app_state.entities)
            brand_budget_watcher.start(app_state.bus, app_state.entities)
    except Exception as ex:
        print(f"[server] entanglement watchers failed to start: {ex}")
    # pitch-h4: subsidiary capacity watcher. Reads in-flight workflow
    # counts from the StateStore (no entity-graph dependency) so it can
    # boot even when the entity plane is disabled.
    try:
        subsidiary_capacity_watcher.start(app_state.bus, app_state.store)
    except Exception as ex:
        print(f"[server] subsidiary_capacity_watcher failed to start: {ex}")
    # pitch-i2: auto-block rule learner. Subscribes to decision.recorded
    # and installs a permanent precedent after 3 KYC rejections per
    # vendor. Wired regardless of the entity plane — falls back to the
    # in-memory ledger when ``entities`` is absent.
    try:
        auto_block_rule_learner.start(
            app_state.bus, getattr(app_state, "entities", None)
        )
    except Exception as ex:
        print(f"[server] auto_block_rule_learner failed to start: {ex}")
    # pitch-i5: KPI-trend-driven cadence triggers. Provisional in-memory
    # ring buffer (kpi_trend_buffer); J1 will replace with the durable
    # KPI history series. Mirrors the H1/H2 module-singleton pattern so
    # uvicorn --reload cycles don't accumulate tick loops.
    try:
        trend_cadence_watcher.start(bus=app_state.bus)
    except Exception as ex:
        print(f"[server] trend_cadence_watcher failed to start: {ex}")
    # pitch-j5: hourly story-pack writer. Idempotent on the (hour, hour+1)
    # key so a tick storm at boot can't duplicate a file.
    try:
        story_pack_writer.start()
    except Exception as ex:
        print(f"[server] story_pack_writer failed to start: {ex}")
    # pitch-j1: KPI history recorder. Per-minute snapshot of agency KPIs
    # (and, via J2, per-persona load) into the durable kpi_history SQLite
    # ring. Module-singleton pattern matches the trend watcher above.
    try:
        kpi_history_recorder.start()
    except Exception as ex:
        print(f"[server] kpi_history_recorder failed to start: {ex}")
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

    # pitch-h5 (entanglement) — TalentTransferCascade bridges
    # ``intercompany-talent-transfer`` completions into four child
    # ``workflow.sub_spawned`` events + Person-OWNS-Asset reassignment so
    # the cosmic lens animates the cross-domain ripple.
    _ttc_off = None
    try:
        from api.server.services.ambient_agents.talent_transfer_cascade import (
            TalentTransferCascade,
        )
        app_state.talent_transfer_cascade = TalentTransferCascade(
            bus=app_state.bus,
            audit=getattr(app_state, "audit", None),
            graph=getattr(app_state, "entities", None),
        )
        app_state.talent_transfer_cascade.start()
        _ttc_off = app_state.talent_transfer_cascade.aclose
    except Exception as ex:
        print(f"[server] TalentTransferCascade failed to start: {ex}")

    # Wire bus -> hub fan-out inside the lifespan so each app instance owns
    # exactly one subscription. Previously this lived at module import time,
    # which under uvicorn --reload accumulated a fresh subscription per
    # reload — every event then fanned out N× and old AppState references
    # leaked. Capturing the unsubscribe and calling it on teardown closes
    # that loop.
    _bus_to_hub_off = app_state.bus.on_any(
        lambda e: app_state.hub.broadcast("fleet", e.model_dump())
    )

    # pitch-j6: subscribe the what's-new ring buffer to the four
    # learning-loop event types. Owned by the lifespan so each
    # uvicorn --reload cycle ends with a single subscription.
    _whats_new_off = _whats_new_attach(app_state.bus)

    try:
        yield
    finally:
        try:
            _whats_new_off()
        except Exception:
            pass
        try:
            _bus_to_hub_off()
        except Exception:
            pass
        if _ttc_off is not None:
            try:
                _ttc_off()
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
            vendor_block_watcher.stop()
        except Exception:
            pass
        try:
            brand_budget_watcher.stop()
        except Exception:
            pass
        try:
            subsidiary_capacity_watcher.stop()
        except Exception:
            pass
        try:
            auto_block_rule_learner.stop()
        except Exception:
            pass
        try:
            trend_cadence_watcher.stop()
        except Exception:
            pass
        try:
            story_pack_writer.stop()
        except Exception:
            pass
        try:
            kpi_history_recorder.stop()
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
    allow_origins=_cors_allowed_origins(),
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
from api.server.routes.dream_pass_exceptions import router as dream_pass_exceptions_router
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
from api.server.routes.decisions import router as decisions_router
# Blueprint microsite — composition tree + live observatory SSE
from api.server.routes.blueprint import router as blueprint_router
# Substrate registry surfaces (Phase 7 of feature-authority-and-personae-1).
from api.server.routes.personas import router as personas_router
from api.server.routes.authority import router as authority_router
# Governance kernel surface (Phase 4 of feature-agent-governance-toolkit-1).
from api.server.routes.governance import router as governance_router
# Entity-graph plane read API (Phase 1 TASK-030..-035).
from api.server.routes.entities import router as entities_router
# Phase 2 — accounts substrate.
from api.server.routes.accounts import router as accounts_router
from api.server.routes.functions import router as functions_router
from api.server.routes.functions_ambient import router as functions_ambient_router
from api.server.routes.cadences import router as cadences_router
# Cosmic Lens v2 — capabilities/entities city roster + affinity for the new viz
from api.server.routes.cities import router as cities_router
# Agency KPI panel — feature-enterprise-pitch-readiness-1 task pitch-e4.
from api.server.routes.kpis import router as kpis_router
# Network-effects holding view — feature-enterprise-pitch-readiness-1 task pitch-e6.
from api.server.routes.network import router as network_router
# Learning-loop diagnostics — feature-enterprise-pitch-readiness-1 Track I.
from api.server.routes.learning import router as learning_router
# Story-pack — feature-enterprise-pitch-readiness-1 task pitch-j5.
from api.server.routes.story_pack import router as story_pack_router
# What's-new dashboard — feature-enterprise-pitch-readiness-1 task pitch-j6.
from api.server.routes.whats_new import (
    router as whats_new_router,
    attach_to_bus as _whats_new_attach,
)
from api.server.routes.replay import router as replay_router
# Persona insights — autonomous-domain-insights v1 Phase 6.
from api.server.routes.insights import router as insights_router
# Demo trigger routes — autonomous-domain-insights v1.1 Phase A4.
from api.server.routes.demo_triggers import router as demo_triggers_router
# Live decision/insight ticker — autonomous-domain-insights v1.1 Phase D1.
from api.server.routes.ticker import router as ticker_router

for r in (stream_router, workflows_router, exceptions_router, policy_router,
          simulator_router, audit_router, evals_router, orchestration_router,
          durable_event_router, fleet_router, accuracy_router, policy_md_router,
          receipts_router, creative_campaign_assets_router,
          webhooks_servicenow_router, webhooks_finance_bp_router,
          a2a_router,
          portal_router, portal_voice_router, portal_interview_router,
          portal_admin_decisions_router,
          decisions_router,
          blueprint_router,
          personas_router, authority_router,
          governance_router,
          entities_router,
          accounts_router,
          functions_router,
          functions_ambient_router,
          cadences_router,
          cities_router,
          kpis_router,
          network_router,
          learning_router,
          replay_router,
          story_pack_router,
          whats_new_router,
          insights_router,
          demo_triggers_router,
          ticker_router,
          foundry_router,
          dream_pass_exceptions_router):
    app.include_router(r)

# Mount the built blueprint Vite bundle if present (production deploy).
# No-op in dev when web/blueprint/dist/ doesn't exist (Vite serves the
# page directly on :5275 and proxies /api back here).
from api.server.static_blueprint import mount_blueprint_static
_blueprint_mounted = mount_blueprint_static(app)
if _blueprint_mounted:
    print("[server] mounted blueprint bundle from web/blueprint/dist/")

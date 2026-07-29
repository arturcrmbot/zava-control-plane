"""Internal state/events/inject surfaces for the world simulator (JSON only —
not UX).

Two authorities can back these routes, never both at once (see the lifespan
wiring in ``api/server/main.py``):

  - ``app_state.world_service`` — the live ``ActorWorldService`` (spec
    2026-07-13, ``ZAVA_WORLD=support``): an explicit-actor SimPy simulation
    with a causal event journal. This is the primary authority.
  - ``app_state.world_engine`` — the aggregate ``WorldEngine`` (spec
    2026-07-10, ``ZAVA_WORLD=toy``): retained as a regression-only fallback
    when the actor service isn't active.

Routes, in the spirit of the existing internal/demo routes
(``routes/demo_triggers.py``, ``routes/internal_durable_event.py``):

  GET  /api/world/state                — snapshot of live world state + the
                                          last Durable responder run.
  GET  /api/world/events?after=<seq>   — journal catch-up (actor world only).
  POST /api/world/inject/demand_surge  — inject a demand surge.

Per the ponytail amendment to the Plan 2 spec, pause/resume/step/restart,
SSE streaming and the generic ``/control``/``/inject/{name}`` surfaces are
cut from this plan and deferred to Plan 3 (viewer). These exist so a proof
driver (or an operator) can drive and observe the world that runs inside the
FastAPI process. No frontend, no rendering.
"""
from __future__ import annotations

import asyncio
from typing import Literal

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from api.server.state import app_state
from api.server.services.world_bridge import WorldBridge
from verticals.telco.process_profiles import STANDARD_PROCESS_PROFILES

router = APIRouter(prefix="/api/world", tags=["world"])
_UI_SESSION_SAMPLE_PER_STATUS = 24


def _compact_telco_state(snapshot: dict) -> dict:
    if snapshot.get("scenario") != "telco":
        return snapshot

    compact = dict(snapshot)
    sessions = compact.get("sessions")
    if isinstance(sessions, list):
        counts: dict[str, int] = {}
        sampled_counts: dict[str, int] = {}
        sampled_sessions: list[dict] = []
        for session in sessions:
            status = str(session.get("status", "unknown"))
            counts[status] = counts.get(status, 0) + 1
            sampled = sampled_counts.get(status, 0)
            if sampled < _UI_SESSION_SAMPLE_PER_STATUS:
                sampled_sessions.append(session)
                sampled_counts[status] = sampled + 1
        compact["session_counts"] = counts
        compact["sessions"] = sampled_sessions

    subscribers = compact.pop("subscribers", None)
    if isinstance(subscribers, list):
        compact["subscriber_count"] = len(subscribers)

    subscriptions = compact.pop("subscriptions", None)
    if isinstance(subscriptions, list):
        compact["subscription_count"] = len(subscriptions)

    accounts = compact.get("accounts")
    if isinstance(accounts, list):
        compact["account_count"] = len(accounts)
        impact = compact.get("customer_impact")
        impacted_ids = set(
            impact.get("account_ids", [])
            if isinstance(impact, dict)
            else []
        )
        compact["accounts"] = [
            account
            for index, account in enumerate(accounts)
            if index == 0 or account.get("id") in impacted_ids
        ]

    return compact


class DemandSurgeRequest(BaseModel):
    """Body for ``POST /inject/demand_surge``. Every field is optional."""

    multiplier: float = Field(default=4, gt=1, allow_inf_nan=False)
    duration_minutes: float = Field(default=90, gt=0, allow_inf_nan=False)


class SiteFailureRequest(BaseModel):
    """Body for ``POST /inject/site_failure`` (telco). ``site_id`` optional —
    when omitted the world fails its busiest healthy site deterministically."""

    site_id: str | None = Field(default=None)


class CapacityPressureRequest(BaseModel):
    site_id: str = Field(min_length=1)
    utilization: float = Field(default=0.95, ge=0.9, le=1.0, allow_inf_nan=False)


class ServiceOrderRequest(BaseModel):
    account_id: str = Field(min_length=1)
    product: str = Field(min_length=1)
    requested_site_id: str = Field(min_length=1)


class WeatherRiskRequest(BaseModel):
    region: str = Field(min_length=1)
    severity: float = Field(gt=0, allow_inf_nan=False)
    duration_minutes: float = Field(gt=0, allow_inf_nan=False)


class SpareShortageRequest(BaseModel):
    region: str = Field(min_length=1)
    part_kind: str = Field(min_length=1)


class TechnicianUnavailableRequest(BaseModel):
    technician_id: str = Field(min_length=1)


class DirectDiagnosticRequest(BaseModel):
    """Explicit opt-in for a pack-owned disabled-world diagnostic."""

    mode: Literal["direct-diagnostic"]


class WorldResetRequest(BaseModel):
    seed: int | None = None


@router.get("/state")
async def world_state(compact: bool = False) -> dict:
    service = getattr(app_state, "world_service", None)
    if service is not None:
        snapshot = service.snapshot()
        if compact:
            snapshot = _compact_telco_state(snapshot)
        snapshot["last_response"] = getattr(app_state, "world_last_response", None)
        return snapshot
    engine = getattr(app_state, "world_engine", None)
    if engine is None:
        return {"enabled": False}
    st = engine.state
    return {
        "enabled": True,
        "pack": engine.pack.name,
        "stocks": {k: round(v, 3) for k, v in st.stocks.items()},
        "resources": {k: round(v, 3) for k, v in st.resources.items()},
        "signals": {k: round(v, 4) for k, v in st.signals.items()},
        "inputs": {k: round(v, 3) for k, v in st.inputs.items()},
        "last_response": getattr(app_state, "world_last_response", None),
    }


@router.get("/events")
async def world_events(
    after: int = 0,
    limit: int | None = Query(default=None, ge=1, le=1_000),
) -> dict:
    """Actor-world journal catch-up. Disabled unless the actor service runs."""
    service = getattr(app_state, "world_service", None)
    if service is None:
        return {"enabled": False, "latest_seq": 0, "events": []}
    events = service.events_after(after)
    if limit is not None:
        events = events[-limit:]
    return {
        "enabled": True,
        "latest_seq": len(service.runtime.journal),
        "events": events,
    }


@router.post("/diagnostics/{workflow_type}")
async def run_actor_world_diagnostic(
    workflow_type: str,
    body: DirectDiagnosticRequest,
) -> dict:
    """Run a pack-owned Durable diagnostic only while its actor world is off."""
    if getattr(app_state, "world_service", None) is not None:
        raise HTTPException(
            status_code=409,
            detail="actor-world diagnostic requires the live actor world to be disabled",
        )

    runtime = app_state.runtime
    registration = runtime.pack.worlds.get(runtime.world_name or "")
    build_input = (
        getattr(registration, "build_diagnostic_input", None)
        if registration is not None
        else None
    )
    if build_input is None:
        raise HTTPException(
            status_code=404,
            detail=f"no disabled-world diagnostic is registered for {workflow_type!r}",
        )

    try:
        sensor_event, observation = build_input(workflow_type)
        responder = next(
            candidate
            for candidate in registration.responders.values()
            if candidate.workflow_type == workflow_type
        )
    except (StopIteration, ValueError) as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    workflow_id = await WorldBridge(app_state).start_diagnostic(
        sensor_event=sensor_event,
        responder=responder,
        observation=observation,
    )
    source_sensor_event_id = (sensor_event.get("payload") or {}).get(
        "source_sensor_event_id"
    )
    if not isinstance(source_sensor_event_id, str):
        raise HTTPException(
            status_code=500,
            detail="diagnostic input did not preserve its source sensor event id",
        )
    return {
        "workflow_id": workflow_id,
        "mode": body.mode,
        "source_sensor_event_id": source_sensor_event_id,
    }


@router.get("/scene")
async def world_scene() -> dict:
    service = getattr(app_state, "world_service", None)
    registration = getattr(service, "registration", None)
    scene = getattr(registration, "scene", None)
    if scene is None:
        return {"enabled": False}
    return {"enabled": True, **dict(scene)}


@router.post("/reset")
async def reset_world(body: WorldResetRequest = WorldResetRequest()) -> dict:
    service = getattr(app_state, "world_service", None)
    reset = getattr(service, "reset", None)
    if reset is None:
        return {"ok": False, "error": "actor world not enabled"}
    seed = service.seed if body.seed is None else body.seed
    bridge = getattr(app_state, "world_bridge", None)
    if bridge is not None:
        bridge.stop()
    reset(seed)
    world_task = app_state.world_task
    if world_task is None or world_task.done():
        app_state.world_task = asyncio.create_task(service.run())
    if bridge is not None:
        bridge.start()
    return {"ok": True, "seed": seed, "sim_time": service.runtime.now}


@router.post("/inject/demand_surge")
async def inject_demand_surge(body: DemandSurgeRequest = DemandSurgeRequest()) -> dict:
    service = getattr(app_state, "world_service", None)
    if service is not None:
        service.inject_demand_surge(body.multiplier, body.duration_minutes)
        return {
            "ok": True,
            "sim_time": service.runtime.now,
            "multiplier": body.multiplier,
            "duration_minutes": body.duration_minutes,
        }
    engine = getattr(app_state, "world_engine", None)
    if engine is not None:
        engine.inject("demand_surge")
        return {"ok": True, "injected": "demand_surge"}
    return {"ok": False, "error": "world engine not enabled (set ZAVA_WORLD)"}


@router.post("/inject/site_failure")
async def inject_site_failure(body: SiteFailureRequest = SiteFailureRequest()) -> dict:
    """Fail one real cell site (telco actor world). Deterministic default site."""
    service = getattr(app_state, "world_service", None)
    inject = getattr(service, "inject_site_failure", None) if service is not None else None
    if inject is None:
        return {"ok": False, "error": "telco world not enabled (set ZAVA_WORLD=telco)"}
    try:
        site_id = inject(body.site_id)
    except ValueError as exc:
        return {"ok": False, "error": str(exc)}
    return {"ok": True, "sim_time": service.runtime.now, "site_id": site_id}


@router.post("/inject/capacity_pressure")
async def inject_capacity_pressure(body: CapacityPressureRequest) -> dict:
    """Constrain a healthy Telco site's available capacity with world evidence."""
    service = getattr(app_state, "world_service", None)
    inject = (
        getattr(service, "inject_capacity_pressure", None)
        if service is not None
        else None
    )
    if inject is None:
        return {"ok": False, "error": "telco world not enabled (set ZAVA_WORLD=telco)"}
    try:
        site_id = inject(body.site_id, utilization=body.utilization)
    except ValueError as exc:
        return {"ok": False, "error": str(exc)}
    return {
        "ok": True,
        "sim_time": service.runtime.now,
        "site_id": site_id,
        "utilization": body.utilization,
    }


@router.post("/service-orders")
async def submit_service_order(body: ServiceOrderRequest) -> dict:
    service = getattr(app_state, "world_service", None)
    submit = getattr(service, "submit_service_order", None)
    if submit is None:
        return {"ok": False, "error": "telco world not enabled"}
    try:
        order_id = submit(
            account_id=body.account_id,
            product=body.product,
            requested_site_id=body.requested_site_id,
        )
    except ValueError as exc:
        return {"ok": False, "error": str(exc)}
    return {"ok": True, "order_id": order_id, "sim_time": service.runtime.now}


@router.post("/inject/weather-risk")
async def inject_weather_risk(body: WeatherRiskRequest) -> dict:
    """Inject a regional weather risk event (telco actor world)."""
    service = getattr(app_state, "world_service", None)
    inject = (
        getattr(service, "inject_weather_risk", None) if service is not None else None
    )
    if inject is None:
        return {"ok": False, "error": "telco world not enabled (set ZAVA_WORLD=telco)"}
    try:
        event_id = inject(body.region, body.severity, body.duration_minutes)
    except ValueError as exc:
        return {"ok": False, "error": str(exc)}
    return {
        "ok": True,
        "sim_time": service.runtime.now,
        "event_id": event_id,
        "region": body.region,
    }


@router.post("/inject/spare-shortage")
async def inject_spare_shortage(body: SpareShortageRequest) -> dict:
    """Zero out one region's spare stock for a part kind (telco actor world)."""
    service = getattr(app_state, "world_service", None)
    inject = (
        getattr(service, "inject_spare_shortage", None) if service is not None else None
    )
    if inject is None:
        return {"ok": False, "error": "telco world not enabled (set ZAVA_WORLD=telco)"}
    try:
        stock_id = inject(body.region, body.part_kind)
    except ValueError as exc:
        return {"ok": False, "error": str(exc)}
    return {"ok": True, "sim_time": service.runtime.now, "stock_id": stock_id}


@router.post("/inject/technician-unavailable")
async def inject_technician_unavailable(body: TechnicianUnavailableRequest) -> dict:
    """Mark one technician unavailable (telco actor world)."""
    service = getattr(app_state, "world_service", None)
    inject = (
        getattr(service, "inject_technician_unavailable", None)
        if service is not None
        else None
    )
    if inject is None:
        return {"ok": False, "error": "telco world not enabled (set ZAVA_WORLD=telco)"}
    try:
        technician_id = inject(body.technician_id)
    except ValueError as exc:
        return {"ok": False, "error": str(exc)}
    return {
        "ok": True,
        "sim_time": service.runtime.now,
        "technician_id": technician_id,
    }


@router.post("/scenarios/{name}")
async def run_world_scenario(name: str) -> dict:
    service = getattr(app_state, "world_service", None)
    run = getattr(service, "run_scenario", None) if service is not None else None
    if run is None:
        return {
            "ok": False,
            "error": "actor world does not expose deterministic scenarios",
        }
    try:
        result = run(name)
    except ValueError as exc:
        return {"ok": False, "error": str(exc)}
    return {"ok": True, **result}


def _runnable_reference_processes(service: object) -> frozenset[str]:
    """Reference-process types the *active* world can run.

    A world scenario may declare its own ``reference_process_types``. Scenarios
    that don't declare them keep the historical telco standard-profile set, so
    this route's contract for those worlds is unchanged.
    """
    scenario = getattr(service, "scenario", None)
    declared = getattr(scenario, "reference_process_types", None)
    if declared:
        return frozenset(declared)
    return frozenset(STANDARD_PROCESS_PROFILES)


@router.post("/processes/{workflow_type}/run")
async def run_reference_process(workflow_type: str) -> dict:
    service = getattr(app_state, "world_service", None)
    run = (
        getattr(service, "run_reference_process", None)
        if service is not None
        else None
    )
    if run is None:
        return {
            "ok": False,
            "error": "actor world not enabled (set ZAVA_VERTICAL)",
        }
    if workflow_type not in _runnable_reference_processes(service):
        return {
            "ok": False,
            "error": f"unknown reference process: {workflow_type!r}",
        }
    try:
        result = run(workflow_type)
    except ValueError as exc:
        return {"ok": False, "error": str(exc)}
    return {
        "ok": True,
        "workflow_type": workflow_type,
        **result,
        "sim_time": service.runtime.now,
    }

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

from fastapi import APIRouter
from pydantic import BaseModel, Field

from api.server.state import app_state
from verticals.telco.process_profiles import STANDARD_PROCESS_PROFILES

router = APIRouter(prefix="/api/world", tags=["world"])


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


TELCO_SCENARIOS = frozenset(
    {
        "storm-cascade",
        "maintenance-save",
        "capacity-revenue",
        "vulnerable-retention",
    }
)


@router.get("/state")
async def world_state() -> dict:
    service = getattr(app_state, "world_service", None)
    if service is not None:
        snapshot = service.snapshot()
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
async def world_events(after: int = 0) -> dict:
    """Actor-world journal catch-up. Disabled unless the actor service runs."""
    service = getattr(app_state, "world_service", None)
    if service is None:
        return {"enabled": False, "latest_seq": 0, "events": []}
    return {
        "enabled": True,
        "latest_seq": len(service.runtime.journal),
        "events": service.events_after(after),
    }


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
async def run_telco_scenario(name: str) -> dict:
    if name not in TELCO_SCENARIOS:
        return {"ok": False, "error": f"unknown Telco scenario: {name!r}"}
    service = getattr(app_state, "world_service", None)
    run = getattr(service, "run_scenario", None) if service is not None else None
    if run is None:
        return {
            "ok": False,
            "error": "telco world not enabled (set ZAVA_WORLD=telco)",
        }
    try:
        result = run(name)
    except ValueError as exc:
        return {"ok": False, "error": str(exc)}
    return {"ok": True, **result}


def _runnable_reference_processes(service: object) -> frozenset[str]:
    """Reference-process types the *active* world can run.

    A world scenario may declare its own ``reference_process_types`` (the
    Fashion world does, one per pack domain). Scenarios that don't declare
    them — telco/support — keep the historical telco standard-profile set, so
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

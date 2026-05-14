"""Read-only routes that surface the persona registry.

Backs:
  - GET /api/personas              — full list
  - GET /api/personas/by-archetype — grouped
  - GET /api/personas/by-function  — grouped
  - GET /api/personas/{role}       — single

The registry data lives in `api/shared/personas.py`. These routes do
zero IO beyond a dict walk; safe to call frequently. Used by the
blueprint microsite's persona library and any future operator-UI
surface.
"""
from __future__ import annotations

from dataclasses import asdict

from fastapi import APIRouter, HTTPException

from api.shared import personas as personas_registry
from api.server.data_fabric.narrative_arcs import ARCS as _NARRATIVE_ARCS


router = APIRouter(prefix="/api/personas")


def _serialise(p: personas_registry.Persona) -> dict:
    return asdict(p)


@router.get("")
@router.get("/", include_in_schema=False)
async def list_personas() -> dict:
    """Return every registered persona plus aggregate counts."""
    items = [_serialise(p) for p in personas_registry.PERSONAS.values()]
    items.sort(key=lambda d: d["role"])
    return {
        "total": len(items),
        "by_archetype": {
            arch: len(personas_registry.by_archetype(arch))  # type: ignore[arg-type]
            for arch in sorted(personas_registry.all_archetypes())
        },
        "by_function": {
            fn: len(personas_registry.by_function(fn))  # type: ignore[arg-type]
            for fn in sorted(personas_registry.all_functions())
        },
        "uses_authority_mcp": len(personas_registry.authority_users()),
        "items": items,
    }


@router.get("/colors")
async def persona_colors() -> dict[str, str | None]:
    """Return a tiny ``{role: display_color | null}`` map for every registered
    persona. Used by the cosmic-lens HUD (autonomous-domain-insights v1.1
    Phase F1) to tint persona-name spans in the DecisionTicker and to
    flash workflow particles when a gate is decided. Read once at boot
    by the frontend; payload is small enough to inline."""
    return {
        role: p.display_color for role, p in personas_registry.PERSONAS.items()
    }


@router.get("/by-archetype")
async def by_archetype() -> dict:
    out: dict[str, list[dict]] = {}
    for arch in sorted(personas_registry.all_archetypes()):
        out[arch] = sorted(
            (_serialise(p) for p in personas_registry.by_archetype(arch)),  # type: ignore[arg-type]
            key=lambda d: d["role"],
        )
    return out


@router.get("/by-function")
async def by_function() -> dict:
    out: dict[str, list[dict]] = {}
    for fn in sorted(personas_registry.all_functions()):
        out[fn] = sorted(
            (_serialise(p) for p in personas_registry.by_function(fn)),  # type: ignore[arg-type]
            key=lambda d: d["role"],
        )
    return out


@router.get("/narrative-arcs")
async def narrative_arcs() -> list[dict]:
    """Return the pitch demo's hand-curated named individuals (Pitch D5).

    Static, public read. Used by the cosmic-lens HUD to render a
    stacked-deck panel of named humans (photo, name, role, one-liner)
    instead of anonymous role ids. Registered before ``/{role}`` so
    the path doesn't get swallowed by the catch-all matcher below.
    """
    return [
        {
            "employee_id": a.employee_id,
            "name": a.name,
            "role": a.role,
            "photo_url": a.photo_url,
            "one_liner": a.one_liner,
            "arc": a.arc,
            "function": a.function,
        }
        for a in _NARRATIVE_ARCS
    ]


@router.post("/sweep")
async def sweep_pending() -> dict:
    """Drain every workflow currently parked at a HITL gate by running the
    matching persona's decision policy. Honours ``PERSONA_AUTO_CLOSE`` —
    workflows whose persona is not in the auto-close set are left alone."""
    from api.server.services.persona_responder import sweep_pending_hitl
    return await sweep_pending_hitl()


# pitch-j2 — per-persona load history. Registered BEFORE the catch-all
# ``/{role}`` matcher below so the path doesn't get swallowed.
_J2_METRICS = {"queue_depth": "persona_queue_depth",
               "decisions_per_min": "persona_decisions_per_min"}

_HISTORY_WINDOW_SUFFIXES = {"s": 1, "m": 60, "h": 3600, "d": 86400}


def _parse_window_seconds(window: str) -> int:
    s = (window or "").strip().lower()
    if not s:
        return 3600
    if s[-1] in _HISTORY_WINDOW_SUFFIXES:
        try:
            return int(s[:-1]) * _HISTORY_WINDOW_SUFFIXES[s[-1]]
        except ValueError:
            return 3600
    try:
        return int(s)
    except ValueError:
        return 3600


@router.get("/{role}/history")
async def persona_history(
    role: str, metric: str = "queue_depth", window: str = "60m"
) -> dict:
    """Return the per-minute load series for ``role``.

    ``metric`` is one of ``queue_depth`` or ``decisions_per_min`` and
    maps onto the ``persona_queue_depth`` / ``persona_decisions_per_min``
    samples written by the ``kpi_history_recorder`` ambient agent."""
    kpi_id = _J2_METRICS.get(metric)
    if kpi_id is None:
        raise HTTPException(
            status_code=400,
            detail=f"metric must be one of {sorted(_J2_METRICS)}",
        )
    from api.server.services import kpi_history
    seconds = _parse_window_seconds(window)
    pts = kpi_history.series(kpi_id, since_seconds=seconds, dim=role)
    return {
        "role": role,
        "metric": metric,
        "window_seconds": seconds,
        "points": [{"ts": t, "value": v} for t, v in pts],
    }


@router.get("/{role}")
async def get_persona(role: str) -> dict:
    p = personas_registry.get(role)
    if p is None:
        raise HTTPException(status_code=404, detail=f"persona '{role}' not registered")
    return _serialise(p)


# ---------------------------------------------------------------------------
# Org Ops v2 — current-state endpoint used by all three operator views.
# Path is `/_state` to avoid colliding with the existing /{role} matcher
# above (FastAPI registers routes in order; /{role} would shadow /state).
# ---------------------------------------------------------------------------
import time as _time
from collections import defaultdict as _defaultdict
from api.server.state import app_state as _app_state
from api.server.services import persona_responder as _pr


@router.get("/index/state")
async def personas_state():
    """One row per known persona role with current state + last decision summary.

    State is one of:
      - ``working``           : currently has a pending HITL gate awaiting decision
      - ``recently_decided``  : last decision <= 60s ago, no pending gates
      - ``idle``              : no pending gates, last decision > 60s ago

    Used by Approach A persona strip, Approach B channel avatars, Approach C
    gate annotations.
    """
    pending_by_role, last_decision_by_role = _compute_persona_pending_and_decisions()
    now = _time.time()
    rows: list[dict] = []
    auto_close = _pr._auto_close_set()
    all_roles = set(_pr.PERSONA_DEFINITIONS.keys()) | set(pending_by_role.keys()) | set(last_decision_by_role.keys())
    for role in sorted(all_roles):
        pending = pending_by_role.get(role, [])
        last = last_decision_by_role.get(role)
        last_age = (now - last["ts"]) if last and last.get("ts") else None
        if pending:
            state = "working"
        elif last_age is not None and last_age <= 60:
            state = "recently_decided"
        else:
            state = "idle"
        rows.append({
            "role": role,
            "state": state,
            "auto_close": _pr._role_auto_closes(role, auto_close),
            "pending_count": len(pending),
            "pending": pending[:5],
            "last_decision": last,
            "last_decision_age_s": round(last_age, 1) if last_age is not None else None,
        })
    return rows


def _compute_persona_pending_and_decisions() -> tuple[dict[str, list[dict]], dict[str, dict]]:
    """Walk every workflow and bucket awaiting_hitl + decisions by persona role.

    Returns ``(pending_by_role, last_decision_by_role)``. Extracted from
    ``personas_state`` so other routes (notably ``/api/cities/{id}`` for
    the click-to-inspect drawer) can answer 'which workflows are parked
    on this persona right now?' without going through HTTP.
    """
    now = _time.time()
    pending_by_role: dict[str, list[dict]] = _defaultdict(list)
    last_decision_by_role: dict[str, dict] = {}

    try:
        from api.shared.domains import DOMAINS  # type: ignore
        _domains_by_type = DOMAINS if isinstance(DOMAINS, dict) else {}
    except Exception:
        _domains_by_type = {}

    for w in _app_state.store.list_workflows():
        if w.status == "awaiting_hitl":
            ctx = (w.payload or {}).get("hitl_context") or {}
            persona_role = (
                ctx.get("persona")
                or (w.payload or {}).get("persona")
                or None
            )
            # Fallback: look up persona via DOMAINS hitl_gates roster.
            # Match the workflow's current_phase against gate_phase first;
            # if no exact match, fall back to the first declared gate
            # (cosmic-lens accuracy is a parked rocket at the right
            # function family).
            if not persona_role:
                domain = _domains_by_type.get(w.type)
                if domain is not None:
                    gates = getattr(domain, "hitl_gates", None) or []
                    for gate in gates:
                        if getattr(gate, "gate_phase", None) == w.current_phase:
                            persona_role = (
                                getattr(gate, "persona", None)
                                or getattr(gate, "persona_role", None)
                            )
                            break
                    if not persona_role:
                        for gate in gates:
                            cand = (
                                getattr(gate, "persona", None)
                                or getattr(gate, "persona_role", None)
                            )
                            if cand:
                                persona_role = cand
                                break
            if persona_role:
                pending_by_role[persona_role].append({
                    "workflow_id": w.id,
                    "workflow_type": w.type,
                    "phase": w.current_phase,
                    "since": w.created_at,
                    "age_s": round(now - float(w.created_at or now), 1),
                })

        for d in (w.payload or {}).get("decisions") or []:
            role = d.get("persona_role")
            if not role:
                continue
            try:
                import datetime as _dt
                ts_iso = d.get("decided_at")
                ts_val = (
                    _dt.datetime.fromisoformat(ts_iso).timestamp()
                    if isinstance(ts_iso, str)
                    else float(ts_iso or 0.0)
                )
            except Exception:
                ts_val = 0.0
            cur = last_decision_by_role.get(role)
            if cur is None or ts_val > cur.get("ts", 0.0):
                last_decision_by_role[role] = {
                    "ts": ts_val,
                    "workflow_id": w.id,
                    "verdict": d.get("verdict"),
                    "phase": d.get("phase"),
                    "reason": d.get("reason"),
                }

    return pending_by_role, last_decision_by_role

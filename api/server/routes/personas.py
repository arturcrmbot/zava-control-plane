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
    now = _time.time()
    pending_by_role: dict[str, list[dict]] = _defaultdict(list)
    last_decision_by_role: dict[str, dict] = {}

    for w in _app_state.store.list_workflows():
        if w.status == "awaiting_hitl":
            ctx = (w.payload or {}).get("hitl_context") or {}
            persona_role = (
                ctx.get("persona")
                or (w.payload or {}).get("persona")
                or None
            )
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
            "auto_close": role in auto_close,
            "pending_count": len(pending),
            "pending": pending[:5],
            "last_decision": last,
            "last_decision_age_s": round(last_age, 1) if last_age is not None else None,
        })
    return rows

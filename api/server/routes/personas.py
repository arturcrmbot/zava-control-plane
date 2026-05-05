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

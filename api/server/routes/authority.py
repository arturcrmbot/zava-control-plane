"""Read-only routes that surface the delegated-authority MCP.

Backs:
  - GET  /api/authority/health   — proxy the MCP /health
  - POST /api/authority/resolve  — body { action, value?, category?, ... }
  - POST /api/authority/check    — body { role, action, value?, category?, ... }
  - GET  /api/authority/matrix   — full ordered ruleset (read-through)

The route does no caching — the MCP itself is a sub-millisecond rule
walk and `/reload` lets the JSON be edited live during demos. Wraps
`api.server.mcp_tools.delegated_authority` so the underlying transport
(httpx) and Pydantic shapes are reused.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

import httpx
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from api.server.mcp_tools.delegated_authority import (
    ApproverResolution,
    AuthorityCheck,
    check_authority,
    resolve_approver,
    _base_url,
)


router = APIRouter(prefix="/api/authority")

_MATRIX_PATH = Path(__file__).resolve().parents[3] / "data" / "synthetic" / "authority" / "matrix.json"


class _ResolveBody(BaseModel):
    action: str = Field(description="What is being approved (snake_case action constant).")
    value: float | None = None
    category: str | None = None
    requester_role: str | None = None
    business_unit: str | None = None
    geography: str | None = None


class _CheckBody(BaseModel):
    role: str
    action: str
    value: float | None = None
    category: str | None = None
    requester_role: str | None = None
    business_unit: str | None = None
    geography: str | None = None


@router.get("/health")
async def authority_health() -> dict[str, Any]:
    """Proxy the MCP /health so any UI can render a single status badge."""
    try:
        resp = httpx.get(f"{_base_url()}/health", timeout=3.0)
        resp.raise_for_status()
        return resp.json()
    except httpx.HTTPError as ex:
        raise HTTPException(
            status_code=503,
            detail=f"authority MCP unreachable at {_base_url()}: {ex}",
        )


@router.post("/resolve")
async def authority_resolve(body: _ResolveBody) -> ApproverResolution:
    try:
        return resolve_approver(
            action=body.action,
            value=body.value,
            category=body.category,
            requester_role=body.requester_role,
            business_unit=body.business_unit,
            geography=body.geography,
        )
    except httpx.HTTPError as ex:
        raise HTTPException(status_code=503, detail=str(ex))


@router.post("/check")
async def authority_check_route(body: _CheckBody) -> AuthorityCheck:
    try:
        return check_authority(
            role=body.role,
            action=body.action,
            value=body.value,
            category=body.category,
            requester_role=body.requester_role,
            business_unit=body.business_unit,
            geography=body.geography,
        )
    except httpx.HTTPError as ex:
        raise HTTPException(status_code=503, detail=str(ex))


@router.get("/matrix")
async def authority_matrix() -> dict[str, Any]:
    """Read the matrix from disk and return it. Mirrors what the MCP serves."""
    if not _MATRIX_PATH.exists():
        raise HTTPException(status_code=404, detail=f"matrix not found at {_MATRIX_PATH}")
    rules = json.loads(_MATRIX_PATH.read_text(encoding="utf-8"))
    actions = sorted({r.get("action") for r in rules if r.get("action")})
    return {
        "source": str(_MATRIX_PATH),
        "rule_count": len(rules),
        "actions": actions,
        "rules": rules,
    }

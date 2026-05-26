"""Read-only routes that surface the delegated-authority matrix.

Backs:
  - GET  /api/authority/health   — proxy the MCP /health (always HTTP)
  - POST /api/authority/resolve  — body { action, value?, category?, ... }
  - POST /api/authority/check    — body { role, action, value?, category?, ... }
  - GET  /api/authority/matrix   — full ordered ruleset (read-through)

Resolve / check route through the in-process governance kernel by
default (Phase 3 TASK-022..024 of plan/feature-agent-governance-toolkit-1.md):
both wrap ``api.server.mcp_tools.delegated_authority.resolve_approver`` /
``check_authority`` which prefer ``governance.kernel().resolve_approver(...)``
and only fall back to HTTP when ``AUTHORITY_MCP_URL`` is set in env
(Foundry-IQ engagement-POC swap-in seam, REQ-002).

The /health endpoint always uses HTTP because it intentionally probes
liveness of the configured MCP, not the in-process kernel (which is
trivially healthy whenever this process is running).
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
    """Report authority backend liveness.

    Backends (mirrors :func:`api.server.mcp_tools.delegated_authority._http_fallback_enabled`):

    - **In-process kernel** (default): when ``AUTHORITY_MCP_URL`` is unset,
      ``resolve``/``check`` route through the governance kernel. There is
      no HTTP hop to probe — instead we report green when the kernel has
      loaded a non-empty matrix.
    - **HTTP MCP** (engagement-POC swap-in): when ``AUTHORITY_MCP_URL`` is
      set, we proxy ``GET <url>/health`` so the UI can render a single
      status badge.
    """
    from api.server.mcp_tools.delegated_authority import _http_fallback_enabled

    if not _http_fallback_enabled():
        from api.server.services.governance.kernel import kernel

        try:
            rule_count = len(kernel()._matrix)
        except Exception as ex:  # pragma: no cover - defensive
            raise HTTPException(
                status_code=503,
                detail=f"in-process authority kernel unavailable: {ex}",
            )
        return {
            "ok": rule_count > 0,
            "backend": "in-process",
            "rule_count": rule_count,
        }

    try:
        resp = httpx.get(f"{_base_url()}/health", timeout=3.0)
        resp.raise_for_status()
        payload = resp.json()
    except httpx.HTTPError as ex:
        raise HTTPException(
            status_code=503,
            detail=f"authority MCP unreachable at {_base_url()}: {ex}",
        )
    if isinstance(payload, dict):
        payload.setdefault("backend", "http")
    return payload


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

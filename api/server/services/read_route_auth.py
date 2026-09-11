"""Lightweight per-request actor dependency for sensitive read routes.

The substrate's existing identity primitives
(:mod:`api.server.services.governance.identity` and
:mod:`api.server.services.audit_logger`) sign *agent* actions for the
audit ledger, but there is no human-actor request gate. This module
plugs that gap for the four read surfaces called out in
``plan/refactor-repo-coherence-remediation-1.md`` task
``c6-audit-evals-entities-authz`` (audit, evals, entities, cities)
**without** introducing a new auth library.

Modes, switched by the ``READ_ROUTE_AUTH`` env var:

* ``platform`` — use the Entra principal injected by configured ACA/App
  Service authentication. Caller-supplied ``X-Actor-*`` headers are ignored.
* ``enforce`` — legacy local-test mode requiring ``X-Actor-Id``. This is
  not production authentication.
* anything else (default, including unset) — local-PoC ergonomics: a
  synthetic ``local-dev`` / ``local`` actor is stamped on every
  request so handlers always have an actor to project responses for.

The projector (:func:`project_for_role`) redacts ``prompt`` /
``response`` shaped fields for roles other than ``cfo`` / ``gc``.
"""
from __future__ import annotations

import base64
import binascii
import json
import os
from dataclasses import dataclass
from typing import Any

from fastapi import Header, HTTPException


_ENV_FLAG = "READ_ROUTE_AUTH"
_ENFORCE_VALUE = "enforce"
_PLATFORM_ROLES = {
    "Zava.CFO": "cfo",
    "Zava.Executive": "executive",
    "Zava.GC": "gc",
    "Zava.Operator": "operator",
    "Zava.Viewer": "viewer",
}

# Roles that may see raw prompts/responses/details in audit + entity
# payloads. CFO and General Counsel are the substrate-wide privileged
# governance personae; everyone else gets a redacted projection.
_PRIVILEGED_ROLES: frozenset[str] = frozenset({"cfo", "gc"})

# Field names whose values are unconditionally redacted for non-
# privileged roles. Keep narrow on purpose — the projector should be
# obvious to read at a glance, not a deny-list game of whack-a-mole.
_REDACTED_KEYS: frozenset[str] = frozenset({
    "prompt",
    "prompt_text",
    "response",
    "response_text",
    "messages",
})

_REDACTED_PLACEHOLDER = "[redacted]"


@dataclass(frozen=True)
class Actor:
    """Identity stamped on every read-route request."""

    id: str
    role: str

    @property
    def is_privileged(self) -> bool:
        return self.role in _PRIVILEGED_ROLES


def _enforce_mode() -> bool:
    raw = os.environ.get(_ENV_FLAG, "").strip().lower()
    return raw in {_ENFORCE_VALUE, "platform"}


def _platform_actor(header: str | None) -> Actor:
    """Decode a trusted platform header, not an arbitrary bearer token.

    Enable only behind configured platform authentication, which removes
    caller-supplied principal headers before injecting its own identity.
    """
    tenant = os.environ.get("AUTH_TENANT_ID", "").strip().lower()
    if not tenant:
        raise HTTPException(503, "platform_auth_not_configured: AUTH_TENANT_ID required")
    if not isinstance(header, str) or not header:
        raise HTTPException(401, "missing_platform_identity")
    try:
        principal = json.loads(base64.b64decode(header, validate=True))
    except (binascii.Error, ValueError, UnicodeDecodeError) as exc:
        raise HTTPException(401, "invalid_platform_identity") from exc
    if not isinstance(principal, dict) or principal.get("auth_typ") != "aad":
        raise HTTPException(401, "invalid_platform_identity")
    claims = principal.get("claims")
    if not isinstance(claims, list) or any(
        not isinstance(claim, dict)
        or not isinstance(claim.get("typ"), str)
        or not isinstance(claim.get("val"), str)
        for claim in claims
    ):
        raise HTTPException(401, "invalid_platform_claims")
    tenants = {
        claim["val"].lower() for claim in claims
        if claim["typ"] in {"tid", "http://schemas.microsoft.com/identity/claims/tenantid"}
    }
    if tenants != {tenant}:
        raise HTTPException(403, "wrong_tenant")
    identities = {
        claim["val"] for claim in claims
        if claim["typ"] in {"oid", "http://schemas.microsoft.com/identity/claims/objectidentifier"}
        and claim["val"].strip()
    }
    if len(identities) != 1:
        raise HTTPException(401, "missing_platform_object_id")
    role_types = {"roles", "http://schemas.microsoft.com/ws/2008/06/identity/claims/role"}
    if isinstance(principal.get("role_typ"), str):
        role_types.add(principal["role_typ"])
    assigned = {claim["val"] for claim in claims if claim["typ"] in role_types}
    role = next((mapped for name, mapped in _PLATFORM_ROLES.items() if name in assigned), "viewer")
    return Actor(id=identities.pop(), role=role)


async def require_actor(
    x_actor_id: str | None = Header(default=None),
    x_actor_role: str | None = Header(default=None),
    x_ms_client_principal: str | None = Header(default=None),
) -> Actor:
    """FastAPI dependency: resolve the request actor.

    Read fresh from the environment on every call so test fixtures can
    flip the flag with ``monkeypatch.setenv`` mid-suite without app
    re-import. In ``enforce`` mode a missing ``X-Actor-Id`` is a hard
    401; in default mode we stamp ``local-dev`` so downstream code can
    always assume an :class:`Actor` is present.
    """
    if os.environ.get(_ENV_FLAG, "").strip().lower() == "platform":
        return _platform_actor(x_ms_client_principal)
    if _enforce_mode():
        if not x_actor_id:
            raise HTTPException(
                status_code=401,
                detail="missing_actor: X-Actor-Id header required",
            )
        return Actor(id=x_actor_id, role=(x_actor_role or "viewer").strip().lower())
    return Actor(
        id=(x_actor_id or "local-dev").strip(),
        role=(x_actor_role or "local").strip().lower(),
    )


def _redact_value(value: Any) -> Any:
    if isinstance(value, dict):
        return {k: _REDACTED_PLACEHOLDER if k in _REDACTED_KEYS else _redact_value(v)
                for k, v in value.items()}
    if isinstance(value, list):
        return [_redact_value(v) for v in value]
    return value


def project_for_role(payload: Any, role: str) -> Any:
    """Return ``payload`` with prompt/response-shaped fields redacted
    for non-privileged roles.

    Privileged roles (``cfo``, ``gc``) get the payload back unchanged.
    Everyone else gets a deep-copied projection where any dict key in
    :data:`_REDACTED_KEYS` is replaced with ``"[redacted]"`` at any
    nesting depth. Lists/dicts are recursed into; scalars pass through.
    """
    if (role or "").strip().lower() in _PRIVILEGED_ROLES:
        return payload
    if isinstance(payload, dict):
        return {k: _REDACTED_PLACEHOLDER if k in _REDACTED_KEYS else _redact_value(v)
                for k, v in payload.items()}
    if isinstance(payload, list):
        return [project_for_role(item, role) for item in payload]
    return payload

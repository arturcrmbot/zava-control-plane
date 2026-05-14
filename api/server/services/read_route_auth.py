"""Lightweight per-request actor dependency for sensitive read routes.

The substrate's existing identity primitives
(:mod:`api.server.services.governance.identity` and
:mod:`api.server.services.audit_logger`) sign *agent* actions for the
audit ledger, but there is no human-actor request gate. This module
plugs that gap for the four read surfaces called out in
``plan/refactor-repo-coherence-remediation-1.md`` task
``c6-audit-evals-entities-authz`` (audit, evals, entities, cities)
**without** introducing a new auth library.

Two modes, switched by the ``READ_ROUTE_AUTH`` env var:

* ``enforce`` — request MUST carry an ``X-Actor-Id`` header (and may
  carry ``X-Actor-Role``). Missing → ``401``.
* anything else (default, including unset) — local-PoC ergonomics: a
  synthetic ``local-dev`` / ``local`` actor is stamped on every
  request so handlers always have an actor to project responses for.

The projector (:func:`project_for_role`) redacts ``prompt`` /
``response`` shaped fields for roles other than ``cfo`` / ``gc``.
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any

from fastapi import Header, HTTPException


_ENV_FLAG = "READ_ROUTE_AUTH"
_ENFORCE_VALUE = "enforce"

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
    return raw == _ENFORCE_VALUE


async def require_actor(
    x_actor_id: str | None = Header(default=None),
    x_actor_role: str | None = Header(default=None),
) -> Actor:
    """FastAPI dependency: resolve the request actor.

    Read fresh from the environment on every call so test fixtures can
    flip the flag with ``monkeypatch.setenv`` mid-suite without app
    re-import. In ``enforce`` mode a missing ``X-Actor-Id`` is a hard
    401; in default mode we stamp ``local-dev`` so downstream code can
    always assume an :class:`Actor` is present.
    """
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

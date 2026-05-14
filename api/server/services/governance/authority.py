"""In-process authority resolver — Phase 3 of plan/feature-agent-governance-toolkit-1.md.

Mirrors ``mocks/authority-mcp/resolver.ts`` byte-for-byte: ordered matrix
walk, first-match wins, wildcard ``"*"`` semantics on scope fields,
``value_band_gbp`` inclusive on both bounds, and a non-monetary band
(``min`` and ``max`` both ``null``) matches regardless of supplied value.

This module is consumed by :class:`api.server.services.governance.kernel.GovernanceKernel`
which exposes :meth:`resolve_approver` / :meth:`check_authority` to
external callers (replacing the HTTP round-trip to ``mocks/authority-mcp/``).

Pure functions, no I/O, no global state. Reentrant. The test
``tests/api/server/services/governance/test_authority_parity.py`` (TASK-021)
proves byte-identical output against the Node mock for the 8 canonical
resolutions.
"""
from __future__ import annotations

import logging
from typing import Any, Mapping, Optional, Sequence

from pydantic import BaseModel, Field

log = logging.getLogger(__name__)

WILDCARD = "*"


# ---------------------------------------------------------------------------
# Public records — MUST match the shapes in
# api/server/mcp_tools/delegated_authority.py so the in-process kernel and
# the HTTP fallback are interchangeable. Field names are Foundry-IQ
# contract surface; do not rename without the engagement-POC swap-in
# being aware (REQ-002).
# ---------------------------------------------------------------------------


class ApproverResolution(BaseModel):
    """Result of a resolve_approver call. Mirrors
    ``api.server.mcp_tools.delegated_authority.ApproverResolution``."""

    matched: bool
    approver_role: Optional[str] = None
    threshold_gbp: Optional[float] = None
    escalation_chain: list[str] = Field(default_factory=list)
    rule_id: Optional[str] = None
    basis: Optional[str] = None
    reason: Optional[str] = None  # populated when matched=False


class AuthorityCheck(BaseModel):
    """Result of a check_authority call. Mirrors
    ``api.server.mcp_tools.delegated_authority.AuthorityCheck``."""

    allowed: bool
    reason: str
    governing_rule_id: Optional[str] = None


# ---------------------------------------------------------------------------
# Resolver primitives — direct line-by-line port from
# mocks/authority-mcp/resolver.ts
# ---------------------------------------------------------------------------


def _field_matches(rule_value: Any, request_value: Any) -> bool:
    """Wildcard semantics on a scope field.

    A rule value of ``"*"`` matches any request value (including
    ``None``/empty). A non-wildcard rule value matches only when the
    request value is non-empty AND equal.
    """
    if rule_value == WILDCARD:
        return True
    if request_value is None or request_value == "":
        return False
    return rule_value == request_value


def _value_in_band(band: Mapping[str, Any] | None, value: float | None) -> bool:
    """Inclusive band check.

    - Both bounds ``None`` → non-monetary band; matches regardless of value.
    - Otherwise the caller MUST supply a numeric value, and that value
      must satisfy ``band.min <= value <= band.max`` (each bound
      respected only if non-null).
    """
    if not band or (band.get("min") is None and band.get("max") is None):
        return True
    if value is None:
        return False
    try:
        v = float(value)
    except (TypeError, ValueError):
        return False
    bmin = band.get("min")
    bmax = band.get("max")
    if bmin is not None and v < bmin:
        return False
    if bmax is not None and v > bmax:
        return False
    return True


def _is_malformed(rule: Mapping[str, Any], idx: int) -> str | None:
    """Return a description of why ``rule`` is malformed, or ``None``."""
    if not rule.get("rule_id"):
        return f"rule[{idx}] missing rule_id"
    if not rule.get("action"):
        return f"rule[{rule.get('rule_id')}] missing action"
    if not rule.get("approver_role"):
        return f"rule[{rule.get('rule_id')}] missing approver_role"
    band = rule.get("value_band_gbp")
    if band is None:
        return f"rule[{rule.get('rule_id')}] missing value_band_gbp"
    bmin, bmax = band.get("min"), band.get("max")
    if bmin is not None and bmax is not None and bmin > bmax:
        return f"rule[{rule.get('rule_id')}] has min > max"
    return None


def resolve(
    matrix: Sequence[Mapping[str, Any]],
    *,
    action: str,
    value: float | None = None,
    category: str | None = None,
    requester_role: str | None = None,
    business_unit: str | None = None,
    geography: str | None = None,
) -> ApproverResolution:
    """Walk ``matrix`` and return the first matching rule as an
    :class:`ApproverResolution`. No match returns ``matched=False``
    with a human-readable ``reason``.
    """
    for idx, rule in enumerate(matrix):
        malformed = _is_malformed(rule, idx)
        if malformed:
            log.warning("authority-resolver: skipping malformed rule: %s", malformed)
            continue
        if rule.get("action") != action:
            continue
        if not _field_matches(rule.get("category"), category):
            continue
        if not _field_matches(rule.get("business_unit"), business_unit):
            continue
        if not _field_matches(rule.get("geography"), geography):
            continue
        if not _field_matches(rule.get("requester_role"), requester_role):
            continue
        if not _value_in_band(rule.get("value_band_gbp"), value):
            continue
        band = rule.get("value_band_gbp") or {}
        return ApproverResolution(
            matched=True,
            approver_role=rule.get("approver_role"),
            threshold_gbp=band.get("max"),
            escalation_chain=list(rule.get("escalation_chain") or []),
            rule_id=rule.get("rule_id"),
            basis=rule.get("basis", "") or "",
        )
    return ApproverResolution(
        matched=False,
        reason=(
            f"no rule matched action={action} category={category or '*'} "
            f"value={value if value is not None else 'n/a'} "
            f"bu={business_unit or '*'} geo={geography or '*'}"
        ),
    )


def check(
    matrix: Sequence[Mapping[str, Any]],
    *,
    role: str,
    action: str,
    value: float | None = None,
    category: str | None = None,
    requester_role: str | None = None,
    business_unit: str | None = None,
    geography: str | None = None,
) -> AuthorityCheck:
    """Does ``role`` have authority for the request? Walks via
    :func:`resolve` and inspects ``approver_role`` + ``escalation_chain``."""
    resolution = resolve(
        matrix,
        action=action,
        value=value,
        category=category,
        requester_role=requester_role,
        business_unit=business_unit,
        geography=geography,
    )
    if not resolution.matched:
        return AuthorityCheck(
            allowed=False,
            reason=resolution.reason or "no rule matched",
            governing_rule_id=None,
        )
    if resolution.approver_role == role:
        return AuthorityCheck(
            allowed=True,
            reason=(
                f"role '{role}' is the matched approver per rule "
                f"{resolution.rule_id}"
            ),
            governing_rule_id=resolution.rule_id,
        )
    if role in resolution.escalation_chain:
        return AuthorityCheck(
            allowed=True,
            reason=(
                f"role '{role}' is in the escalation chain for rule "
                f"{resolution.rule_id}"
            ),
            governing_rule_id=resolution.rule_id,
        )
    chain = ", ".join(resolution.escalation_chain) or "none"
    return AuthorityCheck(
        allowed=False,
        reason=(
            f"role '{role}' is not authorised; matched rule "
            f"{resolution.rule_id} requires '{resolution.approver_role}' "
            f"(escalation: {chain})"
        ),
        governing_rule_id=resolution.rule_id,
    )

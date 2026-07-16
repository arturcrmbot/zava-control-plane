"""api/shared/persona_contracts.py — persona structural contract types.

Extracted so :mod:`api.shared.vertical_pack` (and the vertical pack
manifests that build ``personas: Mapping[str, Persona]``) can depend on
these types without importing the (business-owning) pack persona modules,
mirroring :mod:`api.shared.domain_contracts` / :mod:`api.shared.agent_contracts`.

Canonical persona declarations live in ``verticals/agency/personas.py`` and
``verticals/telco/personas.py``. This module declares no personae.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Literal


Archetype = Literal["approver", "subject", "reviewer", "delegate", "notifier"]
ScopeFunction = Literal[
    "finance",
    "hr",
    "it",
    "procurement",
    "legal",
    "legal_privacy",
    "commercial",
    "candidate",
]


@dataclass(frozen=True)
class Persona:
    """A persona structural record. Behaviour lives in SKILL.md decision_policy.

    `archetype` groups personae for UI rendering and FM skill text:
      - approver: signs off the gate (most common).
      - subject:  the person the workflow is *about* (claimant, candidate).
      - reviewer: examines and may flag without final sign-off.
      - delegate: stands in for an absent approver.
      - notifier: receives information, no decision authority.

    `scope_function` is the corporate function the persona belongs to.
    `scope_business_unit` and `scope_geography` default to "*" (all).

    `default_authority_band` is a free-text label of the value band the
    persona typically signs off (e.g. "<=£500", "£10k-£50k", "any"). It
    is documentation only; the binding authority resolution comes from
    the delegated_authority MCP at runtime.

    `uses_authority_mcp = True` declares that the persona's
    decision_policy consults `context.authority` (or calls
    `authority_check` from the sandbox) to resolve thresholds, instead
    of inlining numeric values. The persona responder uses this flag to
    surface migration status in tests and on the microsite.
    """

    role: str
    archetype: Archetype
    scope_function: ScopeFunction
    workflow_label: str
    external_event_default: str | None = None
    scope_business_unit: str = "*"
    scope_geography: str = "*"
    default_authority_band: str | None = None
    uses_authority_mcp: bool = False
    description: str = ""
    # autonomous-domain-insights v1.1 (F1): per-persona display hue used by
    # the cosmic-lens HUD (DecisionTicker, workflow gate flashes). None
    # means the UI falls back to a neutral grey.
    display_color: str | None = None

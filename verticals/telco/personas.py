"""verticals/telco/personas.py — Telco vertical persona metadata registry.

Canonical Telco ``Persona`` declarations. This module owns Telco's
Customer Success persona metadata exclusively — Agency's ~74 remaining
personae live in ``verticals/agency/personas.py`` and are never imported
here.

``delivery_lead`` is a legitimately shared role used by both packs (same
metadata/behaviour in each pack today); it is declared verbatim here AND in
``verticals/agency/personas.py`` rather than imported cross-pack.

Consumers (via the ``api.shared.personas`` compatibility adapter):
- api.server.services.persona_responder       — validates against registry at attach()
- api.server.services.blueprint_inventory     — renders persona library on the microsite
- api.server.services.fleet_manager_service   — composes "personae under supervision" text
"""
from __future__ import annotations

import dataclasses as _dataclasses

from api.shared.persona_contracts import Archetype, Persona, ScopeFunction


__all__ = ["Archetype", "ScopeFunction", "Persona", "TELCO_PERSONAS"]


_TELCO_PERSONAS: dict[str, Persona] = {
    # Customer Success tier
    "cs_director": Persona(
        role="cs_director", archetype="approver", scope_function="commercial",
        workflow_label="Customer Success — director", external_event_default="cs_director_decision",
        description="Customer Success Director; sign-off on strategic CS initiatives; escalates to the COO.",
    ),
    "cs_account_director": Persona(
        role="cs_account_director", archetype="approver", scope_function="commercial",
        workflow_label="Customer Success — account", external_event_default="cs_account_director_decision",
        description="CS Account Director; owns the CS P&L for a portfolio; escalates to CS Director.",
    ),
    "cs_manager": Persona(
        role="cs_manager", archetype="approver", scope_function="commercial",
        workflow_label="Customer Success — manager", external_event_default="cs_manager_decision",
        description="CS Manager; runs a CS pod for a set of accounts; escalates to CS Account Director.",
    ),
    "cs_specialist": Persona(
        role="cs_specialist", archetype="subject", scope_function="commercial",
        workflow_label="Customer Success — specialist", external_event_default="cs_specialist_decision",
        description="CS Specialist; day-to-day customer support and engagement; escalates to CS Manager.",
    ),

    # Network Operations
    "network_ops_director": Persona(
        role="network_ops_director", archetype="approver", scope_function="commercial",
        workflow_label="Network Operations — director",
        external_event_default="network_ops_director_decision",
        description="Network Operations Director; approves exceptional operational and capital actions.",
    ),
    "delivery_lead": Persona(
        role="delivery_lead", archetype="approver", scope_function="commercial",
        workflow_label="Operations — delivery", external_event_default="delivery_lead_decision",
        description="Delivery Lead; owns delivery within a single project workstream; first-line approver under the project manager.",
    ),
}

TELCO_DISPLAY_COLORS: dict[str, str] = {
    # Account / CS — sky blue (same hue as Agency's account_director /
    # account_manager — Customer Success is Telco's analogue of Agency's
    # account-services tree).
    "cs_director": "#7fc4ff",
    "cs_manager": "#7fc4ff",
    "network_ops_director": "#8b5cf6",
}

TELCO_PERSONAS: dict[str, Persona] = {
    role: (
        _dataclasses.replace(p, display_color=TELCO_DISPLAY_COLORS[role])
        if role in TELCO_DISPLAY_COLORS
        else p
    )
    for role, p in _TELCO_PERSONAS.items()
}

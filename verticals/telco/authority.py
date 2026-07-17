"""verticals/telco/authority.py — Telco vertical delegated-authority matrix.

Canonical Telco ``AuthorityRow`` declarations. This module owns Telco's
Customer Success authority rows exclusively — Agency's ~73 rows live in
``verticals/agency/authority.py`` and are never imported here.

``delivery_lead`` is a legitimately shared role used by both packs (same
row/behaviour in each pack today); it is declared verbatim here AND in
``verticals/agency/authority.py`` rather than imported cross-pack.

Consumers (via the ``api.shared.authority`` compatibility adapter):
- api.server.services.persona_responder — sandbox authority_check() calls
- decision_policy blocks in verticals/telco/personae/*/SKILL.md
"""
from __future__ import annotations

from api.shared.authority_contracts import AuthorityRow


TELCO_AUTHORITY: dict[str, AuthorityRow] = {
    # ----- Customer Success --------------------------------------------
    "cs_specialist": AuthorityRow(
        role="cs_specialist", spend_limit_gbp=0.0,
        approval_actions=(), delegate_to="cs_manager",
    ),
    "cs_manager": AuthorityRow(
        role="cs_manager", spend_limit_gbp=10_000.0,
        approval_actions=("cs_manager_decision",),
        delegate_to="cs_account_director",
    ),
    "cs_account_director": AuthorityRow(
        role="cs_account_director", spend_limit_gbp=100_000.0,
        approval_actions=("cs_account_director_decision",),
        delegate_to="cs_director",
    ),
    "cs_director": AuthorityRow(
        role="cs_director", spend_limit_gbp=500_000.0,
        approval_actions=("cs_director_decision",),
        delegate_to=None,
    ),

    # ----- Network Operations ------------------------------------------
    "delivery_lead": AuthorityRow(
        role="delivery_lead", spend_limit_gbp=10_000.0,
        approval_actions=("delivery_lead_decision",),
        delegate_to="network_ops_director",
    ),
    "network_ops_director": AuthorityRow(
        role="network_ops_director", spend_limit_gbp=100_000.0,
        approval_actions=("network_ops_director_decision",),
        delegate_to=None,
    ),
}

"""verticals/agency/agents.py — Agency vertical machine-agent registry.

Canonical Agency ``AgentRegistryEntry`` declarations. Every machine agent
that the Agency substrate executes (and that may end up writing to the
audit ledger or calling MCP tools) has a structural record in
``AGENCY_AGENTS``, keyed by ``agent_id``.

This module owns Agency's agent identities exclusively — the two Telco
customer-care agent ids live in ``verticals/telco/agents.py`` and are never
imported here. The single kernel-identity actor (``reflector.entity_reflector``
— substrate machinery that dispatches EntityGraph projections regardless of
active vertical) is declared once in the ``api.shared.agents`` compatibility
adapter, not here, so it is never smuggled into (or missing from) either
pack's business-agent mapping.

Consumers (via the ``api.shared.agents`` compatibility adapter):
- api.server.services.governance.kernel — capability/value/reversibility gate
- api.server.services.dream_pass        — actor lookups for lesson writes
"""
from __future__ import annotations

from api.shared.agent_contracts import AgentRegistryEntry


# --------------------------------------------------------------------------
# The registry. Entries grouped by operating function for code review.
# --------------------------------------------------------------------------

AGENCY_AGENTS: dict[str, AgentRegistryEntry] = {
    # ---------------- Finance (POC1 expense-claim) ----------------
    "rag-classifier": AgentRegistryEntry(
        agent_id="rag-classifier",
        allowed_tools=(
            "policy.search",
            "policy.cite",
            "claim.getStructured",
            "claim.lookup",
        ),
        max_value_gbp=None,  # read-only verdict
        reversible_only=True,
        scope_function="finance",
        description=(
            "POC1 RAG-over-policy classifier. Reads the policy corpus and "
            "the structured claim, emits a (verdict, confidence) tuple."
        ),
    ),
    "arbitration": AgentRegistryEntry(
        agent_id="arbitration",
        allowed_tools=(
            "policy.search",
            "policy.cite",
            "claim.getStructured",
            "claim.summary",
            "precedents.search",
            "query.reviewer_decisions",
            "audit.query",
            "compose_exception",
            "authority.resolve_approver",
            "authority.check_authority",
        ),
        max_value_gbp=None,
        reversible_only=True,
        scope_function="finance",
        description=(
            "POC1 Red-tier arbitration recommender. Consults precedents + "
            "policy citations to recommend a HITL routing decision."
        ),
    ),
    "receipt_validator": AgentRegistryEntry(
        agent_id="receipt_validator",
        allowed_tools=(
            "claim.getStructured",
            "claim.getReceipt",
            "ocr.extract",
        ),
        max_value_gbp=None,
        reversible_only=True,
        scope_function="finance",
        description=(
            "Receipt OCR + line-item match validator. Pure read of the claim "
            "+ Document Intelligence."
        ),
    ),

    # ---------------- Hiring (POC2) ----------------
    "cv_crystalliser": AgentRegistryEntry(
        agent_id="cv_crystalliser",
        allowed_tools=(
            "ocr.extract",
            "recall.similar_hires",
            "propose_skill_amplification",
            "workday_hr.employee.get_employee",
        ),
        max_value_gbp=None,
        reversible_only=True,
        scope_function="hiring",
        description=(
            "POC2 candidate CV crystalliser. Ingests the uploaded PDF/CV, "
            "extracts structured candidate fields, recalls similar hires."
        ),
    ),

    # ---------------- Hiring skills (plan/refactor-substrate-agentic-segments-1) ----------------
    # Per-skill ACL rows for the 9 hiring SKILL.md skills. The dotted tool
    # IDs are the canonical names from data/policies/tools.yaml; SKILL.md
    # frontmatter uses underscore names (e.g. policy_search) which the
    # kernel does NOT understand — it composes "server.tool" from the SDK
    # PermissionRequest (see permission_handler._compose_tool_id). Tools
    # the SKILL.md declares but that don't exist in tools.yaml are dropped
    # here with a TODO; under AGT_ENFORCE the kernel allow-throughs any
    # call to an unknown tool (kernel.py:493-497 — "we don't know enough
    # to gate"), so no behaviour regression results from the omission.
    "jd-drafter": AgentRegistryEntry(
        agent_id="jd-drafter",
        allowed_tools=(
            "policy.search",
            # TODO(agt): jd_library_search — not in tools.yaml manifest
        ),
        max_value_gbp=None,
        reversible_only=True,
        scope_function="hiring",
        description="JD drafter — produces a single JD draft from a requisition brief.",
    ),
    "sourcing-orchestrator": AgentRegistryEntry(
        agent_id="sourcing-orchestrator",
        allowed_tools=(
            # TODO(agt): greenhouse_post — not in tools.yaml manifest
            # TODO(agt): linkedin_search — not in tools.yaml manifest
        ),
        max_value_gbp=None,
        reversible_only=True,
        scope_function="hiring",
        description="Sourcing orchestrator — posts the JD and runs LinkedIn search.",
    ),
    "cv-crystalliser": AgentRegistryEntry(
        agent_id="cv-crystalliser",
        allowed_tools=(
            "ocr.extract",
            # TODO(agt): linkedin_profile_fetch — not in tools.yaml manifest
        ),
        max_value_gbp=None,
        reversible_only=True,
        scope_function="hiring",
        description=(
            "CV crystalliser (skill-flavour) — OCR + LinkedIn enrichment "
            "of a candidate's CV. Sister to the legacy cv_crystalliser "
            "agent entry; this one is keyed by the SKILL.md `name:` "
            "(hyphenated) so segment runs resolve cleanly."
        ),
    ),
    "auto-shortlister": AgentRegistryEntry(
        agent_id="auto-shortlister",
        allowed_tools=(
            # TODO(agt): scoring_rubric_load — not in tools.yaml manifest
        ),
        max_value_gbp=None,
        reversible_only=True,
        scope_function="hiring",
        description="Auto-shortlister — scores candidates against the rubric.",
    ),
    "interview-recommender": AgentRegistryEntry(
        agent_id="interview-recommender",
        allowed_tools=(),
        max_value_gbp=None,
        reversible_only=True,
        scope_function="hiring",
        description="Interview recommender — no tool calls; pure model judgement.",
    ),
    "jurisdiction-router": AgentRegistryEntry(
        agent_id="jurisdiction-router",
        allowed_tools=(
            "policy.search",
            # TODO(agt): betrvg_check — not in tools.yaml manifest
            # TODO(agt): eeo_check — not in tools.yaml manifest
        ),
        max_value_gbp=None,
        reversible_only=True,
        scope_function="hiring",
        description="Jurisdiction router — picks USA / DE compliance branch.",
    ),
    "betrvg-checker": AgentRegistryEntry(
        agent_id="betrvg-checker",
        allowed_tools=(
            "policy.search",
            # TODO(agt): graph_mail — not in tools.yaml manifest
        ),
        max_value_gbp=None,
        reversible_only=True,
        scope_function="hiring",
        description="BetrVG checker — DE works-council notification flow.",
    ),
    "offer-personaliser": AgentRegistryEntry(
        agent_id="offer-personaliser",
        allowed_tools=(
            # TODO(agt): offer_template_fetch — not in tools.yaml manifest
            # TODO(agt): comp_band_lookup — not in tools.yaml manifest
        ),
        max_value_gbp=None,
        reversible_only=True,
        scope_function="hiring",
        description="Offer personaliser — drafts the offer letter from the template.",
    ),
    "onboarding-buddy": AgentRegistryEntry(
        agent_id="onboarding-buddy",
        allowed_tools=(
            "avatar.render",
            # TODO(agt): servicenow_jml — not in tools.yaml manifest
            # TODO(agt): graph_invite — not in tools.yaml manifest
        ),
        max_value_gbp=None,
        # Onboarding fires irreversible side-effects (ServiceNow JML /
        # Graph invites / avatar render). reversible_only=False so the
        # kernel's reversibility gate doesn't block legitimate writes.
        reversible_only=False,
        scope_function="hiring",
        description="Onboarding buddy — kicks off ServiceNow JML, avatar, Graph invite.",
    ),

    # ---------------- Hiring segments (plan/refactor-substrate-agentic-segments-1) ----------------
    # Segment-level ACL rows. Each segment runs as one agent_session with
    # the segment label as actor; its allow-list is the deduped union of
    # the constituent skills' allow-lists above. Keeping per-skill rows
    # AND segment rows lets the kernel gate consistently whether the call
    # site is per-phase (legacy) or segment-flavour (new).
    "hiring-segment-b": AgentRegistryEntry(
        agent_id="hiring-segment-b",
        # Union of jd-drafter + sourcing-orchestrator + cv-crystalliser +
        # auto-shortlister.
        allowed_tools=(
            "policy.search",
            "ocr.extract",
        ),
        max_value_gbp=None,
        reversible_only=True,
        scope_function="hiring",
        description=(
            "Hiring Segment B (candidate discovery) — aggregates jd-drafter, "
            "sourcing-orchestrator, cv-crystalliser, auto-shortlister."
        ),
    ),
    "hiring-segment-d": AgentRegistryEntry(
        agent_id="hiring-segment-d",
        # interview-recommender has no tool calls — empty allow-list.
        allowed_tools=(),
        max_value_gbp=None,
        reversible_only=True,
        scope_function="hiring",
        description=(
            "Hiring Segment D (interview decisioning) — aggregates "
            "interview-recommender."
        ),
    ),
    "hiring-segment-e": AgentRegistryEntry(
        agent_id="hiring-segment-e",
        # Union of jurisdiction-router + betrvg-checker + offer-personaliser.
        allowed_tools=(
            "policy.search",
        ),
        max_value_gbp=None,
        reversible_only=True,
        scope_function="hiring",
        description=(
            "Hiring Segment E (compliance + offer) — aggregates "
            "jurisdiction-router, betrvg-checker, offer-personaliser."
        ),
    ),
    "hiring-segment-f": AgentRegistryEntry(
        agent_id="hiring-segment-f",
        # onboarding-buddy only.
        allowed_tools=(
            "avatar.render",
        ),
        max_value_gbp=None,
        # Mirrors onboarding-buddy — segment fires irreversible writes.
        reversible_only=False,
        scope_function="hiring",
        description=(
            "Hiring Segment F (onboarding) — aggregates onboarding-buddy."
        ),
    ),

    # ---------------- System actors (Agency) ----------------
    "dream-pass:hiring": AgentRegistryEntry(
        agent_id="dream-pass:hiring",
        allowed_tools=(
            "lesson.write",
            "lesson.prune",
        ),
        max_value_gbp=None,
        reversible_only=True,
        scope_function="hiring",
        description=(
            "Dream-pass hiring orchestrator — promotes and prunes governed lessons."
        ),
    ),
}

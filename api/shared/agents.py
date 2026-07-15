"""api/shared/agents.py — Machine agent registry: single source of truth.

Sister to :mod:`api.shared.personas` and :mod:`api.shared.domains`. Every
machine agent that the substrate executes (and that may end up writing to
the audit ledger or calling MCP tools) has a structural record in
:data:`AGENTS`, keyed by ``agent_id``.

Why this exists
---------------
Per plan/feature-agent-governance-toolkit-1.md TASK-035 (Phase 5). Before
this file, agent identities were implicit — a free-text ``agent_label``
on whatever event happened to flow through ``EvalRow`` /
``agent_reasoning``. With governance enforcement landing in Phase 6,
"which tools can finance-agent actually call?" becomes a one-line lookup
here, not a grep across SKILL.md frontmatter and hand-knit allowlists.

Each entry declares:

- ``agent_id``           — canonical id; matches the ``agent_label`` value
                           every event uses.
- ``allowed_tools``      — tuple of tool ids from ``data/policies/tools.yaml``.
                           Phase 6 capability gate (TASK-045) denies any tool
                           call from this agent that isn't in this tuple.
- ``max_value_gbp``      — optional ceiling (GBP). Phase 6 denies any call
                           whose extracted ``value`` exceeds this.
- ``reversible_only``    — when True, irreversible tools (per tools.yaml)
                           are denied even if listed in ``allowed_tools``.
- ``scope_function``     — operating function: finance / hiring / shared / creative.
- ``description``        — one-line human description; surfaces in evidence.

Audit (TASK-034)
----------------
The agent_label values that show up in tests + runtime (audit grep
2026-05-07):

- ``rag-classifier``       — POC1 RAG-over-policy classification (verdict)
- ``arbitration``          — POC1 Red-tier arbitration recommender
- ``cv_crystalliser``      — POC2 CV ingest + structured extract
- ``receipt_validator``    — POC1/2 receipt OCR + line-item match

Every skill under ``api/server/skills/`` is a candidate for this
registry; today only the labels above appear on real ledger entries
or test fixtures, and that is the list TASK-036's CI check enforces.
Adding a new agent_label to a fixture without registering it here
fails the CI check.

Provisional skill -> agent_id mapping for Phase 6 expansion: derive
``agent_id`` from the SKILL.md ``name:`` frontmatter (snake_case).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal


ScopeFunction = Literal["finance", "hiring", "shared", "creative", "hr", "it"]


@dataclass(frozen=True)
class AgentRegistryEntry:
    agent_id: str
    allowed_tools: tuple[str, ...] = field(default_factory=tuple)
    max_value_gbp: float | None = None
    reversible_only: bool = True
    scope_function: ScopeFunction = "shared"
    description: str = ""


# --------------------------------------------------------------------------
# The registry. Entries grouped by operating function for code review.
# --------------------------------------------------------------------------

AGENTS: dict[str, AgentRegistryEntry] = {
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
    # ---------------- Telco customer care ----------------
    "proactive-customer-care-entitlement": AgentRegistryEntry(
        agent_id="proactive-customer-care-entitlement",
        allowed_tools=("customer_care_policy_lookup",),
        max_value_gbp=None,
        reversible_only=True,
        scope_function="shared",
        description=(
            "Telco care entitlement agent — reads governed policy for each "
            "impacted commercial account."
        ),
    ),
    "proactive-customer-care-execution": AgentRegistryEntry(
        agent_id="proactive-customer-care-execution",
        allowed_tools=(
            "customer_care_prepare_notification",
            "customer_care_prepare_credit",
        ),
        max_value_gbp=None,
        reversible_only=True,
        scope_function="shared",
        description=(
            "Telco care execution agent — prepares notification and credit "
            "actions for authoritative world validation."
        ),
    ),
    # ---------------- System actors (Phase 1 entity-graph plane) ----------------
    # The entity-graph reflector dispatches projection ops (Person /
    # Organisation upserts + Decision writes) under a fixed actor id so
    # the governance gate can audit + kill-switch it. Listed as a system
    # actor so AppState's `governance=self.governance` wiring doesn't
    # auto-deny under the unknown-agent rule in
    # api/server/services/governance/kernel.py:_registry_gate.
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
    "reflector.entity_reflector": AgentRegistryEntry(
        agent_id="reflector.entity_reflector",
        allowed_tools=("entity.write",),
        max_value_gbp=None,
        reversible_only=False,
        scope_function="shared",
        description=(
            "System actor for EntityReflector — turns FleetEvents into "
            "EntityGraph upserts via the per-domain projection registry."
        ),
    ),
}


# --------------------------------------------------------------------------
# Helpers
# --------------------------------------------------------------------------


def get(agent_id: str) -> AgentRegistryEntry | None:
    """Return the registry entry for ``agent_id``, or ``None``."""
    return AGENTS.get(agent_id)


def by_function(scope: ScopeFunction) -> list[AgentRegistryEntry]:
    """All registered agents scoped to ``scope``."""
    return [a for a in AGENTS.values() if a.scope_function == scope]


def all_agent_ids() -> tuple[str, ...]:
    """Sorted tuple of every registered agent_id."""
    return tuple(sorted(AGENTS.keys()))

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
    # ---------------- System actors (Phase 1 entity-graph plane) ----------------
    # The entity-graph reflector dispatches projection ops (Person /
    # Organisation upserts + Decision writes) under a fixed actor id so
    # the governance gate can audit + kill-switch it. Listed as a system
    # actor so AppState's `governance=self.governance` wiring doesn't
    # auto-deny under the unknown-agent rule in
    # api/server/services/governance/kernel.py:_registry_gate.
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

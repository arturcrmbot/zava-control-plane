"""api/shared/functions.py — FUNCTIONS registry: single source of truth for departments.

Mirrors the dataclass + module-level dict shape of
``api/shared/domains.py``. Each ``Function`` carries the per-department
identity block the FunctionFleetManager templates against (KPIs, owned
domains, persona hierarchy, ambient watchers).

Boot-time side effects (bottom of module):

1. ``_wire_function_back_refs()`` — walks ``FUNCTIONS`` and stamps
   ``Domain.function = <function-name>`` on every domain claimed via
   ``Function.owns_domains``. Raises on unknown domain references and on
   any orphan domain (a domain no function owns).
2. ``_validate_persona_hierarchy()`` — walks every
   ``Function.persona_hierarchy`` recursively and asserts every role
   resolves to a SKILL.md under ``api/server/personae/<role>/``. The
   ``legacy`` function carries the sentinel ``__legacy__`` role and is
   skipped.

Drift between this file's ``owns_domains`` enumeration and
``api/shared/domains.py`` will trip the orphan validator at import.

Plan: plan/feature-agentic-org-phase-3-function-fms.md (TASK-001..-007).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path


@dataclass(frozen=True)
class PersonaTree:
    """Hierarchical role tree under a function. Each node names a persona
    role that must resolve to ``api/server/personae/<role>/SKILL.md``.

    The ``__legacy__`` sentinel role is reserved for the ``legacy``
    function and is skipped by ``_validate_persona_hierarchy``.
    """
    role: str
    manages: tuple["PersonaTree", ...] = ()


@dataclass(frozen=True)
class Function:
    name: str
    display: str
    operator_surface: str
    owns_domains: tuple[str, ...]
    ambient_agents: tuple[str, ...]
    kpis: tuple[str, ...]
    persona_hierarchy: PersonaTree


# --------------------------------------------------------------------------
# The registry. Ten entries — nine business functions + ``legacy`` for
# POC1/POC2 carry-over domains. Drift vs Phase 2's compose-domain v4
# backfill (plan/feature-agentic-org-phase-2-compose-v4.md TASK-026..037)
# will trip the orphan validator below.
# --------------------------------------------------------------------------

FUNCTIONS: dict[str, Function] = {
    "finance": Function(
        name="finance",
        display="Finance",
        operator_surface="finance-controller",
        owns_domains=("ap-invoice", "contract-renewal", "purchase-order",
                      "treasury-fx", "vendor-kyc"),
        # Phase 6 (TASK-035 / TASK-036) plants these instances; the names
        # are listed here so the discovery cross-validation has a target.
        ambient_agents=("budget-variance-watcher", "vendor-risk-watcher"),
        kpis=("dso", "dpo", "budget-variance-pct", "fraud-rate"),
        persona_hierarchy=PersonaTree(
            role="cfo",
            manages=(
                PersonaTree(role="controller", manages=(
                    PersonaTree(role="finance_bp"),
                    PersonaTree(role="ap_clerk"),
                )),
                PersonaTree(role="fpa_analyst"),
                PersonaTree(role="treasurer"),
            ),
        ),
    ),
    "hr": Function(
        name="hr",
        display="People & HR",
        operator_surface="hr-bp",
        owns_domains=("employee-onboarding", "perf-review", "travel-preapproval"),
        ambient_agents=(),
        kpis=("time-to-hire", "regrettable-attrition-pct",
              "engagement-score", "comp-ratio"),
        persona_hierarchy=PersonaTree(
            role="cpo",
            manages=(
                PersonaTree(role="hr_bp", manages=(
                    PersonaTree(role="recruiter"),
                    PersonaTree(role="comp_ben_analyst"),
                )),
                PersonaTree(role="perf_review_hr_bp"),
            ),
        ),
    ),
    "revenue": Function(
        name="revenue",
        display="Revenue",
        operator_surface="account-director",
        # Phase 4 graduates the synthetic ``lead-to-cash`` meta-workflow;
        # for now no domains are owned.
        owns_domains=(),
        ambient_agents=(),
        kpis=("pipeline-coverage", "win-rate", "arr-growth-pct", "nrr"),
        persona_hierarchy=PersonaTree(
            role="account_director",
            manages=(
                PersonaTree(role="sourcing_lead"),
            ),
        ),
    ),
    "ops": Function(
        name="ops",
        display="Operations",
        operator_surface="change-manager",
        owns_domains=(),
        ambient_agents=(),
        kpis=("on-time-delivery-pct", "cycle-time", "incident-rate", "cost-per-unit"),
        persona_hierarchy=PersonaTree(
            role="change_manager",
            manages=(
                PersonaTree(role="project_manager"),
            ),
        ),
    ),
    "legal": Function(
        name="legal",
        display="Legal",
        operator_surface="general-counsel",
        owns_domains=("contract-review", "privacy-dpia"),
        ambient_agents=(),
        kpis=("contract-cycle-time", "litigation-exposure",
              "policy-coverage-pct", "dpia-on-time-pct"),
        persona_hierarchy=PersonaTree(
            role="gc",
            manages=(
                PersonaTree(role="contracts_counsel"),
                PersonaTree(role="dpo"),
            ),
        ),
    ),
    "marketing": Function(
        name="marketing",
        display="Marketing",
        operator_surface="creative-director",
        owns_domains=("creative-campaign",),
        ambient_agents=(),
        kpis=("campaign-roi", "brand-lift", "mql-volume", "creative-cycle-time"),
        # Marketing has only one persona under api/server/personae/ today
        # (creative_director). Hierarchy is a single node until more
        # marketing personae graduate.
        persona_hierarchy=PersonaTree(role="creative_director"),
    ),
    "tech": Function(
        name="tech",
        display="Technology",
        operator_surface="it-admin",
        owns_domains=("it-access-request",),
        # Phase 6 (TASK-037) plants the AccessAnomalyWatcher instance.
        ambient_agents=("access-anomaly-watcher",),
        kpis=("change-failure-rate", "mttr", "access-review-coverage-pct",
              "deploy-frequency"),
        persona_hierarchy=PersonaTree(
            role="it_access_it_admin",
            manages=(
                PersonaTree(role="onboarding_it_admin"),
                PersonaTree(role="it_access_line_manager"),
            ),
        ),
    ),
    "data": Function(
        name="data",
        display="Data",
        operator_surface="data-bp",
        owns_domains=(),
        ambient_agents=(),
        kpis=("data-quality-score", "model-drift-rate",
              "platform-uptime-pct", "data-incident-rate"),
        # No data-specific personae graduated yet; reuse change-management
        # personae as the placeholder hierarchy until data personae land.
        persona_hierarchy=PersonaTree(
            role="project_manager",
            manages=(
                PersonaTree(role="category_manager"),
            ),
        ),
    ),
    "customer-success": Function(
        name="customer-success",
        display="Customer Success",
        operator_surface="account-director",
        owns_domains=(),
        ambient_agents=(),
        kpis=("nps", "gross-retention-pct", "expansion-arr-pct", "csat"),
        persona_hierarchy=PersonaTree(
            role="account_director",
            manages=(
                PersonaTree(role="recruiter"),  # placeholder until CS personae land
            ),
        ),
    ),
    "legacy": Function(
        name="legacy",
        display="Legacy (POC1/POC2 carry-over)",
        operator_surface="ssc-reviewer",
        owns_domains=("expense-claim", "hiring"),
        ambient_agents=(),
        kpis=(),  # legacy carries no KPIs
        # Sentinel — _validate_persona_hierarchy skips this role.
        persona_hierarchy=PersonaTree(role="__legacy__"),
    ),
}


# --------------------------------------------------------------------------
# Boot-time validators
# --------------------------------------------------------------------------

_LEGACY_SENTINEL = "__legacy__"


def _wire_function_back_refs() -> None:
    """Stamp ``Domain.function`` for every domain a function claims.

    Lazy-imports ``DOMAINS`` to avoid a circular import (domains.py is
    consumed by many services; functions.py is consumed by fewer; the
    arrow points functions → domains).

    Raises ``ValueError`` if a function claims an unknown domain or if
    any domain remains unclaimed after the wire pass (orphan).
    """
    from api.shared.domains import DOMAINS  # local import — see docstring

    for fn_name, fn in FUNCTIONS.items():
        for d in fn.owns_domains:
            if d not in DOMAINS:
                raise ValueError(
                    f"FUNCTIONS['{fn_name}'] claims unknown domain '{d}'"
                )
            DOMAINS[d].function = fn_name

    orphans = [k for k, dom in DOMAINS.items() if dom.function is None]
    if orphans:
        raise ValueError(
            f"unclaimed domains (no function owns these): {orphans}"
        )


def _persona_root() -> Path:
    """Return the personae directory root."""
    return Path(__file__).resolve().parents[1] / "server" / "personae"


def _walk_persona_tree(node: PersonaTree, fn_name: str, root: Path) -> None:
    if node.role == _LEGACY_SENTINEL:
        return
    skill = root / node.role / "SKILL.md"
    if not skill.is_file():
        raise ValueError(
            f"FUNCTIONS['{fn_name}'].persona_hierarchy references unknown persona '{node.role}'"
        )
    for child in node.manages:
        _walk_persona_tree(child, fn_name, root)


def _validate_persona_hierarchy() -> None:
    """Assert every PersonaTree role resolves to a real SKILL.md.

    The ``legacy`` function carries the ``__legacy__`` sentinel and is
    skipped (special-cased).
    """
    root = _persona_root()
    for fn_name, fn in FUNCTIONS.items():
        _walk_persona_tree(fn.persona_hierarchy, fn_name, root)


# --------------------------------------------------------------------------
# Import-time side effects — mirrors how DOMAINS is built today.
# --------------------------------------------------------------------------

_wire_function_back_refs()
_validate_persona_hierarchy()

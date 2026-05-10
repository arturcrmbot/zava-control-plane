"""Cities roster + affinity for the Cosmic Lens v2 visualisation.

A "city" is a single dockable resource on the central Hub. Five categories:
- mcp tools         (api/server/mcp_tools/*.py)
- skills            (api/server/skills/*/SKILL.md)
- python tools      (subset of skills classified as native compute)
- validators        (skills/tools whose name implies a gate)
- HITL personas     (PERSONAS registry)

Affinity (Phase C consumer) returns pairwise co-occurrence weights from
recent observatory events.

Note: Phase A frontend doesn't yet need affinity — only the roster.
"""

from __future__ import annotations

from collections import Counter, defaultdict
from pathlib import Path
import re
import time
from typing import Any

from fastapi import APIRouter, Query

REPO_ROOT = Path(__file__).resolve().parents[3]
SKILLS_DIR = REPO_ROOT / "api" / "server" / "skills"
MCP_TOOLS_DIR = REPO_ROOT / "api" / "server" / "mcp_tools"


router = APIRouter(prefix="/api/cities", tags=["cities"])


# ---- Capabilities mode -------------------------------------------------------


def _read_skill_name(skill_md: Path) -> str | None:
    """Extract the `name:` from a SKILL.md frontmatter."""
    try:
        text = skill_md.read_text()
    except OSError:
        return None
    m = re.search(r"^name:\s*(.+)$", text, re.MULTILINE)
    if m:
        return m.group(1).strip()
    return None


def _classify_skill(name: str) -> str:
    """Heuristic: validators / checkers / classifiers → validator. Otherwise skill."""
    n = name.lower()
    if any(s in n for s in ("validator", "checker", "guardian", "screen")):
        return "validator"
    return "skill"


def _gather_skills() -> list[dict[str, str]]:
    out: list[dict[str, str]] = []
    if not SKILLS_DIR.exists():
        return out
    for child in sorted(SKILLS_DIR.iterdir()):
        if not child.is_dir():
            continue
        skill_md = child / "SKILL.md"
        if not skill_md.exists():
            continue
        name = _read_skill_name(skill_md) or child.name
        kind = _classify_skill(name)
        out.append({
            "id": name,
            "kind": kind,
            "label": name,
            "category": "skill" if kind == "skill" else "validator",
        })
    return out


def _gather_mcp_tools() -> list[dict[str, str]]:
    out: list[dict[str, str]] = []
    if not MCP_TOOLS_DIR.exists():
        return out
    for child in sorted(MCP_TOOLS_DIR.iterdir()):
        if not child.is_file() or child.suffix != ".py":
            continue
        if child.name.startswith("_") or child.name == "__init__.py":
            continue
        name = child.stem
        out.append({
            "id": name,
            "kind": "mcp",
            "label": name,
            "category": "mcp",
        })
    return out


def _gather_personas() -> list[dict[str, str]]:
    """Pull persona roster from the same source as /api/personas/index/state.
    Falls back to a hardcoded canonical list if PERSONAS module isn't available.
    """
    canonical = [
        "ap_clerk", "controller", "cfo", "treasurer", "fpa_analyst", "finance_bp",
        "category_manager", "vendor_owner",
        "recruiter", "hiring_manager", "interviewer", "candidate", "people_partner",
        "line_manager", "talent_lead",
        "legal_counsel", "compliance_officer",
        "ceo", "coo", "cmo", "cto", "cdo", "chro", "general_counsel",
        "creative_director", "brand_steward", "campaign_manager", "account_director",
        "policy_owner", "support_lead",
    ]
    try:
        from api.server.routes.personas import _build_persona_state  # type: ignore
        # Try to read the live state
        states = _build_persona_state()
        roles = sorted({s.get("role") for s in states if s.get("role")})
        if roles:
            return [
                {"id": role, "kind": "persona", "label": role, "category": "persona"}
                for role in roles
            ]
    except Exception:
        pass
    return [
        {"id": role, "kind": "persona", "label": role, "category": "persona"}
        for role in canonical
    ]


# ---- Entities mode -----------------------------------------------------------


def _gather_entity_types() -> list[dict[str, str]]:
    """Pull entity-type roster from the entity graph schema (Kuzu).

    Phase A canonical fallback list. Phase D wires actual schema lookup.
    """
    canonical_kinds = [
        "Vendor", "Invoice", "Payment", "Account",
        "Candidate", "Job", "Offer",
        "Contract", "Document",
        "Decision", "Person", "Money", "Period",
        "PerformanceReview", "Campaign",
    ]
    return [
        {"id": k, "kind": "entity_type", "label": k, "category": "entity"}
        for k in canonical_kinds
    ]


# ---- Routes ------------------------------------------------------------------


@router.get("")
def list_cities(mode: str = Query("capabilities")) -> dict[str, Any]:
    """Return the city roster for the requested mode.

    `mode=capabilities` (default) → tools/skills/validators/personas
    `mode=entities` → entity types (with optional graph edges via /api/cities/edges)
    """
    if mode == "entities":
        cities = _gather_entity_types()
    else:
        cities = (
            _gather_mcp_tools()
            + _gather_skills()
            + _gather_personas()
        )
    return {"cities": cities, "mode": mode, "count": len(cities)}


# ---- Affinity (Phase C) ------------------------------------------------------

_AFFINITY_CACHE: dict[str, Any] = {"ts": 0.0, "data": None}
_AFFINITY_TTL_S = 60.0


def _compute_affinity() -> dict[str, Any]:
    """Compute pairwise city co-occurrence weights from recent events.

    Group events by workflow_id over the last N events; emit edges between
    every pair of cities that fired in the same workflow.
    """
    try:
        from api.server.services.blueprint_recorder import recent_events  # type: ignore
    except Exception:
        recent_events = lambda limit: []  # noqa: E731

    by_wf: dict[str, set[str]] = defaultdict(set)
    try:
        for ev in recent_events(2000):
            wid = (
                ev.get("workflow_id")
                or ev.get("caller_workflow_id")
                or ev.get("data", {}).get("workflow_id")
            )
            if not wid:
                continue
            data = ev.get("data") if isinstance(ev.get("data"), dict) else ev
            tn = data.get("tool_name") or ev.get("tool_name")
            persona = data.get("persona") or ev.get("persona")
            agent = data.get("agent_name") or ev.get("agent_name")
            for c in (tn, persona, agent):
                if c:
                    by_wf[wid].add(c)
    except Exception:
        pass

    pair_counts: Counter = Counter()
    for cities in by_wf.values():
        if len(cities) < 2:
            continue
        sorted_cities = sorted(cities)
        for i in range(len(sorted_cities)):
            for j in range(i + 1, len(sorted_cities)):
                pair_counts[(sorted_cities[i], sorted_cities[j])] += 1

    pairs = [
        {"a": a, "b": b, "weight": w}
        for (a, b), w in pair_counts.most_common(500)
    ]
    return {"pairs": pairs, "count": len(pairs)}


@router.get("/affinity")
def cities_affinity() -> dict[str, Any]:
    """Pairwise city co-occurrence weights, cached for 60s."""
    now = time.time()
    if _AFFINITY_CACHE["data"] is None or now - _AFFINITY_CACHE["ts"] > _AFFINITY_TTL_S:
        _AFFINITY_CACHE["data"] = _compute_affinity()
        _AFFINITY_CACHE["ts"] = now
    return _AFFINITY_CACHE["data"]


# ---- Entity edges (Phase D) --------------------------------------------------


@router.get("/edges")
def entity_edges() -> dict[str, Any]:
    """Persistent Kuzu graph relationships between entity types.

    Phase D consumer; Phase A returns canonical hardcoded edges so the
    Entities-mode persistent web has something to render.
    """
    canonical = [
        {"from_kind": "Vendor", "to_kind": "Invoice", "label": "supplies"},
        {"from_kind": "Invoice", "to_kind": "Payment", "label": "settled_by"},
        {"from_kind": "Payment", "to_kind": "Account", "label": "drawn_from"},
        {"from_kind": "Vendor", "to_kind": "Contract", "label": "party_to"},
        {"from_kind": "Candidate", "to_kind": "Job", "label": "applies_to"},
        {"from_kind": "Job", "to_kind": "Offer", "label": "results_in"},
        {"from_kind": "Candidate", "to_kind": "Offer", "label": "receives"},
        {"from_kind": "Offer", "to_kind": "Person", "label": "becomes"},
        {"from_kind": "Person", "to_kind": "PerformanceReview", "label": "subject_of"},
        {"from_kind": "Decision", "to_kind": "Document", "label": "references"},
        {"from_kind": "Money", "to_kind": "Period", "label": "in"},
        {"from_kind": "Campaign", "to_kind": "Document", "label": "asset"},
    ]
    return {"edges": canonical, "count": len(canonical)}

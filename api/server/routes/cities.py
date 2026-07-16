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

from fastapi import APIRouter, Depends, Query

from api.server.services.read_route_auth import Actor, require_actor
from api.shared.personas import PERSONAS
from api.shared.vertical_loader import active_runtime

REPO_ROOT = Path(__file__).resolve().parents[3]
_RUNTIME = active_runtime()
SKILLS_DIR = _RUNTIME.pack.skill_roots[0]
MCP_TOOL_PATHS = {
    module_name.rsplit(".", 1)[-1]: REPO_ROOT.joinpath(
        *module_name.split(".")
    ).with_suffix(".py")
    for module_name in _RUNTIME.pack.mcp_modules
}
PERSONAE_ROOTS = _RUNTIME.pack.personae_roots


# Real entity-graph kinds enumerated when listing cities in entity-mode.
# Kept in lock-step with `_NODE_TABLES` in
# `api/server/services/entity_graph.py`. `Workflow` is included so that
# `SUB_WORKFLOW_OF` parent-child chains surface as a first-class city in
# the cosmic lens.
ENTITY_KINDS: list[str] = [
    "Person", "Organisation", "Asset", "Money",
    "Decision", "Place", "Period", "Workflow",
    # pitch-e1: agency-domain kinds
    "Brand", "Campaign", "Pitch", "MediaPlan", "Subsidiary",
]


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
    for name in sorted(MCP_TOOL_PATHS):
        out.append({
            "id": name,
            "kind": "mcp",
            "label": name,
            "category": "mcp",
        })
    return out


def _gather_personas() -> list[dict[str, str]]:
    return [
        {"id": role, "kind": "persona", "label": role, "category": "persona"}
        for role in sorted(PERSONAS)
    ]


# ---- Detail endpoint ---------------------------------------------------------


def _read_skill_description(skill_id: str) -> str | None:
    """Pull `description:` from the matching SKILL.md frontmatter."""
    if not SKILLS_DIR.exists():
        return None
    for child in SKILLS_DIR.iterdir():
        if not child.is_dir():
            continue
        skill_md = child / "SKILL.md"
        if not skill_md.exists():
            continue
        try:
            text = skill_md.read_text()
        except OSError:
            continue
        name = _read_skill_name(skill_md) or child.name
        if name != skill_id:
            continue
        m = re.search(r"^description:\s*(.+)$", text, re.MULTILINE)
        return m.group(1).strip() if m else None
    return None


def _read_mcp_description(mcp_id: str) -> str | None:
    """Pull the first paragraph of the module docstring from `mcp_tools/<id>.py`."""
    py = MCP_TOOL_PATHS.get(mcp_id)
    if py is None or not py.exists():
        return None
    try:
        text = py.read_text()
    except OSError:
        return None
    m = re.search(r'^"""(.*?)"""', text, re.DOTALL)
    if not m:
        return None
    body = m.group(1).strip()
    para = re.split(r"\n\s*\n", body, maxsplit=1)[0].strip()
    return " ".join(para.split())


def _read_persona_description(role: str) -> str | None:
    """Pull `description:` from the matching persona SKILL.md frontmatter."""
    skill_md = next(
        (
            root / role / "SKILL.md"
            for root in PERSONAE_ROOTS
            if (root / role / "SKILL.md").exists()
        ),
        None,
    )
    if skill_md is None:
        return None
    try:
        text = skill_md.read_text()
    except OSError:
        return None
    m = re.search(r"^description:\s*(.+)$", text, re.MULTILINE)
    return m.group(1).strip() if m else None


def _capability_meta(city_id: str) -> dict[str, Any]:
    """Per-capability detail used by the click-to-inspect drawer.

    Returns id, kind, label, description, parked_workflow_ids,
    last_called_at (epoch s, or None), recent_invocation_count.

    Reads description from SKILL.md (skills + personas) or the .py module
    docstring (mcp tools). Workflow parking comes from the live
    pending_gates registry for personae; for skills/mcps it's not directly
    tracked so the field is empty.
    """
    kind: str | None = None
    label = city_id
    for c in _gather_mcp_tools():
        if c["id"] == city_id:
            kind = "mcp"
            break
    if kind is None:
        for c in _gather_skills():
            if c["id"] == city_id:
                kind = c["kind"]
                break
    if kind is None:
        for c in _gather_personas():
            if c["id"] == city_id:
                kind = "persona"
                break
    description: str | None = None
    parked: list[dict[str, Any]] = []
    if kind == "mcp":
        description = _read_mcp_description(city_id)
    elif kind in ("skill", "validator"):
        description = _read_skill_description(city_id)
    elif kind == "persona":
        description = _read_persona_description(city_id)
        # Use the same canonical resolver the persona index route uses —
        # the helper is in api/server/routes/personas. NO swallowing of
        # ImportError this time: if it can't load, that's a real bug.
        from api.server.routes.personas import _compute_persona_pending_and_decisions
        pending_by_role, _ = _compute_persona_pending_and_decisions()
        for entry in pending_by_role.get(city_id, []):
            wid = entry.get("workflow_id")
            if not wid:
                continue
            parked.append({
                "workflow_id": wid,
                "workflow_type": entry.get("workflow_type"),
                "phase": entry.get("phase"),
                "age_s": entry.get("age_s"),
            })
    last_called_at: float | None = None
    recent_count = 0
    try:
        from api.server.services.blueprint_recorder import recent_events  # type: ignore
        evs = recent_events(2000)
        for ev in evs:
            ev_city = (
                ev.get("capability")
                or ev.get("skill")
                or ev.get("mcp")
                or ev.get("persona")
                or ev.get("kind")
            )
            if ev_city == city_id:
                recent_count += 1
                ts = ev.get("ts") or ev.get("timestamp")
                if ts is not None and (last_called_at is None or ts > last_called_at):
                    last_called_at = float(ts)
    except Exception:
        pass
    return {
        "id": city_id,
        "kind": kind or "unknown",
        "label": label,
        "description": description,
        "parked_workflows": parked,
        "last_called_at": last_called_at,
        "recent_invocation_count": recent_count,
    }


# ---- Entities mode -----------------------------------------------------------


def _gather_entity_types() -> list[dict[str, Any]]:
    """Return cities for the 8 real entity-graph kinds with live counts."""
    from api.server.state import app_state
    try:
        counts = app_state.entities.count_by_kind()
    except Exception:
        counts = {k: 0 for k in ENTITY_KINDS}
    out: list[dict[str, Any]] = []
    for k in ENTITY_KINDS:
        cnt = int(counts.get(k, 0))
        try:
            rate = float(app_state.entities.recent_activity_per_min(k))
        except Exception:
            rate = 0.0
        out.append({
            "id": k,
            "kind": "entity_type",
            "label": k,
            "category": "entity",
            "count": cnt,
            "recent_activity_per_min": round(rate, 2),
            "active": cnt > 0 or rate > 0.0,
        })
    return out


# ---- Routes ------------------------------------------------------------------


@router.get("")
def list_cities(
    mode: str = Query("capabilities"),
    actor: Actor = Depends(require_actor),
) -> dict[str, Any]:
    # NOTE: per-role projector is intentionally a no-op for cities — the
    # roster (tool / skill / persona names + entity-type counts) is
    # operational metadata, not user content. Sensitivity is enforced at
    # ingress via ``require_actor``.
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
def cities_affinity(
    kind: str | None = Query(None),
    actor: Actor = Depends(require_actor),
) -> dict[str, Any]:
    """Pairwise city co-occurrence. With ?kind= returns rels incident to that kind."""
    if kind is not None:
        from api.server.state import app_state
        try:
            rows = app_state.entities.rel_counts()
        except Exception:
            rows = []
        filtered = [
            {
                "rel": r["rel"],
                "partner_kind": r["to_kind"] if r["from_kind"] == kind else r["from_kind"],
                "count": int(r.get("count", 0)),
            }
            for r in rows
            if r["from_kind"] == kind or r["to_kind"] == kind
        ]
        filtered.sort(key=lambda x: -x["count"])
        return {"kind": kind, "rels": filtered}
    now = time.time()
    if _AFFINITY_CACHE["data"] is None or now - _AFFINITY_CACHE["ts"] > _AFFINITY_TTL_S:
        _AFFINITY_CACHE["data"] = _compute_affinity()
        _AFFINITY_CACHE["ts"] = now
    return _AFFINITY_CACHE["data"]


# ---- Entity edges (Phase D) --------------------------------------------------


@router.get("/edges")
def entity_edges(actor: Actor = Depends(require_actor)) -> dict[str, Any]:
    """Persistent entity-type edges derived from `_REL_TABLES` with live counts."""
    from api.server.state import app_state
    try:
        rows = app_state.entities.rel_counts()
    except Exception:
        rows = []
    edges = [
        {
            "from_kind": r["from_kind"],
            "to_kind": r["to_kind"],
            "rel": r["rel"],
            "label": r["rel"].lower(),
            "count": int(r.get("count", 0)),
        }
        for r in rows
    ]
    return {"edges": edges, "count": len(edges)}


# IMPORTANT: keep this catch-all dynamic route LAST in the file. FastAPI
# matches routes in declaration order; defining /{city_id} before /affinity
# or /edges would steal those requests because the path parameter matches
# anything.
@router.get("/{city_id}")
def get_city(
    city_id: str,
    actor: Actor = Depends(require_actor),  # noqa: B008
) -> dict[str, Any]:
    """Capability detail for the click-to-inspect drawer.

    Returns description, kind, parked workflows, recent invocation count,
    and last-called timestamp. See `_capability_meta` for the source of
    each field.
    """
    return _capability_meta(city_id)

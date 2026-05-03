"""Blueprint inventory — read the case of type from disk.

Reads ``api/server/skills/*/SKILL.md`` and ``api/server/mcp_tools/*.py`` and
returns a structured composition tree consumed by ``web/blueprint``.

Single source of truth for adding a domain to the page is the ``DOMAINS``
list below. Each domain declares:

  - name           — human-readable label rendered in the UI
  - status         — "live" (drawn solid) | "aspirational" (drawn dashed)
  - workflow_type  — the value the runtime emits as `workflow_type` on
                     FleetEvents. The mind-map uses this to map an event
                     stream back to a domain.
  - skills         — list of skill names (matching SKILL.md `name:` field
                     or directory name) this domain composes.
  - phase_aliases  — { skill_name: phase_label } pairs for the mind-map's
                     phase orbit. A skill not present here will appear in
                     the orbit without a phase label.

To add a new domain to the visualisation:

  1. Append an entry to DOMAINS.
  2. (Optional) Add a stream template to the dev demo trickle in
     api/server/routes/blueprint.py so the page lights up for it.

Nothing else changes. The frontend reads everything from the composition
tree response.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[3]
SKILLS_DIR = REPO_ROOT / "api" / "server" / "skills"
MCP_TOOLS_DIR = REPO_ROOT / "api" / "server" / "mcp_tools"


# --------------------------------------------------------------------------
# Domain manifest. Single source of truth.
# --------------------------------------------------------------------------
DOMAINS: list[dict[str, Any]] = [
    {
        "name": "Finance Compliance",
        "status": "live",
        "workflow_type": "expense-claim",
        "skills": [
            "field-extractor",
            "line-item-extractor",
            "rag-classifier",
            "receipt-validator",
            "escalation-advisor",
            "notification-composer",
            "arbitration",
            "anomaly-flagger",
            "exception-classifier",
            "resolution-recommender",
            "root-cause-explainer",
            "audit-summariser",
            "use-document-intelligence",
        ],
        "phase_aliases": {
            "field-extractor": "Intake",
            "line-item-extractor": "Intake",
            "rag-classifier": "Classify",
            "receipt-validator": "Receipt",
            "escalation-advisor": "Route",
            "notification-composer": "Notify",
            "arbitration": "Arbitrate",
            "audit-summariser": "Audit",
        },
    },
    {
        "name": "Hiring",
        "status": "live",
        "workflow_type": "hiring",
        "skills": [
            "budget-checker",
            "jd-drafter",
            "sourcing-orchestrator",
            "cv-crystalliser",
            "auto-shortlister",
            "voice-screener",
            "interview-recommender",
            "interview-coordinator",
            "jurisdiction-router",
            "betrvg-checker",
            "offer-personaliser",
            "exception-classifier",
            "use-document-intelligence",
        ],
        "phase_aliases": {
            "budget-checker": "Budget",
            "jd-drafter": "Job Design",
            "sourcing-orchestrator": "Sourcing",
            "cv-crystalliser": "Triage",
            "auto-shortlister": "Screening",
            "voice-screener": "Voice",
            "interview-recommender": "Interview",
            "interview-coordinator": "Interview",
            "jurisdiction-router": "Compliance",
            "betrvg-checker": "Compliance",
            "offer-personaliser": "Offer",
        },
    },
    {
        "name": "Onboarding",
        "status": "live",
        "workflow_type": "onboarding",
        "skills": [
            "onboarding-buddy",
        ],
        "phase_aliases": {
            "onboarding-buddy": "Onboarding",
        },
    },
    {
        # First domain composed by compose-domain (sandbox 20260503-104041,
        # graduated commit 7146290d). Lives in api/functions/workflows/
        # fleet_travel_preapproval.py + per-phase graphs; the runtime emits
        # workflow_type="travel-preapproval" via the simulator entry.
        "name": "Travel pre-approval",
        "status": "live",
        "workflow_type": "travel-preapproval",
        "skills": [
            "fleet-travel-preapproval-policy-fit-checker",
        ],
        "phase_aliases": {
            "fleet-travel-preapproval-policy-fit-checker": "Policy fit",
        },
    },
    {
        "name": "Procurement",
        "status": "aspirational",
        "workflow_type": None,
        "skills": [],
        "phase_aliases": {},
    },
    {
        "name": "Legal",
        "status": "aspirational",
        "workflow_type": None,
        "skills": [],
        "phase_aliases": {},
    },
    {
        "name": "IT",
        "status": "aspirational",
        "workflow_type": None,
        "skills": [],
        "phase_aliases": {},
    },
]

# --------------------------------------------------------------------------
# Aspirational meta-skills — designed but not yet shipped.
# Section 6 renders these as faint dashed cards inside the skills row to make
# the recursive point visible without overclaiming.
# --------------------------------------------------------------------------
META_SKILLS: list[dict[str, Any]] = [
    {
        "name": "skill-author",
        "status": "designed",
        "description": (
            "Reads a spec, inventories the existing case of type, "
            "and writes a new SKILL.md."
        ),
        "allowed_tools": [
            "read_existing_skills",
            "read_mcp_catalog",
            "write_skill",
            "propose_skill_amplification",
            "dry_run_policy",
        ],
    },
    {
        "name": "mcp-author",
        "status": "designed",
        "description": (
            "Reads a spec, identifies missing capability, "
            "and writes a new MCP tool."
        ),
        "allowed_tools": [
            "read_mcp_catalog",
            "write_mcp_tool",
            "propose_skill_amplification",
            "dry_run_policy",
        ],
    },
]


# --------------------------------------------------------------------------
# YAML frontmatter parsing for SKILL.md. Only handles the keys we care about
# (name, description, allowed-tools, model). Avoids a yaml dependency to keep
# this module dependency-free.
# --------------------------------------------------------------------------
_FRONTMATTER_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n", re.DOTALL)


def _split_csv_or_block(value: str) -> list[str]:
    """Parse a frontmatter scalar that may be a CSV string or a YAML block.

    Handles both single-line ``allowed-tools: a, b, c`` and a continuation
    line wrapped onto the next line via YAML block-scalar conventions. The
    skill files in this repo use a mix of both.
    """
    parts: list[str] = []
    for raw in value.replace("\n", ",").split(","):
        item = raw.strip().strip("\"'")
        if item and item != "-":
            # Strip leading "- " from YAML lists and trailing punctuation.
            item = re.sub(r"^[-\s]+", "", item)
            if item:
                parts.append(item)
    return parts


def _parse_frontmatter(text: str) -> dict[str, Any]:
    """Parse a small YAML-ish frontmatter block.

    Handles the two patterns used in this repo's SKILL.md files:

      key: value-on-same-line
      multi-line:
        - item-a
        - item-b
      another:
        first chunk
        second chunk continuation

    And the trickiest one — value on same line *plus* continuation indent:

      allowed-tools: a, b, c,
        d, e
    """
    match = _FRONTMATTER_RE.match(text)
    if not match:
        return {}
    block = match.group(1)
    data: dict[str, Any] = {}
    current_key: str | None = None
    for raw_line in block.splitlines():
        if not raw_line.strip():
            continue
        # Indented continuation of the previous key. Append to whatever
        # the previous line stored; works whether that value is empty or not.
        if raw_line.startswith((" ", "\t")) and current_key is not None:
            existing = data.get(current_key, "")
            extra = raw_line.strip()
            if existing:
                data[current_key] = f"{existing} {extra}"
            else:
                data[current_key] = extra
            continue
        line = raw_line.rstrip()
        if ":" in line:
            key, _, rest = line.partition(":")
            key = key.strip()
            rest = rest.strip()
            data[key] = rest
            current_key = key
        else:
            current_key = None
    return data


# --------------------------------------------------------------------------
# Public API
# --------------------------------------------------------------------------


@dataclass
class Skill:
    name: str
    description: str
    allowed_tools: list[str]
    model: str | None
    status: str = "live"  # "live" | "designed"


@dataclass
class McpTool:
    name: str
    file: str  # filename without extension


def _load_skills() -> list[Skill]:
    skills: list[Skill] = []
    for skill_md in sorted(SKILLS_DIR.glob("*/SKILL.md")):
        text = skill_md.read_text(encoding="utf-8")
        fm = _parse_frontmatter(text)
        name = fm.get("name") or skill_md.parent.name
        description = fm.get("description", "").strip()
        raw_tools = fm.get("allowed-tools", "")
        tools = _split_csv_or_block(raw_tools) if raw_tools else []
        model = fm.get("model")
        skills.append(
            Skill(
                name=name,
                description=description,
                allowed_tools=tools,
                model=model,
                status="live",
            )
        )
    return skills


def _load_mcp_tools() -> list[McpTool]:
    """Enumerate MCP tool files. We list the modules; the registered name is
    derived from the filename (kebab-cased to snake-case in this repo's
    convention)."""
    tools: list[McpTool] = []
    for path in sorted(MCP_TOOLS_DIR.glob("*.py")):
        stem = path.stem
        if stem.startswith("_") or stem == "__init__":
            continue
        tools.append(McpTool(name=stem, file=path.name))
    return tools


def _normalise_tool(name: str) -> str:
    """Skill frontmatter mixes ``policy_search``, ``policy.search``, and
    ``query-fleet``. Normalise to the underscore form used by the MCP tool
    filenames so the composition edges line up."""
    cleaned = name.strip().lower()
    cleaned = cleaned.replace(".", "_").replace("-", "_")
    return cleaned


def composition_tree() -> dict[str, Any]:
    """Build the JSON payload for ``GET /api/blueprint/composition``.

    Returns a tree the page can render directly:

      {
        "skills":           [{ name, description, allowed_tools, model, domains[], status }],
        "mcps":             [{ name, used_by_skills[] }],
        "domains":          [{ name, status, workflow_type, skills[], tools[] }],
        "meta_skills":      [...],
        "workflow_types":   { workflow_type_str: domain_name }   # for the mindmap
        "phase_aliases":    { skill_name: phase_label }          # for the mindmap
        "counts":           { skills, mcps, domains_live, domains_aspirational }
      }
    """
    skills = _load_skills()
    mcps = _load_mcp_tools()
    skill_names = {s.name for s in skills}
    mcp_names = {t.name for t in mcps}

    # Build skill -> domains lookup.
    skill_to_domains: dict[str, list[str]] = {}
    for domain in DOMAINS:
        if domain["status"] != "live":
            continue
        for skill_name in domain["skills"]:
            if skill_name in skill_names:
                skill_to_domains.setdefault(skill_name, []).append(domain["name"])

    # Build mcp -> skills lookup, normalising tool names for matching.
    mcp_to_skills: dict[str, list[str]] = {name: [] for name in mcp_names}
    for skill in skills:
        for tool in skill.allowed_tools:
            normalised = _normalise_tool(tool)
            if normalised in mcp_to_skills:
                mcp_to_skills[normalised].append(skill.name)

    # Resolve each domain's tool set (union of its skills' allowed-tools).
    domain_payload: list[dict[str, Any]] = []
    for domain in DOMAINS:
        domain_skills = [s for s in skills if s.name in domain["skills"]]
        domain_tools_raw: set[str] = set()
        for s in domain_skills:
            for t in s.allowed_tools:
                norm = _normalise_tool(t)
                if norm in mcp_names:
                    domain_tools_raw.add(norm)
        domain_payload.append(
            {
                "name": domain["name"],
                "status": domain["status"],
                "workflow_type": domain.get("workflow_type"),
                "skills": [s for s in domain["skills"] if s in skill_names],
                "tools": sorted(domain_tools_raw),
            }
        )

    skills_payload = [
        {
            "name": s.name,
            "description": s.description,
            "allowed_tools": [
                _normalise_tool(t) for t in s.allowed_tools if _normalise_tool(t) in mcp_names
            ],
            "model": s.model,
            "domains": skill_to_domains.get(s.name, []),
            "status": s.status,
        }
        for s in skills
    ]

    mcps_payload = [
        {
            "name": t.name,
            "used_by_skills": sorted(set(mcp_to_skills.get(t.name, []))),
        }
        for t in mcps
    ]

    # Reverse lookups the frontend needs but should not hard-code:
    #   workflow_type "hiring" -> domain "Hiring"
    #   skill "cv-crystalliser" -> phase "Triage"
    workflow_types: dict[str, str] = {}
    phase_aliases: dict[str, str] = {}
    for domain in DOMAINS:
        wt = domain.get("workflow_type")
        if wt:
            workflow_types[wt] = domain["name"]
        for skill_name, phase_label in (domain.get("phase_aliases") or {}).items():
            # Per-domain overrides are merged; later domains win on collision.
            phase_aliases[skill_name] = phase_label

    counts = {
        "skills": len(skills),
        "mcps": len(mcps),
        "domains_live": sum(1 for d in DOMAINS if d["status"] == "live"),
        "domains_aspirational": sum(1 for d in DOMAINS if d["status"] != "live"),
    }

    return {
        "skills": skills_payload,
        "mcps": mcps_payload,
        "domains": domain_payload,
        "meta_skills": META_SKILLS,
        "workflow_types": workflow_types,
        "phase_aliases": phase_aliases,
        "counts": counts,
    }

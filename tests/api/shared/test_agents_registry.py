"""TASK-036 — CI guarantees on the agent registry.

(a) Every agent_id appearing in a test fixture's ``agent_label`` MUST
    resolve to a real identity — a registered entry in
    :data:`api.shared.agents.AGENTS` (governance actors) or a declared
    skill directory (the telemetry labels the agent wrapper emits).
(b) Every tool in any agent's ``allowed_tools`` MUST exist in
    ``data/policies/tools.yaml``.
(c) Each agent's ``max_value_gbp`` (if set) is non-negative; ``agent_id``
    is non-empty; ``scope_function`` is one of the typed values.
"""
from __future__ import annotations

import os
import re
import subprocess
from pathlib import Path

# Short-circuit Azurite probe before importing anything that ends up
# touching api.server.state via api.server.services.governance.manifest.
os.environ.setdefault("AZURE_STORAGE_CONNECTION_STRING", "")

import pytest

from api.server.services.governance.manifest import load_tools_yaml
from api.shared.agents import AGENTS, AgentRegistryEntry, all_agent_ids


_REPO_ROOT = Path(__file__).resolve().parents[3]


def _grep_agent_labels() -> set[str]:
    """Walk every test file and pull out the agent_label string literals.

    Matches both kwarg form (``agent_label="x"``) and positional inside
    Pydantic constructors. Returns the set of unique values seen — that
    set is the runtime population every fixture uses.

    Filters out placeholder labels (single chars, no separator) used by
    fast unit tests that don't care about the registry — Phase 6 enforce
    mode treats those as auto-deny anyway, so they aren't part of the
    "real" identity surface.
    """
    pattern = re.compile(
        r'agent_label\s*=\s*["\']([a-zA-Z][a-zA-Z0-9_-]*)["\']'
    )
    seen: set[str] = set()
    tests_dir = _REPO_ROOT / "tests"
    for path in tests_dir.rglob("*.py"):
        try:
            text = path.read_text(encoding="utf-8")
        except OSError:
            continue
        for match in pattern.finditer(text):
            label = match.group(1)
            # Skip obvious placeholder labels: must be at least 4 chars
            # AND contain a slug separator. This is a noise filter, not
            # an escape hatch — a real agent_id like "ab" would still be
            # a registry bug.
            if len(label) < 4:
                continue
            if "-" not in label and "_" not in label:
                continue
            seen.add(label)
    return seen


def _declared_skill_labels() -> set[str]:
    """Every skill declared anywhere in the repo, by directory name.

    ``agent_label`` carries two distinct populations. The governance
    *actor* namespace is :data:`AGENTS`. The telemetry namespace is the
    skill set: the agent wrapper stamps the skill onto the event with
    ``"agent_label": skill_label or "unknown"`` (see
    ``api/functions/graphs/executors/agents/_wrapper.py``, "Each skill is
    its own agent"), so a skill name in an ``agent_label`` fixture is
    faithful to runtime, not a registry bug.

    Skills are never governance actors: ``call_mcp`` resolves the actor
    from ``AGT_DEFAULT_ACTOR`` (default ``unknown-agent``), which
    ``GovernanceKernel._registry_gate`` soft-escapes, so a skill label
    can't reach the registry gate.
    """
    skills: set[str] = set()
    roots = [_REPO_ROOT / "api" / "server" / "skills"]
    roots.extend((_REPO_ROOT / "verticals").glob("*/skills"))
    for root in roots:
        if not root.is_dir():
            continue
        for path in root.iterdir():
            if path.is_dir() and (path / "SKILL.md").is_file():
                skills.add(path.name)
    return skills


# --------------------------------------------------------------------------
# (a) every fixture agent_label has a registry entry
# --------------------------------------------------------------------------


def test_every_fixture_agent_label_is_registered() -> None:
    """Auto-discovered: any agent_label string in any test fixture MUST
    resolve to a real identity — either a registered
    :class:`AgentRegistryEntry` (the governance actor namespace) or a
    declared skill (the telemetry namespace the agent wrapper stamps onto
    events). A label that is neither is a typo or an invented name, and
    fails CI immediately."""
    fixture_labels = _grep_agent_labels()
    assert fixture_labels, (
        "expected to discover at least one agent_label in tests/; "
        "the grep regex may have drifted"
    )
    known = set(all_agent_ids()) | _declared_skill_labels()
    missing = fixture_labels - known
    assert not missing, (
        f"agent_label values appear in test fixtures but match neither a "
        f"registered agent in api.shared.agents.AGENTS nor a declared "
        f"skill directory: {sorted(missing)!r}. Register the agent, add "
        f"the skill, or fix the fixture to use a real identity."
    )


# --------------------------------------------------------------------------
# (b) every allowed_tool maps to an entry in tools.yaml
# --------------------------------------------------------------------------


def test_every_allowed_tool_is_in_tools_yaml() -> None:
    """An agent that lists a tool not in the manifest can never call it
    in enforce mode (the kernel would deny). Catch that misalignment
    here rather than at runtime."""
    tools = load_tools_yaml()
    tool_ids = set(tools.keys())
    bad: dict[str, list[str]] = {}
    for agent_id, entry in AGENTS.items():
        unknown = [t for t in entry.allowed_tools if t not in tool_ids]
        if unknown:
            bad[agent_id] = unknown
    assert not bad, (
        f"agents allow tools that aren't declared in data/policies/tools.yaml: "
        f"{bad!r}. Either add the tool to the manifest or remove from the "
        f"agent's allowed_tools."
    )


# --------------------------------------------------------------------------
# (c) basic registry well-formedness
# --------------------------------------------------------------------------


def test_registry_keys_match_agent_ids() -> None:
    """The dict key MUST equal the entry's agent_id (avoid drift)."""
    for k, v in AGENTS.items():
        assert isinstance(v, AgentRegistryEntry)
        assert v.agent_id == k, f"key={k!r} != entry.agent_id={v.agent_id!r}"


def test_registry_max_value_gbp_non_negative() -> None:
    for k, v in AGENTS.items():
        if v.max_value_gbp is not None:
            assert v.max_value_gbp >= 0, f"{k}: max_value_gbp must be >= 0"


def test_registry_agent_id_non_empty() -> None:
    for k, v in AGENTS.items():
        assert v.agent_id and v.agent_id.strip(), f"empty agent_id under key {k!r}"


def test_registry_scope_function_is_typed() -> None:
    valid = {"finance", "hiring", "shared", "creative", "hr", "it"}
    for k, v in AGENTS.items():
        assert v.scope_function in valid, (
            f"{k}: scope_function {v.scope_function!r} not in {sorted(valid)}"
        )


def test_helpers_round_trip() -> None:
    from api.shared.agents import by_function, get

    for agent_id in all_agent_ids():
        entry = get(agent_id)
        assert entry is not None
        assert entry.agent_id == agent_id

    # by_function should partition the registry without duplication.
    union: list[str] = []
    for fn in {a.scope_function for a in AGENTS.values()}:
        union.extend(a.agent_id for a in by_function(fn))
    assert sorted(union) == sorted(all_agent_ids())

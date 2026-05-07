"""Policy bundle compiler.

Per ``plan/feature-agent-governance-toolkit-1.md`` TASK-012. Pure
function: ``(matrix.json, tools.yaml, agents) -> (PolicyDocument, version_hash)``.

Determinism (SEC-001)
---------------------
Same inputs → byte-identical YAML serialisation → byte-identical sha256.
We achieve this by:

- Sorting matrix rows by ``rule_id`` and tools dict by ``id`` before
  emitting rules.
- Using ``yaml.safe_dump`` with ``sort_keys=True`` and a fixed key order
  on every dict via Pydantic ``model_dump`` (Pydantic v2 preserves
  field-declaration order, which we treat as the canonical order).
- Stripping any timestamps / non-deterministic metadata — the bundle is
  pure data.

Phase 2 scope
-------------
- Tool rules: one per tool, ``condition: tool == <id>``, ``action: AUDIT``.
  These give every tool call a stable ``matched_rule`` for traceability
  even when the kernel is in log-only mode.
- Matrix rules: one per row, ``condition: action == <action>``,
  ``action: AUDIT``. These cover the 19 authority actions; Phase 3
  uses them inside ``resolve_approver`` for in-process resolution.
- Defaults: ``ALLOW`` so the log-only Phase 2 + 3 flow keeps the
  90/90 test suite green.
- Agents argument is accepted for forward compatibility (Phase 5
  populates it) and is included in the version hash even when empty,
  so adding the registry in Phase 5 changes the version monotonically.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Any, Mapping, Sequence

import yaml
from agent_os.policies import (
    PolicyAction,
    PolicyCondition,
    PolicyDefaults,
    PolicyDocument,
    PolicyOperator,
    PolicyRule,
)

from .manifest import ToolManifestEntry

# Priority bands. Higher = checked first by AGT.
# Phase 6 (TASK-045) adds a top band for hand-authored capability rules
# at priority >= 100. Reserve the 0-99 band for compiler-derived rules.
_PRIO_TOOL_RULE = 30  # per-tool registration rule
_PRIO_MATRIX_RULE = 20  # per matrix-row authority rule
_PRIO_AGENT_RULE = 50  # reserved for Phase 5 agent capability rules

POLICY_NAME = "apex-substrate"
POLICY_DOC_VERSION = "1.0"


@dataclass(frozen=True)
class CompiledBundle:
    """Output of :func:`compile_bundle`. Carried on the kernel."""

    document: PolicyDocument
    yaml_text: str
    version_hash: str  # sha256 hex of yaml_text
    rule_count: int

    @property
    def short_version(self) -> str:
        return self.version_hash[:12]


# ---------------------------------------------------------------------------
# Compiler
# ---------------------------------------------------------------------------


def compile_bundle(
    matrix: Sequence[Mapping[str, Any]],
    tools: Mapping[str, ToolManifestEntry],
    agents: Mapping[str, Any] | None = None,
) -> CompiledBundle:
    """Compile a deterministic AGT policy bundle.

    Parameters
    ----------
    matrix:
        The decoded ``data/synthetic/authority/matrix.json`` list of
        rule dicts. Each row must carry at least ``rule_id`` and
        ``action``; other fields surface in the rule message for
        post-hoc evidence.
    tools:
        The validated ``tools.yaml`` map (from :func:`manifest.load_tools_yaml`).
    agents:
        Phase 5 hook; ignored in Phase 2 but included in the version
        hash so adding the registry causes a visible bundle change.

    Returns
    -------
    A :class:`CompiledBundle` carrying the constructed
    :class:`PolicyDocument`, the canonical YAML serialisation, and the
    sha256 hex (full + 12-char) of the YAML.
    """
    rules: list[PolicyRule] = []

    # -- per-tool rules (sorted by id for determinism) ----------------------
    for tool_id in sorted(tools.keys()):
        entry = tools[tool_id]
        rules.append(
            PolicyRule(
                name=f"tool:{tool_id}",
                condition=PolicyCondition(
                    field="tool",
                    operator=PolicyOperator.EQ,
                    value=tool_id,
                ),
                action=PolicyAction.AUDIT,
                priority=_PRIO_TOOL_RULE,
                message=(
                    f"tool {tool_id} (reversible={entry.reversible}, "
                    f"requires_authority={entry.requires_authority}, "
                    f"scope={entry.scope_function})"
                ),
            )
        )

    # -- per-matrix-row rules (sorted by rule_id for determinism) -----------
    sorted_matrix = sorted(matrix, key=lambda r: str(r.get("rule_id", "")))
    for row in sorted_matrix:
        rule_id = str(row.get("rule_id", ""))
        action = str(row.get("action", ""))
        approver = str(row.get("approver_role", "?"))
        band = row.get("value_band_gbp", {}) or {}
        message = (
            f"matrix:{rule_id} action={action} approver={approver} "
            f"band=({band.get('min')},{band.get('max')}) "
            f"basis={row.get('basis', '')!r}"
        )
        rules.append(
            PolicyRule(
                name=f"matrix:{rule_id}",
                condition=PolicyCondition(
                    field="action",
                    operator=PolicyOperator.EQ,
                    value=action,
                ),
                action=PolicyAction.AUDIT,
                priority=_PRIO_MATRIX_RULE,
                message=message,
            )
        )

    document = PolicyDocument(
        version=POLICY_DOC_VERSION,
        name=POLICY_NAME,
        description=(
            "Compiled from data/synthetic/authority/matrix.json + "
            "data/policies/tools.yaml. See "
            "plan/feature-agent-governance-toolkit-1.md (TASK-012)."
        ),
        rules=rules,
        defaults=PolicyDefaults(action=PolicyAction.ALLOW),
    )

    yaml_text = _canonical_yaml(document, agents or {})
    version_hash = hashlib.sha256(yaml_text.encode("utf-8")).hexdigest()
    return CompiledBundle(
        document=document,
        yaml_text=yaml_text,
        version_hash=version_hash,
        rule_count=len(rules),
    )


# ---------------------------------------------------------------------------
# Canonical serialisation
# ---------------------------------------------------------------------------


def _canonical_yaml(document: PolicyDocument, agents: Mapping[str, Any]) -> str:
    """Emit a byte-deterministic YAML dump of the policy document.

    We round-trip through ``model_dump`` so enums become their
    string values (PolicyAction.ALLOW -> "allow"), then through
    ``json.loads(json.dumps(..., sort_keys=True, default=str))`` to
    canonicalise nested dict ordering, then through ``yaml.safe_dump``
    with ``sort_keys=True`` and ``default_flow_style=False`` for the
    final canonical text.

    The ``agents`` mapping is folded in as a top-level ``agents:`` key
    so adding agent identities in Phase 5 produces a different
    ``version_hash`` even though it doesn't yet add rules.
    """
    payload: dict[str, Any] = {
        "policy": document.model_dump(mode="json"),
        "agents": _canonicalise(agents),
    }
    # JSON round-trip canonicalises dict ordering and turns any leftover
    # non-JSON types (Enum, etc.) into strings.
    canonical = json.loads(json.dumps(payload, sort_keys=True, default=str))
    return yaml.safe_dump(
        canonical,
        sort_keys=True,
        default_flow_style=False,
        width=1000,
        allow_unicode=True,
    )


def _canonicalise(obj: Any) -> Any:
    """Recursively canonicalise mappings/sequences for stable serialisation."""
    if isinstance(obj, Mapping):
        return {k: _canonicalise(obj[k]) for k in sorted(obj.keys(), key=str)}
    if isinstance(obj, (list, tuple)):
        return [_canonicalise(x) for x in obj]
    return obj

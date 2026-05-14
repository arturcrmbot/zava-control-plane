"""Phase 2 compiler tests — TASK-013.

Covers:

- Determinism: same inputs → byte-identical YAML → identical hash.
- Coverage: every tool in the manifest gets a ``tool:<id>`` rule;
  every matrix row gets a ``matrix:<rule_id>`` rule.
- Evaluation: 8 canonical authority actions (one per major domain)
  match a matrix-derived AUDIT rule.

Snapshot files:
- ``snapshots/policy_version.txt``  — sha256 hex of the canonical YAML.
- ``snapshots/policy_bundle.yaml``  — the canonical YAML serialisation.

Both snapshots are recreated on first run via ``pytest --regen`` (see the
``_maybe_regen`` helper). After that the tests assert byte equality. Any
change to ``matrix.json`` / ``tools.yaml`` / the compiler output requires
either a deliberate snapshot bump or a code fix — never a silent diff.
"""
from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from api.server.services.governance.manifest import load_tools_yaml
from api.server.services.governance.policy_compiler import compile_bundle

# Canonical 8-domain probe set: action name + a sample value within band.
# Mirrors the "8 canonical resolutions" set referenced in
# plan/feature-authority-and-personae-1.md TASK-006.
CANONICAL_ACTIONS: list[tuple[str, dict]] = [
    ("expense_claim_approval", {"value": 250.0}),
    ("travel_preapproval", {"value": 1500.0}),
    ("hire_offer_approval", {"value": 80000.0}),
    ("hire_budget_approval", {"value": 200000.0}),
    ("contract_renewal_signoff", {"value": 50000.0}),
    ("ap_invoice_approval", {"value": 4500.0}),
    ("vendor_kyc_signoff", {"value": None}),
    ("privacy_dpia_signoff", {"value": None}),
]


def _repo_root() -> Path:
    here = Path(__file__).resolve()
    for parent in here.parents:
        if (parent / "pyproject.toml").is_file():
            return parent
    raise RuntimeError("repo root not found")


def _matrix() -> list[dict]:
    p = _repo_root() / "data" / "synthetic" / "authority" / "matrix.json"
    return json.loads(p.read_text(encoding="utf-8"))


def _snapshot_dir() -> Path:
    d = Path(__file__).parent / "snapshots"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _maybe_regen(name: str, content: str) -> Path:
    """When the env var ``REGEN_GOLDEN=1`` is set OR the snapshot is
    absent, write the snapshot and return its path. Otherwise return
    the existing snapshot path."""
    p = _snapshot_dir() / name
    if os.environ.get("REGEN_GOLDEN", "").strip() == "1" or not p.exists():
        p.write_text(content, encoding="utf-8")
    return p


# ---------------------------------------------------------------------------
# Determinism
# ---------------------------------------------------------------------------


def test_compile_is_deterministic() -> None:
    """Same inputs twice → byte-identical YAML + identical hash."""
    tools = load_tools_yaml()
    matrix = _matrix()
    a = compile_bundle(matrix=matrix, tools=tools)
    b = compile_bundle(matrix=matrix, tools=tools)
    assert a.yaml_text == b.yaml_text
    assert a.version_hash == b.version_hash
    assert a.rule_count == b.rule_count


def test_compile_changes_when_inputs_change() -> None:
    """Adding a row to the matrix must change the hash. Trivial proof
    that the version_hash actually depends on the inputs."""
    tools = load_tools_yaml()
    matrix = _matrix()
    base = compile_bundle(matrix=matrix, tools=tools)

    extra_matrix = list(matrix) + [
        {
            "rule_id": "ZZZ-TEST",
            "action": "synthetic_action_for_test",
            "value_band_gbp": {"min": 0, "max": 100},
            "approver_role": "auto",
            "basis": "synthetic test row",
        }
    ]
    bumped = compile_bundle(matrix=extra_matrix, tools=tools)
    assert bumped.version_hash != base.version_hash
    assert bumped.rule_count == base.rule_count + 1


def test_compile_uses_agents_in_hash() -> None:
    """The agents arg is folded into the version hash so adding the
    Phase 5 registry produces a visible bump (forward-compat)."""
    tools = load_tools_yaml()
    matrix = _matrix()
    base = compile_bundle(matrix=matrix, tools=tools, agents={})
    with_agents = compile_bundle(
        matrix=matrix,
        tools=tools,
        agents={"finance-agent": {"allowed_tools": ["claim.lookup"]}},
    )
    assert base.version_hash != with_agents.version_hash


# ---------------------------------------------------------------------------
# Coverage — every tool + every matrix row produces a rule
# ---------------------------------------------------------------------------


def test_every_tool_has_a_rule() -> None:
    tools = load_tools_yaml()
    bundle = compile_bundle(matrix=_matrix(), tools=tools)
    rule_names = {r.name for r in bundle.document.rules}
    for tool_id in tools:
        assert f"tool:{tool_id}" in rule_names, f"missing rule for tool {tool_id}"


def test_every_matrix_row_has_a_rule() -> None:
    matrix = _matrix()
    bundle = compile_bundle(matrix=matrix, tools=load_tools_yaml())
    rule_names = {r.name for r in bundle.document.rules}
    for row in matrix:
        assert f"matrix:{row['rule_id']}" in rule_names, row["rule_id"]


# ---------------------------------------------------------------------------
# Snapshot — golden YAML + version
# ---------------------------------------------------------------------------


def test_policy_bundle_snapshot_matches() -> None:
    bundle = compile_bundle(matrix=_matrix(), tools=load_tools_yaml())
    snap_path = _maybe_regen("policy_bundle.yaml", bundle.yaml_text)
    assert bundle.yaml_text == snap_path.read_text(encoding="utf-8"), (
        "policy bundle drifted from snapshot. If intentional, re-run with "
        "REGEN_GOLDEN=1."
    )


def test_policy_version_snapshot_matches() -> None:
    bundle = compile_bundle(matrix=_matrix(), tools=load_tools_yaml())
    snap_path = _maybe_regen("policy_version.txt", bundle.version_hash + "\n")
    expected = snap_path.read_text(encoding="utf-8").strip()
    assert bundle.version_hash == expected, (
        f"policy_version hash drifted: got {bundle.version_hash}, "
        f"snapshot {expected}. If intentional, re-run with REGEN_GOLDEN=1."
    )


# ---------------------------------------------------------------------------
# Canonical evaluation — 8 domains
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("action,extra", CANONICAL_ACTIONS)
def test_canonical_action_matches_matrix_rule(action: str, extra: dict) -> None:
    """Each of the 8 canonical authority actions evaluates to ``ALLOW``
    via a matrix-derived AUDIT rule (rules with ``ALLOW`` outcome are
    audited but allowed in Phase 2)."""
    bundle = compile_bundle(matrix=_matrix(), tools=load_tools_yaml())
    from agent_os.policies import PolicyEvaluator
    evaluator = PolicyEvaluator(policies=[bundle.document])

    ctx = {"actor": "test-agent", "tool": "any.tool", "action": action, **extra}
    result = evaluator.evaluate(ctx)
    assert result.allowed is True, f"{action} should be allowed under defaults"
    assert result.matched_rule is not None, f"{action} should match some rule"
    assert result.matched_rule.startswith("matrix:"), (
        f"{action} matched non-matrix rule: {result.matched_rule}"
    )

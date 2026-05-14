"""pitch-d1 / pitch-d3: persona hierarchies must be realistic for a
Tier-1 agency holding — at least 3 layers deep for every business
function. Legacy carries the ``__legacy__`` sentinel and CEO inherits
from finance via reuse of the ``cfo`` root, so both are exempt.
"""
from __future__ import annotations

from api.shared.functions import FUNCTIONS, PersonaTree


def _max_depth(node: PersonaTree) -> int:
    if not node.manages:
        return 1
    return 1 + max(_max_depth(child) for child in node.manages)


# Legacy is the POC1/POC2 sentinel; CEO is intentionally a single-node
# tree (it reuses ``cfo`` and inherits the finance hierarchy).
_EXEMPT = {"legacy", "ceo"}


def test_every_function_hierarchy_is_at_least_three_layers_deep():
    shallow = []
    for name, fn in FUNCTIONS.items():
        if name in _EXEMPT:
            continue
        depth = _max_depth(fn.persona_hierarchy)
        if depth < 3:
            shallow.append((name, depth))
    assert not shallow, (
        f"functions with persona_hierarchy depth <3 (need at least 3 "
        f"layers post pitch-d1): {shallow}"
    )


def test_marketing_creative_branch_is_deep():
    """Marketing's creative tree must reach junior_creative — proves the
    seven-layer creative hierarchy from pitch-d1 stuck."""
    depth = _max_depth(FUNCTIONS["marketing"].persona_hierarchy)
    assert depth >= 6, f"marketing creative tree too shallow: depth={depth}"


def test_finance_hierarchy_includes_regional_layer():
    """pitch-d1 deepens finance with regional controllers + BP pod."""
    seen: set[str] = set()

    def _walk(node: PersonaTree) -> None:
        seen.add(node.role)
        for c in node.manages:
            _walk(c)

    _walk(FUNCTIONS["finance"].persona_hierarchy)
    assert {"regional_controller_emea", "regional_controller_us", "bp_pod_lead"} <= seen


def test_marketing_hierarchy_includes_d3_agency_branches():
    """pitch-d3 plants account-services, strategy/media, production,
    casting and data-science trees alongside the creative chain."""
    seen: set[str] = set()

    def _walk(node: PersonaTree) -> None:
        seen.add(node.role)
        for c in node.manages:
            _walk(c)

    _walk(FUNCTIONS["marketing"].persona_hierarchy)
    expected = {
        "global_account_director", "regional_account_director",
        "account_director", "account_manager", "account_executive",
        "account_coordinator",
        "head_of_strategy", "strategy_director", "planner",
        "media_planner", "media_buyer", "ad_ops_specialist",
        "executive_producer", "producer", "production_coordinator",
        "casting_director", "casting_assistant",
        "head_of_data_science", "data_scientist",
    }
    missing = expected - seen
    assert not missing, f"D3 marketing roles missing from hierarchy: {sorted(missing)}"

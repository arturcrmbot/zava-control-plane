"""Airline Hero 2 Stage 2 – TDD tests for engineering governance, persona,
AOG MCP tools, AOG ranker skill/agent, tool policy, and pack validity.

Run RED first; then implementation turns them GREEN.
"""
from __future__ import annotations

import copy
import json
import re
from pathlib import Path
from typing import Any

import pytest
import yaml
from copilot.tools import ToolInvocation

ROOT = Path(__file__).resolve().parents[3]
AIRLINE_ROOT = ROOT / "verticals" / "airline"


# ---------------------------------------------------------------------------
# Helpers shared across tests
# ---------------------------------------------------------------------------

def _skill_frontmatter(path: Path) -> tuple[dict[str, Any], str]:
    text = path.read_text(encoding="utf-8")
    match = re.fullmatch(r"---\n(.*?)\n---\n(.*)", text, flags=re.DOTALL)
    assert match is not None, f"Invalid SKILL.md format at {path}"
    return yaml.safe_load(match.group(1)), match.group(2)


def _invocation(tool_name: str, arguments: dict[str, Any]) -> ToolInvocation:
    return ToolInvocation(
        session_id="airline-aog-test",
        tool_call_id=f"tool-{tool_name}",
        tool_name=tool_name,
        arguments=arguments,
    )


def _admitted_aog_options() -> list[dict[str, Any]]:
    return [
        {
            "option_id": "AOG-WORK-LOCAL",
            "actions": [
                {"action_type": "authorise_engineering_work", "spare_id": "SYN-SPARE-LOCAL-001"}
            ],
            "evidence_versions": {"SYN-TAIL-003": 1, "SYN-TASK-001": 2},
            "value_gbp": 85_000.0,
            "feasible": True,
            "admitted": True,
        },
        {
            "option_id": "AOG-SUBSTITUTE",
            "actions": [
                {"action_type": "assign_substitute_aircraft", "tail_id": "SYN-TAIL-005"}
            ],
            "evidence_versions": {"SYN-TAIL-003": 1, "SYN-SECTOR-OUT-003": 3},
            "value_gbp": 195_000.0,
            "feasible": True,
            "admitted": True,
        },
    ]


# ===========================================================================
# 1. AIRLINE_AUTHORITY – engineering_duty_manager row
# ===========================================================================

class TestEngineeringDutyManagerAuthority:
    def test_row_exists_with_200k_limit(self) -> None:
        from verticals.airline.authority import AIRLINE_AUTHORITY
        row = AIRLINE_AUTHORITY["engineering_duty_manager"]
        assert row.spend_limit_gbp == 200_000.0

    def test_row_approval_actions_exact(self) -> None:
        from verticals.airline.authority import AIRLINE_AUTHORITY
        row = AIRLINE_AUTHORITY["engineering_duty_manager"]
        assert set(row.approval_actions) == {
            "engineering_duty_manager_decision",
            "airline.commit_aog_recovery",
        }

    def test_row_no_delegation(self) -> None:
        from verticals.airline.authority import AIRLINE_AUTHORITY
        row = AIRLINE_AUTHORITY["engineering_duty_manager"]
        assert row.delegate_to is None

    def test_hero1_authority_preserved(self) -> None:
        from verticals.airline.authority import AIRLINE_AUTHORITY
        row = AIRLINE_AUTHORITY["duty_operations_manager"]
        assert row.spend_limit_gbp == 150_000.0
        assert "duty_operations_manager_decision" in row.approval_actions
        assert "airline.commit_recovery_plan" in row.approval_actions


# ===========================================================================
# 2. AIRLINE_PERSONAS – engineering_duty_manager record
# ===========================================================================

class TestEngineeringDutyManagerPersona:
    def test_persona_exists(self) -> None:
        from verticals.airline.personas import AIRLINE_PERSONAS
        assert "engineering_duty_manager" in AIRLINE_PERSONAS

    def test_persona_archetype_approver(self) -> None:
        from verticals.airline.personas import AIRLINE_PERSONAS
        p = AIRLINE_PERSONAS["engineering_duty_manager"]
        assert p.archetype == "approver"

    def test_persona_scope_function_it(self) -> None:
        from verticals.airline.personas import AIRLINE_PERSONAS
        p = AIRLINE_PERSONAS["engineering_duty_manager"]
        assert p.scope_function == "it"

    def test_persona_external_event(self) -> None:
        from verticals.airline.personas import AIRLINE_PERSONAS
        p = AIRLINE_PERSONAS["engineering_duty_manager"]
        assert p.external_event_default == "engineering_duty_manager_decision"

    def test_persona_uses_authority_mcp(self) -> None:
        from verticals.airline.personas import AIRLINE_PERSONAS
        p = AIRLINE_PERSONAS["engineering_duty_manager"]
        assert p.uses_authority_mcp is True

    def test_persona_display_color_distinct_from_hero1(self) -> None:
        from verticals.airline.personas import AIRLINE_PERSONAS
        edm = AIRLINE_PERSONAS["engineering_duty_manager"]
        dom = AIRLINE_PERSONAS["duty_operations_manager"]
        assert edm.display_color is not None
        assert edm.display_color != dom.display_color

    def test_hero1_persona_preserved(self) -> None:
        from verticals.airline.personas import AIRLINE_PERSONAS
        p = AIRLINE_PERSONAS["duty_operations_manager"]
        assert p.scope_function == "commercial"
        assert p.external_event_default == "duty_operations_manager_decision"


# ===========================================================================
# 3. Persona SKILL.md – engineering_duty_manager
# ===========================================================================

class TestEngineeringDutyManagerSkill:
    @pytest.fixture
    def skill_path(self) -> Path:
        return AIRLINE_ROOT / "personae" / "engineering_duty_manager" / "SKILL.md"

    def test_skill_file_exists(self, skill_path: Path) -> None:
        assert skill_path.is_file()

    def test_frontmatter_keys(self, skill_path: Path) -> None:
        fm, _ = _skill_frontmatter(skill_path)
        assert "name" in fm
        assert "description" in fm
        assert "external_event" in fm
        assert "decision_policy" in fm
        assert "allowed-tools" not in fm  # no tools in persona

    def test_decision_policy_reads_action_and_request(self, skill_path: Path) -> None:
        fm, _ = _skill_frontmatter(skill_path)
        policy = fm["decision_policy"]
        assert "context.get" in policy or 'context or {}' in policy
        assert "action" in policy
        assert "request" in policy

    def test_decision_policy_calls_authority_check(self, skill_path: Path) -> None:
        fm, _ = _skill_frontmatter(skill_path)
        policy = fm["decision_policy"]
        assert "authority_check(" in policy
        assert "role='engineering_duty_manager'" in policy or 'role="engineering_duty_manager"' in policy
        assert "category='synthetic-engineering-recovery'" in policy or 'category="synthetic-engineering-recovery"' in policy

    def test_decision_policy_sets_approve_and_escalate(self, skill_path: Path) -> None:
        fm, _ = _skill_frontmatter(skill_path)
        policy = fm["decision_policy"]
        assert '"approve"' in policy or "'approve'" in policy
        assert '"escalate"' in policy or "'escalate'" in policy

    def test_decision_policy_extra_copies_required_fields(self, skill_path: Path) -> None:
        fm, _ = _skill_frontmatter(skill_path)
        policy = fm["decision_policy"]
        for field in ("workflow_id", "story_id", "selected_option_id", "evidence_versions", "rationale"):
            assert field in policy

    def test_skill_does_not_certify_or_release(self, skill_path: Path) -> None:
        _, body = _skill_frontmatter(skill_path)
        lowered = body.lower()
        assert "certif" not in lowered
        assert "release" not in lowered
        assert "return-to-service" not in lowered or "outside" in lowered

    def test_persona_loader_can_load_and_compile_policy(self, skill_path: Path) -> None:
        """Decision policy must be valid Python that compiles without error."""
        fm, _ = _skill_frontmatter(skill_path)
        policy = fm["decision_policy"]
        compile(policy, "<engineering_duty_manager_decision_policy>", "exec")

    def test_valid_approve_context_approves_and_copies_extra(self, skill_path: Path) -> None:
        """Simulate an authority_check call that returns allowed=True."""
        fm, _ = _skill_frontmatter(skill_path)
        policy = fm["decision_policy"]

        allow_result = {
            "allowed": True,
            "governing_rule_id": "AUTH-engineering_duty_manager-engineering_duty_manager_decision",
            "reason": "within limit",
        }

        def authority_check(**kwargs: Any) -> dict[str, Any]:
            return allow_result

        context = {
            "action": "engineering_duty_manager_decision",
            "request": {"amount_gbp": 100_000.0, "category": "synthetic-engineering-recovery"},
            "workflow_id": "AOGA-0001",
            "story_id": "SYN-STORY-AOG-001",
            "decision_id": "SYN-AOG-DECISION-001",
            "selected_option_id": "AOG-WORK-LOCAL",
            "evidence_versions": {"SYN-TAIL-003": 1},
        }
        ns: dict[str, Any] = {"authority_check": authority_check, "context": context}
        exec(policy, ns)  # noqa: S102
        assert ns.get("decision") == "approve"
        assert ns.get("extra", {}).get("workflow_id") == "AOGA-0001"
        assert ns.get("extra", {}).get("story_id") == "SYN-STORY-AOG-001"
        assert ns.get("extra", {}).get("decision_id") == "SYN-AOG-DECISION-001"
        assert ns.get("extra", {}).get("selected_option_id") == "AOG-WORK-LOCAL"
        assert ns.get("extra", {}).get("evidence_versions") == {"SYN-TAIL-003": 1}
        assert "rationale" in ns.get("extra", {})

    def test_wrong_action_escalates(self, skill_path: Path) -> None:
        fm, _ = _skill_frontmatter(skill_path)
        policy = fm["decision_policy"]

        def authority_check(**kwargs: Any) -> dict[str, Any]:
            return {"allowed": False, "governing_rule_id": "n/a", "reason": "wrong action"}

        context = {
            "action": "wrong_action",
            "request": {"amount_gbp": 100_000.0, "category": "synthetic-engineering-recovery"},
        }
        ns: dict[str, Any] = {"authority_check": authority_check, "context": context}
        exec(policy, ns)  # noqa: S102
        assert ns.get("decision") in {"escalate", "reject"}

    def test_over_limit_does_not_approve(self, skill_path: Path) -> None:
        fm, _ = _skill_frontmatter(skill_path)
        policy = fm["decision_policy"]

        def authority_check(**kwargs: Any) -> dict[str, Any]:
            return {"allowed": False, "governing_rule_id": "AUTH-EDM", "reason": "exceeds limit"}

        context = {
            "action": "engineering_duty_manager_decision",
            "request": {"amount_gbp": 250_000.0, "category": "synthetic-engineering-recovery"},
        }
        ns: dict[str, Any] = {"authority_check": authority_check, "context": context}
        exec(policy, ns)  # noqa: S102
        assert ns.get("decision") != "approve"


# ===========================================================================
# 4. AOG MCP tools – strict schema and no mutation
# ===========================================================================

class TestAogMcpTools:
    def test_aog_tool_names_set(self) -> None:
        from verticals.airline.mcp_tools import aog
        assert aog.TOOL_NAMES == {
            "airline_read_aog_evidence",
            "airline_rank_admitted_aog_options",
        }

    @pytest.mark.asyncio
    async def test_read_aog_evidence_returns_source_mode_simulated(self) -> None:
        from verticals.airline.mcp_tools import aog
        result = await aog.airline_read_aog_evidence.handler(
            _invocation(
                "airline_read_aog_evidence",
                {
                    "observation": {
                        "story_id": "SYN-STORY-AOG-001",
                        "actor_ids": ["SYN-TAIL-003"],
                        "event_ids": ["evt-aog-001"],
                        "evidence_versions": {"SYN-TAIL-003": 1},
                    }
                },
            )
        )
        payload = json.loads(result.text_result_for_llm)
        assert result.result_type == "success"
        assert payload["source_mode"] == "simulated"
        assert payload["story_id"] == "SYN-STORY-AOG-001"
        assert "recommended_action" not in payload

    @pytest.mark.asyncio
    async def test_read_aog_evidence_preserves_observation_unchanged(self) -> None:
        from verticals.airline.mcp_tools import aog
        obs = {
            "story_id": "SYN-STORY-AOG-001",
            "actor_ids": ["SYN-TAIL-003", "SYN-TECH-003"],
            "event_ids": ["evt-aog-001", "evt-aog-002"],
            "evidence_versions": {"SYN-TAIL-003": 2, "SYN-TECH-003": 1},
            "evidence": {"aircraft": {"id": "SYN-TAIL-003", "status": "grounded"}},
        }
        before = copy.deepcopy(obs)
        result = await aog.airline_read_aog_evidence.handler(
            _invocation("airline_read_aog_evidence", {"observation": obs})
        )
        payload = json.loads(result.text_result_for_llm)
        assert obs == before  # no mutation
        assert payload == {"source_mode": "simulated", **before}

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "bad_obs",
        [
            # missing event_ids
            {"story_id": "SYN-STORY-AOG-001", "actor_ids": ["SYN-TAIL-003"], "evidence_versions": {"SYN-TAIL-003": 1}},
            # actor_ids not a list
            {"story_id": "SYN-STORY-AOG-001", "actor_ids": "SYN-TAIL-003", "event_ids": ["e1"], "evidence_versions": {"SYN-TAIL-003": 1}},
            # bool version
            {"story_id": "SYN-STORY-AOG-001", "actor_ids": ["SYN-TAIL-003"], "event_ids": ["e1"], "evidence_versions": {"SYN-TAIL-003": True}},
            # prohibited field
            {"story_id": "SYN-STORY-AOG-001", "actor_ids": ["SYN-TAIL-003"], "event_ids": ["e1"], "evidence_versions": {"SYN-TAIL-003": 1}, "recommended_action": "cancel"},
        ],
    )
    async def test_read_aog_evidence_rejects_bad_shapes(self, bad_obs: dict) -> None:
        from verticals.airline.mcp_tools import aog
        result = await aog.airline_read_aog_evidence.handler(
            _invocation("airline_read_aog_evidence", {"observation": bad_obs})
        )
        assert result.result_type == "failure"
        assert result.error
        assert "error" in result.text_result_for_llm.lower()

    @pytest.mark.asyncio
    async def test_rank_admitted_aog_options_returns_unchanged(self) -> None:
        from verticals.airline.mcp_tools import aog
        opts = _admitted_aog_options()
        ctx = {
            "story_id": "SYN-STORY-AOG-001",
            "ranking_dimensions": ["cost", "sector_protection", "lead_time"],
        }
        before_opts = copy.deepcopy(opts)
        before_ctx = copy.deepcopy(ctx)
        result = await aog.airline_rank_admitted_aog_options.handler(
            _invocation("airline_rank_admitted_aog_options", {
                "admitted_options": opts,
                "ranking_context": ctx,
            })
        )
        payload = json.loads(result.text_result_for_llm)
        assert result.result_type == "success"
        assert payload["source_mode"] == "simulated"
        assert payload["admitted_options"] == before_opts
        assert payload["ranking_context"] == before_ctx
        assert opts == before_opts  # no mutation
        assert ctx == before_ctx

    @pytest.mark.asyncio
    async def test_rank_admitted_aog_options_rejects_infeasible(self) -> None:
        from verticals.airline.mcp_tools import aog
        opts = _admitted_aog_options()
        opts[0]["feasible"] = False
        result = await aog.airline_rank_admitted_aog_options.handler(
            _invocation("airline_rank_admitted_aog_options", {
                "admitted_options": opts,
                "ranking_context": {},
            })
        )
        assert result.result_type == "failure"
        assert result.error
        assert "not admitted" in result.error.lower() or "infeasible" in result.error.lower() or "not admitted" in result.error

    @pytest.mark.asyncio
    async def test_rank_admitted_aog_options_rejects_unadmitted(self) -> None:
        from verticals.airline.mcp_tools import aog
        opts = _admitted_aog_options()
        opts[1]["admitted"] = False
        result = await aog.airline_rank_admitted_aog_options.handler(
            _invocation("airline_rank_admitted_aog_options", {
                "admitted_options": opts,
                "ranking_context": {},
            })
        )
        assert result.result_type == "failure"
        assert result.error

    @pytest.mark.asyncio
    async def test_rank_admitted_aog_options_rejects_duplicates(self) -> None:
        from verticals.airline.mcp_tools import aog
        opts = _admitted_aog_options()
        opts[1]["option_id"] = opts[0]["option_id"]
        result = await aog.airline_rank_admitted_aog_options.handler(
            _invocation("airline_rank_admitted_aog_options", {
                "admitted_options": opts,
                "ranking_context": {},
            })
        )
        assert result.result_type == "failure"
        assert result.error

    @pytest.mark.asyncio
    async def test_rank_admitted_aog_options_rejects_bad_version_map(self) -> None:
        from verticals.airline.mcp_tools import aog
        opts = _admitted_aog_options()
        opts[0]["evidence_versions"] = {"SYN-TAIL-003": 1.5}  # float, not int
        result = await aog.airline_rank_admitted_aog_options.handler(
            _invocation("airline_rank_admitted_aog_options", {
                "admitted_options": opts,
                "ranking_context": {},
            })
        )
        assert result.result_type == "failure"
        assert result.error

    @pytest.mark.asyncio
    async def test_rank_admitted_aog_options_rejects_empty_list(self) -> None:
        from verticals.airline.mcp_tools import aog
        result = await aog.airline_rank_admitted_aog_options.handler(
            _invocation("airline_rank_admitted_aog_options", {
                "admitted_options": [],
                "ranking_context": {},
            })
        )
        assert result.result_type == "failure"
        assert result.error


# ===========================================================================
# 5. AOG ranker skill frontmatter
# ===========================================================================

class TestAogRankerSkill:
    @pytest.fixture
    def skill_path(self) -> Path:
        return AIRLINE_ROOT / "skills" / "aog-recovery-ranker" / "SKILL.md"

    def test_skill_file_exists(self, skill_path: Path) -> None:
        assert skill_path.is_file()

    def test_frontmatter_allowed_tools_exact(self, skill_path: Path) -> None:
        from verticals.airline.mcp_tools import aog
        fm, _ = _skill_frontmatter(skill_path)
        declared = set(t.strip() for t in fm.get("allowed-tools", "").split(","))
        assert declared == aog.TOOL_NAMES

    def test_skill_body_requires_both_tools_before_response(self, skill_path: Path) -> None:
        _, body = _skill_frontmatter(skill_path)
        lowered = " ".join(body.lower().split())
        assert "airline_read_aog_evidence" in lowered
        assert "airline_rank_admitted_aog_options" in lowered

    def test_skill_body_surface_uncertainty(self, skill_path: Path) -> None:
        _, body = _skill_frontmatter(skill_path)
        lowered = " ".join(body.lower().split())
        assert "uncertainty" in lowered

    def test_skill_body_deterministic_validators_own_feasibility(self, skill_path: Path) -> None:
        _, body = _skill_frontmatter(skill_path)
        lowered = " ".join(body.lower().split())
        assert "feasibility" in lowered or "feasible" in lowered

    def test_skill_body_no_aircraft_release(self, skill_path: Path) -> None:
        _, body = _skill_frontmatter(skill_path)
        lowered = " ".join(body.lower().split())
        assert "return-to-service" not in lowered or "outside" in lowered
        assert "release" not in lowered or "cannot" in lowered


# ===========================================================================
# 6. AIRLINE_AGENTS – aog-recovery-ranker
# ===========================================================================

class TestAogRankerAgent:
    def test_agent_registered(self) -> None:
        from verticals.airline.agents import AIRLINE_AGENTS
        assert "aog-recovery-ranker" in AIRLINE_AGENTS

    def test_agent_allowed_tools_exact(self) -> None:
        from verticals.airline.agents import AIRLINE_AGENTS
        from verticals.airline.mcp_tools import aog
        entry = AIRLINE_AGENTS["aog-recovery-ranker"]
        assert set(entry.allowed_tools) == aog.TOOL_NAMES

    def test_agent_allowed_tools_matches_skill_frontmatter(self) -> None:
        from verticals.airline.agents import AIRLINE_AGENTS
        skill_path = AIRLINE_ROOT / "skills" / "aog-recovery-ranker" / "SKILL.md"
        fm, _ = _skill_frontmatter(skill_path)
        declared = set(t.strip() for t in fm["allowed-tools"].split(","))
        entry = AIRLINE_AGENTS["aog-recovery-ranker"]
        assert set(entry.allowed_tools) == declared

    def test_agent_reversible_only(self) -> None:
        from verticals.airline.agents import AIRLINE_AGENTS
        entry = AIRLINE_AGENTS["aog-recovery-ranker"]
        assert entry.reversible_only is True

    def test_agent_max_value_200k(self) -> None:
        from verticals.airline.agents import AIRLINE_AGENTS
        entry = AIRLINE_AGENTS["aog-recovery-ranker"]
        assert entry.max_value_gbp == 200_000.0

    def test_agent_scope_function_engineering(self) -> None:
        from verticals.airline.agents import AIRLINE_AGENTS
        entry = AIRLINE_AGENTS["aog-recovery-ranker"]
        assert entry.scope_function == "engineering-maintenance"

    def test_hero1_agents_preserved(self) -> None:
        from verticals.airline.agents import AIRLINE_AGENTS
        assert "network-impact-assessor" in AIRLINE_AGENTS
        assert "recovery-option-ranker" in AIRLINE_AGENTS


# ===========================================================================
# 7. Tool policy rows
# ===========================================================================

class TestAogToolPolicy:
    @pytest.fixture
    def policy(self) -> dict[str, Any]:
        import yaml
        path = AIRLINE_ROOT / "policies" / "tools.yaml"
        return yaml.safe_load(path.read_text(encoding="utf-8"))

    def _get_tool(self, policy: dict, tool_id: str) -> dict[str, Any] | None:
        return next((t for t in policy["tools"] if t["id"] == tool_id), None)

    def test_read_aog_evidence_policy_row_exists(self, policy: dict) -> None:
        assert self._get_tool(policy, "airline_read_aog_evidence") is not None

    def test_rank_admitted_aog_options_policy_row_exists(self, policy: dict) -> None:
        assert self._get_tool(policy, "airline_rank_admitted_aog_options") is not None

    def test_read_aog_evidence_reversible(self, policy: dict) -> None:
        row = self._get_tool(policy, "airline_read_aog_evidence")
        assert row is not None
        assert row.get("reversible") is True

    def test_rank_admitted_aog_options_reversible(self, policy: dict) -> None:
        row = self._get_tool(policy, "airline_rank_admitted_aog_options")
        assert row is not None
        assert row.get("reversible") is True

    def test_read_aog_evidence_no_authority_required(self, policy: dict) -> None:
        row = self._get_tool(policy, "airline_read_aog_evidence")
        assert row is not None
        assert not row.get("requires_authority")

    def test_rank_admitted_aog_options_no_authority_required(self, policy: dict) -> None:
        row = self._get_tool(policy, "airline_rank_admitted_aog_options")
        assert row is not None
        assert not row.get("requires_authority")

    def test_aog_tools_scope_engineering_maintenance(self, policy: dict) -> None:
        for tool_id in ("airline_read_aog_evidence", "airline_rank_admitted_aog_options"):
            row = self._get_tool(policy, tool_id)
            assert row is not None
            assert row.get("scope_function") == "engineering-maintenance"


# ===========================================================================
# 8. GovernanceKernel – real authority matrix
# ===========================================================================

def test_kernel_allows_200k_for_engineering_duty_manager(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # engineering_duty_manager_decision is a HITL event; the pack-synthesised
    # authority rule covers airline.commit_aog_recovery (the command action).
    from api.server.services.governance.kernel import GovernanceKernel
    from api.shared.vertical_loader import active_runtime
    monkeypatch.setenv("ZAVA_VERTICAL", "airline")
    monkeypatch.delenv("ZAVA_WORLD", raising=False)
    active_runtime.cache_clear()
    try:
        kernel = GovernanceKernel()
        result = kernel.check_authority(
            role="engineering_duty_manager",
            action="airline.commit_aog_recovery",
            category="synthetic-engineering-recovery",
            value=200_000.0,
        )
    finally:
        active_runtime.cache_clear()
    assert result.allowed is True


def test_kernel_denies_over_200k(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Same as above: use the command action not the HITL-event name.
    from api.server.services.governance.kernel import GovernanceKernel
    from api.shared.vertical_loader import active_runtime
    monkeypatch.setenv("ZAVA_VERTICAL", "airline")
    monkeypatch.delenv("ZAVA_WORLD", raising=False)
    active_runtime.cache_clear()
    try:
        kernel = GovernanceKernel()
        result = kernel.check_authority(
            role="engineering_duty_manager",
            action="airline.commit_aog_recovery",
            category="synthetic-engineering-recovery",
            value=200_001.0,
        )
    finally:
        active_runtime.cache_clear()
    assert result.allowed is False


# ===========================================================================
# 9. AOG command uses real authority row
# ===========================================================================

class TestAogCommandUsesRealAuthority:
    def test_value_over_authority_limit_rejected(self) -> None:
        """The AOG command gateway must fail closed when value exceeds authority."""
        from api.server.world.runtime import SimulationRuntime
        from verticals.airline.aog_constants import (
            AOG_SCENARIO_ID,
            AOG_WORKFLOW_ID,
        )
        from verticals.airline.aog_constraints import AOG_OPTION_WORK_LOCAL
        from verticals.airline.authority import AIRLINE_AUTHORITY
        from verticals.airline.worlds.scenario import AirlineWorld

        row = AIRLINE_AUTHORITY["engineering_duty_manager"]
        # Confirm the authority row drives the ceiling
        assert row.spend_limit_gbp == 200_000.0

        runtime = SimulationRuntime(seed=42)
        world = AirlineWorld(seed=42, runtime=runtime)
        world.install()
        world.activate_scenario(AOG_SCENARIO_ID)

        cmd = world.command_for_aog_option(
            option_id=AOG_OPTION_WORK_LOCAL,
            workflow_id=AOG_WORKFLOW_ID,
            decision_id="SYN-AOG-DECISION-001",
            persona="engineering_duty_manager",
        )
        # Tamper: set value above row limit
        payload = dict(cmd.payload)
        payload["value_gbp"] = 250_000.0
        from api.server.world.model import SimulationCommand
        tampered = SimulationCommand(
            command_id=cmd.command_id,
            trace_id=cmd.trace_id,
            issued_by=cmd.issued_by,
            type=cmd.type,
            payload=payload,
        )
        from verticals.airline.actions.aog_commands import apply_aog_recovery_command
        result = apply_aog_recovery_command(world, tampered)
        assert result.type == "command.rejected"

    def test_absent_authority_row_fails_closed(self) -> None:
        """If the authority row is missing the gateway must reject."""
        from api.server.world.runtime import SimulationRuntime
        from verticals.airline.aog_constants import AOG_SCENARIO_ID, AOG_WORKFLOW_ID
        from verticals.airline.aog_constraints import AOG_OPTION_WORK_LOCAL
        from verticals.airline.worlds.scenario import AirlineWorld

        runtime = SimulationRuntime(seed=42)
        world = AirlineWorld(seed=42, runtime=runtime)
        world.install()
        world.activate_scenario(AOG_SCENARIO_ID)

        cmd = world.command_for_aog_option(
            option_id=AOG_OPTION_WORK_LOCAL,
            workflow_id=AOG_WORKFLOW_ID,
            decision_id="SYN-AOG-DECISION-001",
            persona="engineering_duty_manager",
        )
        # Patch authority so the row is absent for the duration of this test
        from verticals.airline import authority as auth_module
        original = dict(auth_module.AIRLINE_AUTHORITY)
        try:
            # Replace with a dict missing the engineering_duty_manager key
            auth_module.AIRLINE_AUTHORITY = {
                k: v for k, v in original.items() if k != "engineering_duty_manager"
            }
            from verticals.airline.actions.aog_commands import apply_aog_recovery_command
            result = apply_aog_recovery_command(world, cmd)
            assert result.type == "command.rejected"
        finally:
            auth_module.AIRLINE_AUTHORITY = original  # type: ignore[assignment]


# ===========================================================================
# 10. validate_pack passes
# ===========================================================================

def test_validate_pack_airline_passes(tmp_path) -> None:
    from api.shared.vertical_loader import build_runtime, validate_pack
    runtime = build_runtime({"ZAVA_VERTICAL": "airline"}, data_root=tmp_path)
    validate_pack(runtime.pack)  # must not raise

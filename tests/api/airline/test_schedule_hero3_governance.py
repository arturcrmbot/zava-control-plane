"""Airline Hero 3 – Governance/Persona/Agent/MCP stage (TDD RED → GREEN).

Covers:
  1. AIRLINE_AUTHORITY – network_operations_director row (300k, exact actions)
  2. AIRLINE_PERSONAS – network_operations_director record
  3. Persona SKILL.md – decision_policy correctness
  4. MCP tools (mcp_tools/schedule.py) – schemas, purity, monitor preservation
  5. Agent – schedule-resilience-ranker, allowed tools, reversible, max 300k
  6. Tool policies – read-only, no authority, scope
  7. GovernanceKernel – real allow/deny under active airline pack
  8. Command gateway – real authority row, fail-closed
  9. Pack contract – all new symbols present, Hero1/AOG preserved
 10. validate_pack passes
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
# Helpers
# ---------------------------------------------------------------------------

def _skill_frontmatter(path: Path) -> tuple[dict[str, Any], str]:
    text = path.read_text(encoding="utf-8")
    match = re.fullmatch(r"---\n(.*?)\n---\n(.*)", text, flags=re.DOTALL)
    assert match is not None, f"Invalid SKILL.md format at {path}"
    return yaml.safe_load(match.group(1)), match.group(2)


def _invocation(tool_name: str, arguments: dict[str, Any]) -> ToolInvocation:
    return ToolInvocation(
        session_id="airline-schedule-test",
        tool_call_id=f"tool-{tool_name}",
        tool_name=tool_name,
        arguments=arguments,
    )


def _sched_observation() -> dict[str, Any]:
    return {
        "story_id": "SYN-STORY-SCHED-001",
        "risk_signal_id": "SYN-RISK-SCHED-001",
        "affected_sector_ids": ["SYN-SECTOR-OUT-003", "SYN-SECTOR-OUT-004"],
        "affected_slot_ids": ["SYN-SLOT-07", "SYN-SLOT-08"],
        "evidence_versions": {"SYN-RISK-SCHED-001": 1, "SYN-FCAST-SLOT-001": 2},
        "trace_id": "trace-sched-001",
    }


def _admitted_sched_options() -> list[dict[str, Any]]:
    return [
        {
            "option_id": "SCHED-BUFFER-RETIME",
            "feasible": True,
            "admitted": True,
            "actions": [{"action_type": "retime_sector", "sector_id": "SYN-SECTOR-OUT-003"}],
            "evidence_versions": {"SYN-RISK-SCHED-001": 1},
            "value_gbp": 45_000.0,
        },
        {
            "option_id": "SCHED-MONITOR-RISK",
            "feasible": True,
            "admitted": True,
            "actions": [{"action_type": "monitor_risk", "signal_id": "SYN-RISK-SCHED-001"}],
            "evidence_versions": {"SYN-RISK-SCHED-001": 1},
            "value_gbp": 0.0,
        },
    ]


def _ranking_context() -> dict[str, Any]:
    return {"workflow_id": "AIRSCHED-0001", "story_id": "SYN-STORY-SCHED-001"}


# ===========================================================================
# 1. AIRLINE_AUTHORITY – network_operations_director row
# ===========================================================================

class TestNetworkOperationsDirectorAuthority:
    def test_row_exists(self) -> None:
        from verticals.airline.authority import AIRLINE_AUTHORITY
        assert "network_operations_director" in AIRLINE_AUTHORITY

    def test_row_spend_limit_300k(self) -> None:
        from verticals.airline.authority import AIRLINE_AUTHORITY
        row = AIRLINE_AUTHORITY["network_operations_director"]
        assert row.spend_limit_gbp == 300_000.0

    def test_row_approval_actions_exact(self) -> None:
        from verticals.airline.authority import AIRLINE_AUTHORITY
        row = AIRLINE_AUTHORITY["network_operations_director"]
        assert set(row.approval_actions) == {
            "network_operations_director_decision",
            "airline.commit_schedule_adjustment",
        }

    def test_row_no_delegation(self) -> None:
        from verticals.airline.authority import AIRLINE_AUTHORITY
        row = AIRLINE_AUTHORITY["network_operations_director"]
        assert row.delegate_to is None

    def test_hero1_authority_preserved(self) -> None:
        from verticals.airline.authority import AIRLINE_AUTHORITY
        row = AIRLINE_AUTHORITY["duty_operations_manager"]
        assert row.spend_limit_gbp == 150_000.0
        assert "duty_operations_manager_decision" in row.approval_actions
        assert "airline.commit_recovery_plan" in row.approval_actions

    def test_aog_authority_preserved(self) -> None:
        from verticals.airline.authority import AIRLINE_AUTHORITY
        row = AIRLINE_AUTHORITY["engineering_duty_manager"]
        assert row.spend_limit_gbp == 200_000.0
        assert "airline.commit_aog_recovery" in row.approval_actions


# ===========================================================================
# 2. AIRLINE_PERSONAS – network_operations_director record
# ===========================================================================

class TestNetworkOperationsDirectorPersona:
    def test_persona_exists(self) -> None:
        from verticals.airline.personas import AIRLINE_PERSONAS
        assert "network_operations_director" in AIRLINE_PERSONAS

    def test_persona_archetype_approver(self) -> None:
        from verticals.airline.personas import AIRLINE_PERSONAS
        p = AIRLINE_PERSONAS["network_operations_director"]
        assert p.archetype == "approver"

    def test_persona_scope_function_commercial(self) -> None:
        from verticals.airline.personas import AIRLINE_PERSONAS
        p = AIRLINE_PERSONAS["network_operations_director"]
        assert p.scope_function == "commercial"

    def test_persona_external_event(self) -> None:
        from verticals.airline.personas import AIRLINE_PERSONAS
        p = AIRLINE_PERSONAS["network_operations_director"]
        assert p.external_event_default == "network_operations_director_decision"

    def test_persona_uses_authority_mcp(self) -> None:
        from verticals.airline.personas import AIRLINE_PERSONAS
        p = AIRLINE_PERSONAS["network_operations_director"]
        assert p.uses_authority_mcp is True

    def test_persona_description_mentions_synthetic(self) -> None:
        from verticals.airline.personas import AIRLINE_PERSONAS
        p = AIRLINE_PERSONAS["network_operations_director"]
        assert "synthetic" in p.description.lower()

    def test_persona_description_no_safety_or_legality_override(self) -> None:
        from verticals.airline.personas import AIRLINE_PERSONAS
        p = AIRLINE_PERSONAS["network_operations_director"]
        lowered = p.description.lower()
        # description must NOT claim safety/legality waiver authority
        assert "override safety" not in lowered
        assert "override legal" not in lowered

    def test_persona_display_color_distinct(self) -> None:
        from verticals.airline.personas import AIRLINE_PERSONAS
        nod = AIRLINE_PERSONAS["network_operations_director"]
        dom = AIRLINE_PERSONAS["duty_operations_manager"]
        edm = AIRLINE_PERSONAS["engineering_duty_manager"]
        assert nod.display_color is not None
        assert nod.display_color != dom.display_color
        assert nod.display_color != edm.display_color

    def test_hero1_persona_preserved(self) -> None:
        from verticals.airline.personas import AIRLINE_PERSONAS
        p = AIRLINE_PERSONAS["duty_operations_manager"]
        assert p.scope_function == "commercial"
        assert p.external_event_default == "duty_operations_manager_decision"

    def test_aog_persona_preserved(self) -> None:
        from verticals.airline.personas import AIRLINE_PERSONAS
        p = AIRLINE_PERSONAS["engineering_duty_manager"]
        assert p.scope_function == "it"
        assert p.external_event_default == "engineering_duty_manager_decision"


# ===========================================================================
# 3. Persona SKILL.md – network_operations_director
# ===========================================================================

class TestNetworkOperationsDirectorSkill:
    @pytest.fixture
    def skill_path(self) -> Path:
        return AIRLINE_ROOT / "personae" / "network_operations_director" / "SKILL.md"

    def test_skill_file_exists(self, skill_path: Path) -> None:
        assert skill_path.is_file()

    def test_frontmatter_keys(self, skill_path: Path) -> None:
        fm, _ = _skill_frontmatter(skill_path)
        assert "name" in fm
        assert "description" in fm
        assert "external_event" in fm
        assert "decision_policy" in fm
        assert "allowed-tools" not in fm  # persona uses no tools

    def test_frontmatter_external_event(self, skill_path: Path) -> None:
        fm, _ = _skill_frontmatter(skill_path)
        assert fm["external_event"] == "network_operations_director_decision"

    def test_decision_policy_reads_action_and_request(self, skill_path: Path) -> None:
        fm, _ = _skill_frontmatter(skill_path)
        policy = fm["decision_policy"]
        assert "action" in policy
        assert "request" in policy

    def test_decision_policy_calls_authority_check_with_correct_role_action_category(
        self, skill_path: Path
    ) -> None:
        fm, _ = _skill_frontmatter(skill_path)
        policy = fm["decision_policy"]
        assert "authority_check(" in policy
        assert (
            "role='network_operations_director'" in policy
            or 'role="network_operations_director"' in policy
        )
        assert (
            "category='synthetic-schedule-resilience'" in policy
            or 'category="synthetic-schedule-resilience"' in policy
        )

    def test_decision_policy_approve_and_escalate(self, skill_path: Path) -> None:
        fm, _ = _skill_frontmatter(skill_path)
        policy = fm["decision_policy"]
        assert "'approve'" in policy or '"approve"' in policy
        assert "'escalate'" in policy or '"escalate"' in policy

    def test_decision_policy_extra_copies_workflow_story_option_evidence_rationale(
        self, skill_path: Path
    ) -> None:
        fm, _ = _skill_frontmatter(skill_path)
        policy = fm["decision_policy"]
        for field in ("workflow_id", "story_id", "selected_option", "evidence_versions", "rationale"):
            assert field in policy, f"missing field {field!r} in decision_policy extra"

    def test_skill_body_mentions_synthetic_no_safety_legality_override(
        self, skill_path: Path
    ) -> None:
        _, body = _skill_frontmatter(skill_path)
        lowered = body.lower()
        assert "synthetic" in lowered
        assert "safety" not in lowered or "waive" not in lowered

    def test_persona_loader_compiles_policy(self, skill_path: Path) -> None:
        fm, _ = _skill_frontmatter(skill_path)
        policy = fm["decision_policy"]
        compile(policy, "<network_operations_director_decision_policy>", "exec")

    def test_valid_approve_context_approves_and_copies_extra(self, skill_path: Path) -> None:
        fm, _ = _skill_frontmatter(skill_path)
        policy = fm["decision_policy"]

        allow_result = {
            "allowed": True,
            "governing_rule_id": "AUTH-NOD-network_operations_director_decision",
            "reason": "within limit",
        }

        def authority_check(**kwargs: Any) -> dict[str, Any]:
            return allow_result

        context = {
            "action": "network_operations_director_decision",
            "request": {
                "amount_gbp": 45_000.0,
                "category": "synthetic-schedule-resilience",
            },
            "workflow_id": "AIRSCHED-0001",
            "story_id": "SYN-STORY-SCHED-001",
            "selected_option_id": "SCHED-BUFFER-RETIME",
            "evidence_versions": {"SYN-RISK-SCHED-001": 1},
        }
        ns: dict[str, Any] = {"authority_check": authority_check, "context": context}
        exec(policy, ns)  # noqa: S102
        assert ns.get("decision") == "approve"
        extra = ns.get("extra", {})
        assert extra.get("workflow_id") == "AIRSCHED-0001"
        assert extra.get("story_id") == "SYN-STORY-SCHED-001"
        assert "rationale" in extra

    def test_over_limit_does_not_approve(self, skill_path: Path) -> None:
        fm, _ = _skill_frontmatter(skill_path)
        policy = fm["decision_policy"]

        def authority_check(**kwargs: Any) -> dict[str, Any]:
            return {"allowed": False, "governing_rule_id": "AUTH-NOD", "reason": "exceeds limit"}

        context = {
            "action": "network_operations_director_decision",
            "request": {"amount_gbp": 400_000.0, "category": "synthetic-schedule-resilience"},
        }
        ns: dict[str, Any] = {"authority_check": authority_check, "context": context}
        exec(policy, ns)  # noqa: S102
        assert ns.get("decision") != "approve"

    def test_wrong_action_escalates_or_rejects(self, skill_path: Path) -> None:
        fm, _ = _skill_frontmatter(skill_path)
        policy = fm["decision_policy"]

        def authority_check(**kwargs: Any) -> dict[str, Any]:
            return {"allowed": False, "governing_rule_id": "n/a", "reason": "wrong action"}

        context = {
            "action": "wrong_action",
            "request": {"amount_gbp": 45_000.0, "category": "synthetic-schedule-resilience"},
        }
        ns: dict[str, Any] = {"authority_check": authority_check, "context": context}
        exec(policy, ns)  # noqa: S102
        assert ns.get("decision") in {"escalate", "reject"}

    def test_monitor_risk_treated_as_real_governed_decision(self, skill_path: Path) -> None:
        """monitor_risk must go through authority_check like any other option."""
        fm, _ = _skill_frontmatter(skill_path)
        policy = fm["decision_policy"]
        called: list[dict] = []

        def authority_check(**kwargs: Any) -> dict[str, Any]:
            called.append(kwargs)
            return {"allowed": True, "governing_rule_id": "AUTH-NOD", "reason": "ok"}

        context = {
            "action": "network_operations_director_decision",
            "request": {"amount_gbp": 0.0, "category": "synthetic-schedule-resilience"},
            "workflow_id": "AIRSCHED-0001",
            "story_id": "SYN-STORY-SCHED-001",
            "selected_option_id": "SCHED-MONITOR-RISK",
            "evidence_versions": {"SYN-RISK-SCHED-001": 1},
        }
        ns: dict[str, Any] = {"authority_check": authority_check, "context": context}
        exec(policy, ns)  # noqa: S102
        # authority_check must have been called
        assert len(called) >= 1


# ===========================================================================
# 4. MCP tools – mcp_tools/schedule.py
# ===========================================================================

class TestScheduleMcpToolNames:
    def test_tool_names_set(self) -> None:
        from verticals.airline.mcp_tools import schedule
        assert schedule.TOOL_NAMES == {
            "airline_read_schedule_risk_evidence",
            "airline_rank_admitted_resilience_options",
        }


class TestReadScheduleRiskEvidence:
    async def _call(self, observation: dict[str, Any]) -> dict[str, Any]:
        from verticals.airline.mcp_tools import schedule
        inv = _invocation("airline_read_schedule_risk_evidence", {"observation": observation})
        result = await schedule.airline_read_schedule_risk_evidence.handler(inv)
        if result.result_type == "failure":
            raise ValueError(result.text_result_for_llm)
        return json.loads(result.text_result_for_llm)

    @pytest.mark.asyncio
    async def test_returns_source_mode_simulated(self) -> None:
        result = await self._call(_sched_observation())
        assert result["source_mode"] == "simulated"

    @pytest.mark.asyncio
    async def test_observation_fields_preserved(self) -> None:
        obs = _sched_observation()
        result = await self._call(obs)
        assert result["story_id"] == obs["story_id"]
        assert result["risk_signal_id"] == obs["risk_signal_id"]
        assert result["evidence_versions"] == obs["evidence_versions"]

    @pytest.mark.asyncio
    async def test_malformed_observation_rejected(self) -> None:
        from verticals.airline.mcp_tools import schedule
        inv = _invocation("airline_read_schedule_risk_evidence", {"observation": {"story_id": ""}})
        result = await schedule.airline_read_schedule_risk_evidence.handler(inv)
        assert result.result_type == "failure"

    @pytest.mark.asyncio
    async def test_empty_evidence_versions_rejected(self) -> None:
        from verticals.airline.mcp_tools import schedule
        obs = _sched_observation()
        obs["evidence_versions"] = {}
        inv = _invocation("airline_read_schedule_risk_evidence", {"observation": obs})
        result = await schedule.airline_read_schedule_risk_evidence.handler(inv)
        assert result.result_type == "failure"

    def test_no_network_no_mutation(self) -> None:
        """Tool must not import socket, requests, or mutate world state."""
        import inspect
        from verticals.airline.mcp_tools import schedule
        source = inspect.getsource(schedule)
        assert "import socket" not in source
        assert "import requests" not in source
        assert "import httpx" not in source


class TestRankAdmittedResilienceOptions:
    async def _call(
        self,
        admitted_options: list[dict[str, Any]],
        ranking_context: dict[str, Any],
    ) -> dict[str, Any]:
        from verticals.airline.mcp_tools import schedule
        inv = _invocation(
            "airline_rank_admitted_resilience_options",
            {
                "admitted_options": admitted_options,
                "ranking_context": ranking_context,
            },
        )
        result = await schedule.airline_rank_admitted_resilience_options.handler(inv)
        if result.result_type == "failure":
            raise ValueError(result.text_result_for_llm)
        return json.loads(result.text_result_for_llm)

    @pytest.mark.asyncio
    async def test_returns_source_mode_simulated(self) -> None:
        result = await self._call(_admitted_sched_options(), _ranking_context())
        assert result["source_mode"] == "simulated"

    @pytest.mark.asyncio
    async def test_options_returned_unchanged(self) -> None:
        opts = _admitted_sched_options()
        result = await self._call(opts, _ranking_context())
        assert result["admitted_options"] == opts

    @pytest.mark.asyncio
    async def test_ranking_context_preserved(self) -> None:
        ctx = _ranking_context()
        result = await self._call(_admitted_sched_options(), ctx)
        assert result["ranking_context"] == ctx

    @pytest.mark.asyncio
    async def test_monitor_risk_preserved(self) -> None:
        opts = _admitted_sched_options()
        monitor_ids = [o["option_id"] for o in opts if "monitor" in o["option_id"].lower()]
        assert monitor_ids, "test fixture must include a monitor_risk option"
        result = await self._call(opts, _ranking_context())
        returned_ids = [o["option_id"] for o in result["admitted_options"]]
        for mid in monitor_ids:
            assert mid in returned_ids

    @pytest.mark.asyncio
    async def test_infeasible_option_rejected(self) -> None:
        from verticals.airline.mcp_tools import schedule
        opts = copy.deepcopy(_admitted_sched_options())
        opts[0]["feasible"] = False
        inv = _invocation(
            "airline_rank_admitted_resilience_options",
            {"admitted_options": opts, "ranking_context": _ranking_context()},
        )
        result = await schedule.airline_rank_admitted_resilience_options.handler(inv)
        assert result.result_type == "failure"

    @pytest.mark.asyncio
    async def test_unadmitted_option_rejected(self) -> None:
        from verticals.airline.mcp_tools import schedule
        opts = copy.deepcopy(_admitted_sched_options())
        opts[0]["admitted"] = False
        inv = _invocation(
            "airline_rank_admitted_resilience_options",
            {"admitted_options": opts, "ranking_context": _ranking_context()},
        )
        result = await schedule.airline_rank_admitted_resilience_options.handler(inv)
        assert result.result_type == "failure"

    @pytest.mark.asyncio
    async def test_duplicate_option_ids_rejected(self) -> None:
        from verticals.airline.mcp_tools import schedule
        opts = _admitted_sched_options()
        opts_dup = [opts[0], copy.deepcopy(opts[0])]
        inv = _invocation(
            "airline_rank_admitted_resilience_options",
            {"admitted_options": opts_dup, "ranking_context": _ranking_context()},
        )
        result = await schedule.airline_rank_admitted_resilience_options.handler(inv)
        assert result.result_type == "failure"

    @pytest.mark.asyncio
    async def test_missing_option_id_rejected(self) -> None:
        from verticals.airline.mcp_tools import schedule
        opts = copy.deepcopy(_admitted_sched_options())
        del opts[0]["option_id"]
        inv = _invocation(
            "airline_rank_admitted_resilience_options",
            {"admitted_options": opts, "ranking_context": _ranking_context()},
        )
        result = await schedule.airline_rank_admitted_resilience_options.handler(inv)
        assert result.result_type == "failure"

    @pytest.mark.asyncio
    async def test_missing_evidence_versions_rejected(self) -> None:
        from verticals.airline.mcp_tools import schedule
        opts = copy.deepcopy(_admitted_sched_options())
        del opts[0]["evidence_versions"]
        inv = _invocation(
            "airline_rank_admitted_resilience_options",
            {"admitted_options": opts, "ranking_context": _ranking_context()},
        )
        result = await schedule.airline_rank_admitted_resilience_options.handler(inv)
        assert result.result_type == "failure"

    @pytest.mark.asyncio
    async def test_empty_admitted_options_rejected(self) -> None:
        from verticals.airline.mcp_tools import schedule
        inv = _invocation(
            "airline_rank_admitted_resilience_options",
            {"admitted_options": [], "ranking_context": _ranking_context()},
        )
        result = await schedule.airline_rank_admitted_resilience_options.handler(inv)
        assert result.result_type == "failure"


# ===========================================================================
# 5. Agent – schedule-resilience-ranker
# ===========================================================================

class TestScheduleResilienceRankerAgent:
    def test_agent_exists(self) -> None:
        from verticals.airline.agents import AIRLINE_AGENTS
        assert "schedule-resilience-ranker" in AIRLINE_AGENTS

    def test_agent_allowed_tools_exact(self) -> None:
        from verticals.airline.agents import AIRLINE_AGENTS
        agent = AIRLINE_AGENTS["schedule-resilience-ranker"]
        assert set(agent.allowed_tools) == {
            "airline_read_schedule_risk_evidence",
            "airline_rank_admitted_resilience_options",
        }

    def test_agent_reversible_only(self) -> None:
        from verticals.airline.agents import AIRLINE_AGENTS
        agent = AIRLINE_AGENTS["schedule-resilience-ranker"]
        assert agent.reversible_only is True

    def test_agent_max_value_300k(self) -> None:
        from verticals.airline.agents import AIRLINE_AGENTS
        agent = AIRLINE_AGENTS["schedule-resilience-ranker"]
        assert agent.max_value_gbp == 300_000.0

    def test_agent_scope_function_network_planning(self) -> None:
        from verticals.airline.agents import AIRLINE_AGENTS
        agent = AIRLINE_AGENTS["schedule-resilience-ranker"]
        assert agent.scope_function == "network-planning"

    def test_hero1_aog_agents_preserved(self) -> None:
        from verticals.airline.agents import AIRLINE_AGENTS
        assert "network-impact-assessor" in AIRLINE_AGENTS
        assert "recovery-option-ranker" in AIRLINE_AGENTS
        assert "aog-recovery-ranker" in AIRLINE_AGENTS


# ===========================================================================
# 6. Skill SKILL.md – schedule-resilience-ranker
# ===========================================================================

class TestScheduleResilienceRankerSkill:
    @pytest.fixture
    def skill_path(self) -> Path:
        return AIRLINE_ROOT / "skills" / "schedule-resilience-ranker" / "SKILL.md"

    def test_skill_file_exists(self, skill_path: Path) -> None:
        assert skill_path.is_file()

    def test_frontmatter_allowed_tools_exact(self, skill_path: Path) -> None:
        fm, _ = _skill_frontmatter(skill_path)
        raw = fm["allowed-tools"]
        if isinstance(raw, str):
            tools = {t.strip() for t in raw.split(",")}
        else:
            tools = set(raw)
        assert tools == {
            "airline_read_schedule_risk_evidence",
            "airline_rank_admitted_resilience_options",
        }

    def test_skill_body_requires_both_real_calls(self, skill_path: Path) -> None:
        _, body = _skill_frontmatter(skill_path)
        assert "airline_read_schedule_risk_evidence" in body
        assert "airline_rank_admitted_resilience_options" in body

    def test_skill_body_ranks_every_admitted_id_including_monitor_risk(
        self, skill_path: Path
    ) -> None:
        _, body = _skill_frontmatter(skill_path)
        lowered = body.lower()
        assert "monitor_risk" in lowered or "monitor risk" in lowered

    def test_skill_body_preserves_no_action_comparison(self, skill_path: Path) -> None:
        _, body = _skill_frontmatter(skill_path)
        lowered = body.lower()
        assert "no-action" in lowered or "no action" in lowered

    def test_skill_body_deterministic_feasibility_ownership(self, skill_path: Path) -> None:
        _, body = _skill_frontmatter(skill_path)
        lowered = body.lower()
        assert "deterministic" in lowered or "feasibility" in lowered


# ===========================================================================
# 7. Tool policies – schedule tools
# ===========================================================================

class TestScheduleToolPolicies:
    @pytest.fixture
    def tools(self) -> list[dict[str, Any]]:
        policy_path = AIRLINE_ROOT / "policies" / "tools.yaml"
        raw = yaml.safe_load(policy_path.read_text())
        return {t["id"]: t for t in raw["tools"]}

    def test_read_evidence_policy_exists(self, tools: dict) -> None:
        assert "airline_read_schedule_risk_evidence" in tools

    def test_rank_options_policy_exists(self, tools: dict) -> None:
        assert "airline_rank_admitted_resilience_options" in tools

    def test_read_evidence_reversible(self, tools: dict) -> None:
        assert tools["airline_read_schedule_risk_evidence"]["reversible"] is True

    def test_rank_options_reversible(self, tools: dict) -> None:
        assert tools["airline_rank_admitted_resilience_options"]["reversible"] is True

    def test_read_evidence_no_authority(self, tools: dict) -> None:
        assert tools["airline_read_schedule_risk_evidence"].get("requires_authority") is False

    def test_rank_options_no_authority(self, tools: dict) -> None:
        assert tools["airline_rank_admitted_resilience_options"].get("requires_authority") is False

    def test_read_evidence_scope(self, tools: dict) -> None:
        assert tools["airline_read_schedule_risk_evidence"].get("scope_function") == "network-planning"

    def test_rank_options_scope(self, tools: dict) -> None:
        assert tools["airline_rank_admitted_resilience_options"].get("scope_function") == "network-planning"


# ===========================================================================
# 8. GovernanceKernel – real allow/deny under active Airline pack
# ===========================================================================

def test_kernel_allows_300k_for_network_operations_director(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from api.server.services.governance.kernel import GovernanceKernel
    from api.shared.vertical_loader import active_runtime
    monkeypatch.setenv("ZAVA_VERTICAL", "airline")
    monkeypatch.delenv("ZAVA_WORLD", raising=False)
    active_runtime.cache_clear()
    try:
        kernel = GovernanceKernel()
        result = kernel.check_authority(
            role="network_operations_director",
            action="airline.commit_schedule_adjustment",
            category="synthetic-schedule-resilience",
            value=300_000.0,
        )
    finally:
        active_runtime.cache_clear()
    assert result.allowed is True


def test_kernel_denies_over_300k(monkeypatch: pytest.MonkeyPatch) -> None:
    from api.server.services.governance.kernel import GovernanceKernel
    from api.shared.vertical_loader import active_runtime
    monkeypatch.setenv("ZAVA_VERTICAL", "airline")
    monkeypatch.delenv("ZAVA_WORLD", raising=False)
    active_runtime.cache_clear()
    try:
        kernel = GovernanceKernel()
        result = kernel.check_authority(
            role="network_operations_director",
            action="airline.commit_schedule_adjustment",
            category="synthetic-schedule-resilience",
            value=300_001.0,
        )
    finally:
        active_runtime.cache_clear()
    assert result.allowed is False


# ===========================================================================
# 9. Command gateway – real authority row, fail-closed
# ===========================================================================

class TestScheduleCommandUsesRealAuthority:
    def _world_with_scenario(self):
        from api.server.world.runtime import SimulationRuntime
        from verticals.airline.schedule_constants import SCHED_SCENARIO_ID
        from verticals.airline.worlds.scenario import AirlineWorld
        runtime = SimulationRuntime(seed=42)
        world = AirlineWorld(seed=42, runtime=runtime)
        world.install()
        world.activate_scenario(SCHED_SCENARIO_ID)
        return runtime, world

    def test_real_authority_row_drives_ceiling(self) -> None:
        from verticals.airline.authority import AIRLINE_AUTHORITY
        row = AIRLINE_AUTHORITY["network_operations_director"]
        assert row.spend_limit_gbp == 300_000.0

    def test_value_over_authority_limit_rejected(self) -> None:
        from api.server.world.model import SimulationCommand
        from verticals.airline.actions.schedule_commands import apply_schedule_adjustment_command
        from verticals.airline.schedule_constants import (
            SCHED_WORKFLOW_ID,
            SCHED_DECISION_ID,
        )
        from verticals.airline.schedule_constraints import SCHED_OPTION_BUFFER_RETIME

        runtime, world = self._world_with_scenario()
        cmd = world.command_for_schedule_option(
            option_id=SCHED_OPTION_BUFFER_RETIME,
            workflow_id=SCHED_WORKFLOW_ID,
            decision_id=SCHED_DECISION_ID,
            persona="network_operations_director",
        )
        payload = dict(cmd.payload)
        payload["value_gbp"] = 400_000.0
        tampered = SimulationCommand(
            command_id=cmd.command_id,
            trace_id=cmd.trace_id,
            issued_by=cmd.issued_by,
            type=cmd.type,
            payload=payload,
        )
        result = apply_schedule_adjustment_command(world, tampered)
        assert result.type == "command.rejected"

    def test_absent_authority_row_fails_closed(self) -> None:
        from api.server.world.model import SimulationCommand
        from verticals.airline.actions.schedule_commands import apply_schedule_adjustment_command
        from verticals.airline.schedule_constants import (
            SCHED_WORKFLOW_ID,
            SCHED_DECISION_ID,
        )
        from verticals.airline.schedule_constraints import SCHED_OPTION_BUFFER_RETIME
        import verticals.airline.authority as auth_module

        runtime, world = self._world_with_scenario()
        cmd = world.command_for_schedule_option(
            option_id=SCHED_OPTION_BUFFER_RETIME,
            workflow_id=SCHED_WORKFLOW_ID,
            decision_id=SCHED_DECISION_ID,
            persona="network_operations_director",
        )

        original = dict(auth_module.AIRLINE_AUTHORITY)
        stripped = {k: v for k, v in original.items() if k != "network_operations_director"}
        auth_module.AIRLINE_AUTHORITY = stripped  # type: ignore[assignment]
        try:
            result = apply_schedule_adjustment_command(world, cmd)
        finally:
            auth_module.AIRLINE_AUTHORITY = original  # type: ignore[assignment]
        assert result.type == "command.rejected"

    def test_wrong_action_in_authority_row_fails_closed(self) -> None:
        from api.server.world.model import SimulationCommand
        from api.shared.authority_contracts import AuthorityRow
        from verticals.airline.actions.schedule_commands import apply_schedule_adjustment_command
        from verticals.airline.schedule_constants import (
            SCHED_WORKFLOW_ID,
            SCHED_DECISION_ID,
        )
        from verticals.airline.schedule_constraints import SCHED_OPTION_BUFFER_RETIME
        import verticals.airline.authority as auth_module

        runtime, world = self._world_with_scenario()
        cmd = world.command_for_schedule_option(
            option_id=SCHED_OPTION_BUFFER_RETIME,
            workflow_id=SCHED_WORKFLOW_ID,
            decision_id=SCHED_DECISION_ID,
            persona="network_operations_director",
        )

        original = dict(auth_module.AIRLINE_AUTHORITY)
        patched = AuthorityRow(
            role="network_operations_director",
            spend_limit_gbp=300_000.0,
            approval_actions=("network_operations_director_decision",),  # missing command action
            delegate_to=None,
        )
        auth_module.AIRLINE_AUTHORITY = {**original, "network_operations_director": patched}  # type: ignore[assignment]
        try:
            result = apply_schedule_adjustment_command(world, cmd)
        finally:
            auth_module.AIRLINE_AUTHORITY = original  # type: ignore[assignment]
        assert result.type == "command.rejected"


# ===========================================================================
# 10. Pack contract – all new symbols present, Hero1/AOG preserved
# ===========================================================================

class TestPackContract:
    def test_agents_include_schedule_ranker(self) -> None:
        from verticals.airline.agents import AIRLINE_AGENTS
        assert "schedule-resilience-ranker" in AIRLINE_AGENTS

    def test_agents_include_all_expected(self) -> None:
        from verticals.airline.agents import AIRLINE_AGENTS
        assert set(AIRLINE_AGENTS) >= {
            "network-impact-assessor",
            "recovery-option-ranker",
            "aog-recovery-ranker",
            "schedule-resilience-ranker",
        }

    def test_personas_include_all_three(self) -> None:
        from verticals.airline.personas import AIRLINE_PERSONAS
        assert set(AIRLINE_PERSONAS) >= {
            "duty_operations_manager",
            "engineering_duty_manager",
            "network_operations_director",
        }

    def test_authority_includes_all_three(self) -> None:
        from verticals.airline.authority import AIRLINE_AUTHORITY
        assert set(AIRLINE_AUTHORITY) >= {
            "duty_operations_manager",
            "engineering_duty_manager",
            "network_operations_director",
        }

    def test_manifest_registers_schedule_mcp_module(self) -> None:
        from verticals.airline.manifest import build_pack
        pack = build_pack()
        assert "verticals.airline.mcp_tools.schedule" in pack.mcp_modules

    def test_manifest_still_has_operations_and_aog_modules(self) -> None:
        from verticals.airline.manifest import build_pack
        pack = build_pack()
        assert "verticals.airline.mcp_tools.operations" in pack.mcp_modules
        assert "verticals.airline.mcp_tools.aog" in pack.mcp_modules


# ===========================================================================
# 11. validate_pack passes
# ===========================================================================

def test_validate_pack_airline_passes(tmp_path) -> None:
    from api.shared.vertical_loader import build_runtime, validate_pack
    runtime = build_runtime({"ZAVA_VERTICAL": "airline"}, data_root=tmp_path)
    validate_pack(runtime.pack)  # must not raise

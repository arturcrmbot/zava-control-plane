from pathlib import Path

ROOT = Path(__file__).resolve().parents[5]
ADD_DOMAIN = ROOT / ".github" / "skills" / "add-domain" / "SKILL.md"
COMPOSE_SKILL = (
    ROOT / "docs" / "superpowers" / "skills" / "compose-domain" / "SKILL.md"
)
COMPOSE_CHECKLIST = (
    ROOT / "docs" / "superpowers" / "skills" / "compose-domain" / "CHECKLIST.md"
)
COMPOSE_LIVE = ROOT / ".github" / "skills" / "compose-domain-live" / "SKILL.md"
VERTICAL_PROOF = ROOT / "docs" / "VERTICAL-PROOF.md"
BUILD_CONTRACT = (
    ROOT / "docs" / "superpowers" / "contracts" / "VERTICAL-BUILD-CONTRACT.md"
)
AUTHOR_DURABLE = (
    ROOT / "docs" / "superpowers" / "skills" / "author-durable-domain" / "SKILL.md"
)


def test_new_vertical_process_requires_hitl_authority_and_recovery_proof():
    add_domain = ADD_DOMAIN.read_text(encoding="utf-8")
    checklist = COMPOSE_CHECKLIST.read_text(encoding="utf-8")
    proof = VERTICAL_PROOF.read_text(encoding="utf-8")

    assert "authority matrix" in add_domain.lower()
    assert "hitl_context" in checklist
    assert "PERSONA_AUTO_CLOSE=*" in checklist
    assert "latest_seq" in checklist
    assert "click-to-first-visible" in proof.lower()
    assert "backend restart" in proof.lower()


def test_domain_building_docs_require_self_consistent_execution_evidence():
    for path in (ADD_DOMAIN, COMPOSE_SKILL, COMPOSE_CHECKLIST, COMPOSE_LIVE, VERTICAL_PROOF):
        text = path.read_text(encoding="utf-8")
        normalized = " ".join(text.split())
        lower = normalized.lower()

        assert "actual execution evidence must be visible and self-consistent" in lower, path
        assert "every active non-stub workflow type" in lower, path
        assert "run_agent_session" in normalized, path
        assert "tools/workflow_visibility_proof.py" in normalized, path

    for path in (COMPOSE_CHECKLIST, VERTICAL_PROOF):
        lower = " ".join(path.read_text(encoding="utf-8").split()).lower()
        for obsolete_claim in (
            "covered declared phases",
            "executed prefix through",
            "tool-required workflow",
            "matches the gate persona",
            "phase sequence/names matches",
        ):
            assert obsolete_claim not in lower, (path, obsolete_claim)


def test_execution_visibility_proof_has_executable_api_checks():
    for path in (COMPOSE_CHECKLIST, VERTICAL_PROOF):
        text = path.read_text(encoding="utf-8")
        for command_shape in (
            "tools/workflow_visibility_proof.py",
            "--vertical <vertical>",
            "--base-url http://localhost:3101",
            "--save-dir proof/workflow-details/live",
            "--compare-dir proof/workflow-details/live",
            "--save-dir proof/workflow-details/replay",
        ):
            assert command_shape in text, (path, command_shape)
        assert "$detail" not in text, path
        assert "replay_detail=" not in text, path


def test_builder_skills_share_one_current_contract():
    assert BUILD_CONTRACT.exists()
    build_contract = BUILD_CONTRACT.read_text(encoding="utf-8")
    assert "**Contract version:** `1.0.0`" in build_contract
    assert "code-first" in build_contract
    assert all(
        term in build_contract
        for term in ("Reuse", "Extend", "Bespoke", "build ready", "demo ready")
    )

    for path in (ADD_DOMAIN, COMPOSE_SKILL, COMPOSE_LIVE, AUTHOR_DURABLE):
        assert "VERTICAL-BUILD-CONTRACT.md" in path.read_text(encoding="utf-8"), path

    compose = COMPOSE_SKILL.read_text(encoding="utf-8")
    assert "Design-time meta-skill (v3)" not in compose
    assert "## How v4 works" not in compose
    assert "## The five steps" not in compose

    live = COMPOSE_LIVE.read_text(encoding="utf-8")
    assert "hand-stitches" not in live
    assert "add-domain Phase 4d" not in live
    assert "Phase-4b/4c" not in live

    durable = AUTHOR_DURABLE.read_text(encoding="utf-8")
    for stale in (
        "by hand to `function_app.py`",
        "**Patch `function_app.py`.**",
        "**Patch `api/server/services/simulator_orchestrator.py`.**",
        "**Patch `api/server/services/blueprint_inventory.py`.**",
    ):
        assert stale not in durable
    assert "pack-scoped graduation fragments" in durable

    proof = VERTICAL_PROOF.read_text(encoding="utf-8")
    assert "**Contract version:** `1.0.0`" in proof
    assert "Build ready" in proof
    assert "Demo ready" in proof

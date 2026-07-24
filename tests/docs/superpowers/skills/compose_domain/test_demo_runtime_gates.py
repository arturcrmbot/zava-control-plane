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

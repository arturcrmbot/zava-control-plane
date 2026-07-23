from pathlib import Path


ROOT = Path(__file__).resolve().parents[5]
ADD_DOMAIN = ROOT / ".github" / "skills" / "add-domain" / "SKILL.md"
COMPOSE_CHECKLIST = (
    ROOT / "docs" / "superpowers" / "skills" / "compose-domain" / "CHECKLIST.md"
)
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

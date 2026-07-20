from pathlib import Path


ROOT = Path(__file__).resolve().parents[5]
TEMPLATE = (
    ROOT
    / "docs"
    / "superpowers"
    / "skills"
    / "compose-domain"
    / "templates"
    / "graduate.sh.tmpl"
)
CHECKLIST = (
    ROOT
    / "docs"
    / "superpowers"
    / "skills"
    / "compose-domain"
    / "CHECKLIST.md"
)
COMPOSE_SKILL = (
    ROOT
    / "docs"
    / "superpowers"
    / "skills"
    / "compose-domain"
    / "SKILL.md"
)
ADD_DOMAIN_SKILL = ROOT / ".github" / "skills" / "add-domain" / "SKILL.md"
VERTICAL_PROOF = ROOT / "docs" / "VERTICAL-PROOF.md"


def test_graduation_targets_selected_vertical_pack() -> None:
    text = TEMPLATE.read_text(encoding="utf-8")

    assert 'VERTICAL="{{VERTICAL_NAME}}"' in text
    assert 'PACK_ROOT="verticals/$VERTICAL"' in text
    assert 'DURABLE_PATH="$PACK_ROOT/durable.py"' in text
    assert 'DOMAINS_PATH="$PACK_ROOT/domains.py"' in text
    assert 'FUNCTIONS_PATH="$PACK_ROOT/functions.py"' in text
    assert "$PACK_ROOT/skills" in text
    assert "$PACK_ROOT/personae" in text
    assert "$PACK_ROOT/mcp_tools" in text
    assert "$PACK_ROOT/entity_projections" in text


def test_graduation_never_patches_global_business_registries() -> None:
    text = TEMPLATE.read_text(encoding="utf-8")

    forbidden = (
        'cat >> function_app.py',
        'FN_PATH="api/shared/functions.py"',
        'INV_PATH="api/server/services/blueprint_inventory.py"',
        "api/server/skills/{{DOMAIN_NAME}}",
        "api/server/personae/{{PERSONA_ROLES_SPACED}}",
    )
    assert all(value not in text for value in forbidden)


def test_graduation_requires_pack_owned_registration_blocks() -> None:
    text = TEMPLATE.read_text(encoding="utf-8")

    assert "{{SPAWNER_REGISTRATION_BLOCK}}" in text
    assert "{{DOMAIN_DECLARATION_BLOCK}}" in text
    assert "{{FUNCTION_MEMBERSHIP_BLOCK}}" in text


# ---------------------------------------------------------------------------
# New tests — verify pack-scoped authoring contract (Task 3)
# ---------------------------------------------------------------------------


def test_checklist_omits_global_graduation_requirements() -> None:
    """CHECKLIST §7 must not claim graduate.sh patches the global
    function_app.py, simulator_orchestrator.py, or blueprint_inventory.py."""
    text = CHECKLIST.read_text(encoding="utf-8")
    assert "graduate.sh patches `function_app.py`" not in text
    assert (
        "graduate.sh patches `api/server/services/simulator_orchestrator.py`"
        not in text
    )
    assert (
        "graduate.sh patches `api/server/services/blueprint_inventory.py`"
        not in text
    )


def test_collision_check_references_active_pack_not_global_domains() -> None:
    """Domain collision checks must reference the selected pack, not the
    global api.shared.domains.DOMAINS constant."""
    stale = "api.shared.domains.DOMAINS"
    assert stale not in COMPOSE_SKILL.read_text(encoding="utf-8")
    assert stale not in CHECKLIST.read_text(encoding="utf-8")


def test_compose_domain_skill_does_not_enumerate_global_patch_steps() -> None:
    """The graduate.sh step enumeration inside compose-domain SKILL.md must
    not list function_app.py, simulator_orchestrator.py, or
    blueprint_inventory.py as Patch targets."""
    text = COMPOSE_SKILL.read_text(encoding="utf-8")
    assert "Patch `function_app.py`" not in text
    assert "Patch `api/server/services/simulator_orchestrator.py`" not in text
    assert "Patch `api/server/services/blueprint_inventory.py`" not in text


def test_add_domain_entry_point_does_not_reference_global_infrastructure_files() -> None:
    """add-domain SKILL.md (the operator entry point) must not reference
    simulator_orchestrator.py or blueprint_inventory.py as graduation targets."""
    text = ADD_DOMAIN_SKILL.read_text(encoding="utf-8")
    assert "simulator_orchestrator.py" not in text
    assert "blueprint_inventory.py" not in text


def test_vertical_proof_doc_exists() -> None:
    """docs/VERTICAL-PROOF.md must be present in the repository."""
    assert VERTICAL_PROOF.exists(), "docs/VERTICAL-PROOF.md does not exist"


def test_vertical_proof_doc_has_mandatory_concepts() -> None:
    """docs/VERTICAL-PROOF.md must define the full proof chain and reference
    every mandatory concept required by the authoring contract."""
    assert VERTICAL_PROOF.exists(), "docs/VERTICAL-PROOF.md does not exist"
    text = VERTICAL_PROOF.read_text(encoding="utf-8")
    for concept in (
        "actor world",
        "Durable",
        "typed command",
        "world mutation",
        "Constellation",
        "Functions disabled",
        "browser errors",
    ):
        assert concept in text, (
            f"docs/VERTICAL-PROOF.md missing mandatory concept: {concept!r}"
        )

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

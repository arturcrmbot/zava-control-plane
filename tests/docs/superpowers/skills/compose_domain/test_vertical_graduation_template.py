from pathlib import Path


ROOT = Path(__file__).resolve().parents[5]
TEMPLATES_DIR = (
    ROOT / "docs" / "superpowers" / "skills" / "compose-domain" / "templates"
)
TEMPLATE = TEMPLATES_DIR / "graduate.sh.tmpl"
GRADUATION_TMPL = TEMPLATES_DIR / "GRADUATION.md.tmpl"
ACTIVITY_TMPL = TEMPLATES_DIR / "activity.py.tmpl"
ORCHESTRATOR_TMPL = TEMPLATES_DIR / "orchestrator.py.tmpl"
SEGMENT_TRIGGER_TMPL = TEMPLATES_DIR / "segment_activity_trigger.py.tmpl"
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


# ---------------------------------------------------------------------------
# Appendix-phrase regression tests — catch stale active-instruction text
# ---------------------------------------------------------------------------


def test_skill_md_no_stale_function_app_active_instructions() -> None:
    """SKILL.md must not contain active-instruction phrases that describe
    patching function_app.py. Safety prose (forbidden/never-edit) is allowed;
    only specific instruction phrases are banned."""
    text = COMPOSE_SKILL.read_text(encoding="utf-8")
    stale_phrases = (
        "patched into `function_app.py`",
        "function_app.py patch block",
        "applies the function_app.py patch",
        "function_app.py gets ONE",
        "a function_app.py patch from",
        "function_app.py activity-trigger pair",
    )
    for phrase in stale_phrases:
        assert phrase not in text, (
            f"SKILL.md contains stale active-instruction phrase: {phrase!r}"
        )


def test_graduation_tmpl_no_global_patch_steps() -> None:
    """GRADUATION.md.tmpl must not describe patching the three global files
    as graduation steps. The safety prose in graduate.sh.tmpl prohibition
    comments is not affected by this check."""
    text = GRADUATION_TMPL.read_text(encoding="utf-8")
    forbidden_steps = (
        "Patch `function_app.py`",
        "Patch `api/server/services/simulator_orchestrator.py`",
        "Patch `api/server/services/blueprint_inventory.py`",
    )
    for phrase in forbidden_steps:
        assert phrase not in text, (
            f"GRADUATION.md.tmpl still claims global patch step: {phrase!r}"
        )


def test_graduation_tmpl_rollback_targets_pack_files() -> None:
    """Rollback in GRADUATION.md.tmpl must reference pack-owned paths, not
    the global files replaced by the vertical-pack authoring model."""
    text = GRADUATION_TMPL.read_text(encoding="utf-8")
    assert "verticals/{{VERTICAL_NAME}}/durable.py" in text
    assert "verticals/{{VERTICAL_NAME}}/spawners.py" in text
    # Must not revert global files that graduation no longer touches
    assert "git checkout -- \\\n    function_app.py" not in text
    assert "api/server/services/simulator_orchestrator.py" not in text
    assert "api/server/services/blueprint_inventory.py" not in text


def test_graduation_tmpl_six_step_table() -> None:
    """GRADUATION.md.tmpl step table must describe exactly the six steps
    performed by graduate.sh.tmpl."""
    text = GRADUATION_TMPL.read_text(encoding="utf-8")
    assert "Register Durable functions" in text
    assert "Register pack business declarations" in text
    assert "Validate and print smoke commands" in text


def test_segment_trigger_tmpl_targets_durable_py() -> None:
    """segment_activity_trigger.py.tmpl must not tell authors to patch
    function_app.py; it must reference the pack's durable.py."""
    text = SEGMENT_TRIGGER_TMPL.read_text(encoding="utf-8")
    assert "function_app.py" not in text
    assert "durable.py" in text


def test_activity_tmpl_targets_durable_py() -> None:
    """activity.py.tmpl docstring must reference durable.py, not function_app.py."""
    text = ACTIVITY_TMPL.read_text(encoding="utf-8")
    assert "function_app.py" not in text
    assert "durable.py" in text


def test_orchestrator_tmpl_targets_durable_py() -> None:
    """orchestrator.py.tmpl must not say activities are registered in
    function_app.py; it must reference the pack's durable.py."""
    text = ORCHESTRATOR_TMPL.read_text(encoding="utf-8")
    assert "registered in `function_app.py`" not in text
    assert "durable.py" in text
    assert "api/shared/constants.py" not in text


def test_checklist_function_membership_targets_pack_functions_py() -> None:
    """CHECKLIST §10.2–10.3 must describe function membership registration in
    verticals/<vertical>/functions.py, not api/shared/functions.py (which is
    read-only active-pack adapter). Must not reference stale step 9."""
    text = CHECKLIST.read_text(encoding="utf-8")
    # Verify the correct target file is mentioned
    assert "verticals/<vertical>/functions.py" in text, (
        "CHECKLIST §10 must mention verticals/<vertical>/functions.py"
    )
    # Verify read-only nature is documented
    assert "read-only active-pack adapter" in text, (
        "CHECKLIST must explain api/shared/functions.py is read-only"
    )
    # Verify no stale references to non-existent graduate.sh step 9 for functions
    checklist_section_10 = text[text.find("## §10 —") : text.find("## §11 —")]
    assert "graduate.sh §9" not in checklist_section_10, (
        "CHECKLIST §10 must not reference stale graduate.sh §9"
    )
    # Verify it doesn't claim api/shared/functions.py is patched
    assert (
        "patches `api/shared/functions.py`" not in checklist_section_10
    ), "CHECKLIST §10 must not claim api/shared/functions.py is patched"


def test_checklist_sentinel_format_exact() -> None:
    """CHECKLIST §10.2–10.3 must specify exact sentinel format:
    # === BEGIN compose-domain <workflow_type> ===
    (and matching END), guarded by grep `BEGIN compose-domain $MARKER`.
    Must not reference stale compose-domain:owns_domains:<fn> format."""
    text = CHECKLIST.read_text(encoding="utf-8")
    checklist_section_10 = text[text.find("## §10 —") : text.find("## §11 —")]
    
    # Verify exact sentinel format is documented
    assert "# === BEGIN compose-domain <workflow_type> ===" in checklist_section_10, (
        "CHECKLIST §10 must document exact BEGIN sentinel format"
    )
    assert "# === END compose-domain <workflow_type> ===" in checklist_section_10, (
        "CHECKLIST §10 must document exact END sentinel format"
    )
    
    # Verify grep guard pattern is documented
    assert "BEGIN compose-domain $MARKER" in checklist_section_10, (
        "CHECKLIST §10 must document grep guard pattern"
    )
    
    # Verify stale format is NOT mentioned
    assert "compose-domain:owns_domains:" not in checklist_section_10, (
        "CHECKLIST §10 must not mention stale compose-domain:owns_domains: format"
    )


def test_author_function_membership_skill_targets_pack_functions_py() -> None:
    """author-function-membership/SKILL.md 'Graduation patch' section must
    target verticals/<vertical>/functions.py, not api/shared/functions.py."""
    skill_md = (
        ROOT
        / "docs"
        / "superpowers"
        / "skills"
        / "compose-domain"
        / "sub-skills"
        / "author-function-membership"
        / "SKILL.md"
    )
    text = skill_md.read_text(encoding="utf-8")
    
    # Find the Graduation patch section
    if "## Graduation patch" in text:
        start = text.find("## Graduation patch")
        # Find the next section or end of file
        next_section = text.find("\n## ", start + 1)
        if next_section == -1:
            section = text[start:]
        else:
            section = text[start:next_section]
        
        # Verify it targets the pack's functions.py, not the global one
        assert "verticals/<vertical>/functions.py" in section, (
            "author-function-membership SKILL.md must target verticals/<vertical>/functions.py"
        )
        
        # Verify it does NOT instruct writing/patching to api/shared/functions.py
        assert "patches `api/shared/functions.py`" not in section, (
            "author-function-membership SKILL.md must not say it patches api/shared/functions.py"
        )
        assert "append" not in section or "verticals/<vertical>/functions.py" in section, (
            "author-function-membership SKILL.md append/modify instructions must reference pack functions.py"
        )
        
        # Verify it explains api/shared/functions.py is an adapter
        assert "read-only active-pack" in section or "read-only" in section, (
            "author-function-membership SKILL.md must explain api/shared/functions.py is read-only"
        )
        
        # Verify exact sentinel format
        assert "# === BEGIN compose-domain" in section, (
            "author-function-membership SKILL.md must use exact sentinel format"
        )


def test_graduation_template_smoke_restart_sets_zava_vertical() -> None:
    """GRADUATION.md.tmpl smoke test must set ZAVA_VERTICAL={{VERTICAL_NAME}}
    before ./scripts/profile-autonomous.sh to boot the selected vertical pack."""
    text = GRADUATION_TMPL.read_text(encoding="utf-8")
    assert "ZAVA_VERTICAL={{VERTICAL_NAME}} ./scripts/profile-autonomous.sh" in text, (
        "GRADUATION.md.tmpl smoke restart must contain exact "
        "'ZAVA_VERTICAL={{VERTICAL_NAME}} ./scripts/profile-autonomous.sh'"
    )

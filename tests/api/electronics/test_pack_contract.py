from __future__ import annotations

from pathlib import Path

from api.shared.vertical_loader import build_runtime, discover_pack_modules, validate_pack


ROOT = Path(__file__).resolve().parents[3]
PACK = ROOT / "verticals" / "electronics"
WORKFLOWS = (
    "inventory-rebalancing",
    "demand-spike-response",
    "promotion-readiness",
    "markdown-governance",
    "supplier-delay-recovery",
    "fulfilment-exception-resolution",
    "marketplace-seller-exception",
    "returns-disposition",
)


def test_electronics_pack_is_discovered_and_validates(tmp_path: Path) -> None:
    assert discover_pack_modules()["electronics"] == "verticals.electronics.manifest"

    runtime = build_runtime(
        {"ZAVA_VERTICAL": "electronics"},
        data_root=tmp_path,
    )

    assert runtime.pack.name == "electronics"
    assert runtime.pack.display_name == "Electronics Retail"
    assert runtime.world_name == "electronics"
    assert runtime.world_scale_name == "demo"
    assert (
        runtime.pack.worlds["electronics"]
        .scales["demo"]
        .default_minutes_per_second
        == 12.0
    )
    assert runtime.fingerprint.startswith("electronics:")
    validate_pack(runtime.pack)


def test_electronics_declares_exactly_eight_non_stub_workflows(tmp_path: Path) -> None:
    pack = build_runtime(
        {"ZAVA_VERTICAL": "electronics"},
        data_root=tmp_path,
    ).pack

    assert tuple(pack.domains) == WORKFLOWS
    assert all(not domain.stub for domain in pack.domains.values())
    assert len({domain.orchestrator_name for domain in pack.domains.values()}) == 8
    assert all(domain.phases for domain in pack.domains.values())


def test_personae_and_skills_are_pack_owned_under_electronics(tmp_path: Path) -> None:
    pack = build_runtime(
        {"ZAVA_VERTICAL": "electronics"},
        data_root=tmp_path,
    ).pack

    assert all(path.is_relative_to(PACK) for path in pack.personae_roots)
    assert all(path.is_relative_to(PACK) for path in pack.skill_roots)


def test_personae_define_executable_auto_close_policies(monkeypatch) -> None:
    from api.server.services import persona_responder
    from api.shared import authority as active_authority
    from verticals.electronics.authority import ELECTRONICS_AUTHORITY
    from verticals.electronics.personas import ELECTRONICS_PERSONAS

    monkeypatch.setattr(persona_responder, "PERSONAE_DIR", PACK / "personae")
    monkeypatch.setattr(persona_responder, "_lazy_app_graph", lambda: None)
    monkeypatch.setattr(
        active_authority,
        "AUTHORITY",
        dict(ELECTRONICS_AUTHORITY),
    )

    definitions = persona_responder._load_personae()

    assert set(definitions) == set(ELECTRONICS_PERSONAS)
    assert {
        role: definition.external_event
        for role, definition in definitions.items()
    } == {
        role: persona.external_event_default
        for role, persona in ELECTRONICS_PERSONAS.items()
    }
    for role, persona in ELECTRONICS_PERSONAS.items():
        result = definitions[role].decide(
            {
                "action": persona.external_event_default,
                "request": {
                    "amount": (
                        35_976.0 if role == "merchandising_director" else 0
                    ),
                    "category": "electronics-demo",
                },
            }
        )
        assert result["decision"] == "approve"


def test_electronics_python_never_imports_other_verticals() -> None:
    assert PACK.is_dir(), f"Electronics PACK directory not found at {PACK}; tests cannot verify import boundaries without it"
    leaked: list[str] = []
    for path in PACK.rglob("*.py"):
        source = path.read_text(encoding="utf-8")
        if (
            "verticals.fashion" in source
            or "verticals.telco" in source
            or "verticals.agency" in source
        ):
            leaked.append(str(path.relative_to(ROOT)))

    assert leaked == []


def test_governance_manifest_declares_every_electronics_mcp_tool() -> None:
    from api.server.services.governance.manifest import load_tools_yaml

    tools = load_tools_yaml(str(PACK / "policies" / "tools.yaml"))

    assert set(tools) == {
        "electronics_read_inventory",
        "electronics_prepare_inventory_transfer",
        "electronics_assess_promotion",
        "electronics_prepare_markdown_recommendation",
        "electronics_prepare_supplier_recovery",
        "electronics_prepare_fulfilment_resolution",
        "electronics_prepare_seller_suppression",
        "electronics_prepare_return_disposition",
    }

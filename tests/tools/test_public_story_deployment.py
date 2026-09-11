"""Contract tests for the public story deployment pipeline.

These tests verify that:
- infra/main.parameters.json requires ZAVA_MODE at deploy time (no live default);
- scripts/deploy-blueprint.sh uses the full azd path and includes all proof checks;
- infra/main.bicep and infra/modules/aca-app.bicep declare zavaMode as required (no default);
- active documentation does not refer to the old static nginx ACA deployment.
"""

from __future__ import annotations

import json
from pathlib import Path
import re

import pytest

from api.server.services.memory.domain_memory import configured_memory_domains
from api.shared.vertical_loader import PACK_MODULES, build_runtime

ROOT = Path(__file__).resolve().parents[2]


def test_azd_requires_an_explicit_mode() -> None:
    params = json.loads((ROOT / "infra/main.parameters.json").read_text())
    # Must be bare ${ZAVA_MODE} — no '=live' default that would silently deploy
    # a live mode when the operator forgets to set the variable.
    assert params["parameters"]["zavaMode"]["value"] == "${ZAVA_MODE}"


def test_bicep_zava_mode_has_no_live_default() -> None:
    """Both Bicep files must declare zavaMode as required — no = 'live' fallback."""
    for bicep_rel in ("infra/main.bicep", "infra/modules/aca-app.bicep"):
        bicep = (ROOT / bicep_rel).read_text(encoding="utf-8")
        assert "param zavaMode string" in bicep, (
            f"{bicep_rel}: must declare param zavaMode string"
        )
        assert "param zavaMode string = 'live'" not in bicep, (
            f"{bicep_rel}: must not have a 'live' default for zavaMode — "
            "direct deploys must supply mode explicitly"
        )


@pytest.mark.parametrize("vertical", sorted(PACK_MODULES))
def test_aca_memory_configuration_matches_selected_pack(vertical: str) -> None:
    bicep = (ROOT / "infra/modules/aca-app.bicep").read_text()
    declaration = re.search(
        r"\{\s*name:\s*'MEMORY_DOMAINS',\s*value:\s*'([^']*)'\s*\}",
        bicep,
    )
    if "name: 'MEMORY_DOMAINS'" in bicep:
        assert declaration, "Memory override must be a validated literal"
    raw = declaration.group(1) if declaration else None
    allowed = build_runtime({"ZAVA_VERTICAL": vertical}).pack.memory_workflow_types

    assert configured_memory_domains(raw=raw, allowed=allowed) == list(allowed)


def test_azd_forwards_selected_vertical() -> None:
    params = json.loads((ROOT / "infra/main.parameters.json").read_text())
    main = (ROOT / "infra/main.bicep").read_text()
    app = (ROOT / "infra/modules/aca-app.bicep").read_text()

    assert params["parameters"]["zavaVertical"]["value"] == "${ZAVA_VERTICAL=agency}"
    assert "param zavaVertical string = 'agency'" in main
    assert "zavaVertical: zavaVertical" in main
    assert "param zavaVertical string = 'agency'" in app
    assert "{ name: 'ZAVA_VERTICAL', value: zavaVertical }" in app


def test_azd_forwards_azure_supervisor_deployment() -> None:
    params = json.loads((ROOT / "infra/main.parameters.json").read_text())
    main = (ROOT / "infra/main.bicep").read_text()
    app = (ROOT / "infra/modules/aca-app.bicep").read_text()

    assert params["parameters"]["azureOpenAiFleetManagerDeployment"]["value"] == (
        "${AZURE_OPENAI_FLEET_MANAGER_DEPLOYMENT=}"
    )
    assert "azureOpenAiFleetManagerDeployment: azureOpenAiFleetManagerDeployment" in main
    assert (
        "{ name: 'AZURE_OPENAI_FLEET_MANAGER_DEPLOYMENT', value: azureOpenAiFleetManagerDeployment }"
    ) in app


def test_aca_data_root_follows_storage_configuration() -> None:
    app = (ROOT / "infra/modules/aca-app.bicep").read_text()

    assert (
        "{ name: 'ZAVA_DATA_DIR', value: "
        "persistData ? '/data' : '/app/data/runtime' }"
    ) in app


def test_live_deployment_keeps_external_ingress_closed() -> None:
    app = (ROOT / "infra/modules/aca-app.bicep").read_text()
    assert "external: zavaMode == 'replay'" in app


def test_live_deployment_wires_platform_authentication() -> None:
    app = (ROOT / "infra/modules/aca-app.bicep").read_text()
    params = json.loads((ROOT / "infra/main.parameters.json").read_text())
    assert "Microsoft.App/containerApps/authConfigs@2024-03-01" in app
    assert "{ name: 'READ_ROUTE_AUTH', value: zavaMode == 'live' ? 'platform' : '' }" in app
    assert "{ name: 'AUTH_TENANT_ID', value: authTenantId }" in app
    assert params["parameters"]["authTenantId"]["value"] == "${AUTH_TENANT_ID=}"
    assert params["parameters"]["authClientId"]["value"] == "${AUTH_CLIENT_ID=}"


def test_deployment_separates_readiness_from_liveness() -> None:
    app = (ROOT / "infra/modules/aca-app.bicep").read_text()
    assert app.count("path: '/readyz'") == 2
    assert app.count("path: '/healthz'") == 1


def test_replay_deployment_uses_the_proven_graph_memory_budget() -> None:
    bicep = (ROOT / "infra/modules/aca-app.bicep").read_text()
    assert "memory: '4Gi'" in bicep
    assert (
        "{ name: 'ENTITY_GRAPH_BUFFER_POOL_MB', "
        "value: zavaMode == 'replay' ? '256' : '0' }"
    ) in bicep


def test_public_deploy_uses_the_full_azd_path() -> None:
    script = (ROOT / "scripts/deploy-blueprint.sh").read_text()
    # Must require replay mode.
    assert '[[ "${ZAVA_MODE:-}" == "replay" ]]' in script
    # Must check all proof artefacts.
    assert "proof/public-replay.json" in script
    assert "proof/manifest.json" in script
    assert "proof/seller-review.json" in script
    # Must enforce tenant isolation.
    assert "EXPECTED_TENANT_ID" in script
    # Must verify the provenance manifest.
    assert "python tools/public_replay_manifest.py verify" in script
    # Must use the canonical azd deploy, not ad-hoc ACR/ACA commands.
    assert "azd up" in script
    # Must smoke-test the deployed surface.
    assert "/api/replay/meta" in script
    # Must NOT reference the old nginx-only blueprint Dockerfile or ACR provisioning.
    assert "web/blueprint/Dockerfile" not in script
    assert "az acr create" not in script


def test_deploy_script_guards_against_empty_fqdn() -> None:
    script = (ROOT / "scripts/deploy-blueprint.sh").read_text()
    # Must fail with a clear error when the FQDN is empty after azd env get-value.
    assert '[[ -n "$FQDN" ]]' in script
    # Must use correct sed -E to strip https?:// prefix.
    assert "sed -E" in script
    assert "https?://" in script


def test_active_docs_reference_exact_deploy_phrases() -> None:
    """Each active doc must contain its canonical deployment phrase/link."""
    EXPECTED: dict[Path, list[str]] = {
        ROOT / "README.md": [
            "scripts/deploy-blueprint.sh",
            "proof-gated wrapper around `azd up`",
        ],
        ROOT / "docs/DEVELOPMENT.md": [
            "deploy-blueprint.sh",
            "Proof-gated wrapper around `azd up`",
        ],
        ROOT / "docs/blueprint-microsite-contributor-guide.md": [
            "scripts/deploy-blueprint.sh",
            "proof-gated wrapper around the canonical",
            "azd up",
        ],
        ROOT / "docs/superpowers/skills/compose-domain/SKILL.md": [
            "ZAVA_MODE=replay",
            "scripts/deploy-blueprint.sh",
        ],
        ROOT / "docs/superpowers/skills/compose-domain/templates/GRADUATION.md.tmpl": [
            "ZAVA_MODE=replay",
            "scripts/deploy-blueprint.sh",
        ],
    }
    for doc_path, phrases in EXPECTED.items():
        text = doc_path.read_text(encoding="utf-8")
        assert "nginx-only blueprint ACA" not in text, (
            f"{doc_path.relative_to(ROOT)}: must not describe the old nginx-only ACA path"
        )
        for phrase in phrases:
            assert phrase in text, (
                f"{doc_path.relative_to(ROOT)}: must contain canonical phrase {phrase!r}"
            )

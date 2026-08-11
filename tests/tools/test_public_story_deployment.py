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

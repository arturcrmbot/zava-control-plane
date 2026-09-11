"""Offline packaging guards; actual container startup is a separate smoke check."""
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def test_python_image_includes_discoverable_vertical_packs() -> None:
    dockerfile = (ROOT / "deploy/Dockerfile").read_text(encoding="utf-8")
    python_stage = dockerfile.split("AS py-build", 1)[1].split("AS runtime", 1)[0]
    assert "COPY verticals ./verticals" in python_stage
    assert "COPY --from=py-build /app /app" in dockerfile


def test_build_context_excludes_local_state_and_credentials() -> None:
    rules = {
        line.strip()
        for line in (ROOT / ".dockerignore").read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    }
    assert {".env", "**/local.settings.json", "azurite-data/", "data/runtime/"} <= rules
    assert "verticals" not in rules
    assert "verticals/" not in rules


def test_alternate_package_index_preserves_locked_dependency_hashes() -> None:
    dockerfile = (ROOT / "deploy/Dockerfile").read_text(encoding="utf-8")
    assert "ARG PYPI_INDEX_URL=https://pypi.org/simple" in dockerfile
    assert "uv export --frozen --no-dev --no-emit-project" in dockerfile
    assert "--require-hashes" in dockerfile
    assert '--default-index "${PYPI_INDEX_URL}"' in dockerfile
    assert "--no-verify-hashes" not in dockerfile
    assert "--allow-insecure-host" not in dockerfile


def test_frontend_builds_use_locked_installs_and_no_npx_download_fallback() -> None:
    dockerfile = (ROOT / "deploy/Dockerfile").read_text(encoding="utf-8")
    assert "ARG NPM_REGISTRY=https://registry.npmjs.org" in dockerfile
    assert dockerfile.count("ci --include=dev") == 3
    assert "RUN ./node_modules/.bin/vite build" in dockerfile
    assert "RUN npx vite build" not in dockerfile


def test_blueprint_build_copies_imported_walkthrough_media() -> None:
    dockerfile = (ROOT / "deploy/Dockerfile").read_text(encoding="utf-8")
    spa_stage = dockerfile.split("AS spa-build", 1)[1].split("AS py-build", 1)[0]
    media_copy = "COPY docs/media/aurora-recorded-walkthrough* ./docs/media/"
    assert media_copy in spa_stage
    assert spa_stage.index(media_copy) < spa_stage.index("&& BASE_PATH=/blueprint/")


def test_build_context_keeps_walkthrough_media_without_all_docs() -> None:
    rules = [
        line.strip()
        for line in (ROOT / ".dockerignore").read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    ]
    expected = [
        "docs/*",
        "!docs/media/",
        "docs/media/*",
        "!docs/media/aurora-recorded-walkthrough*",
    ]
    assert all(rule in rules for rule in expected)
    positions = [rules.index(rule) for rule in expected]
    assert positions == sorted(positions)


def test_acr_build_enables_buildkit_and_pushes_a_source_tagged_image() -> None:
    import yaml

    task_path = ROOT / "deploy/acr-build.yaml"
    assert task_path.is_file(), "ACR needs an explicit BuildKit task for RUN --mount"
    task = yaml.safe_load(task_path.read_text())
    build, push = task["steps"]

    assert "DOCKER_BUILDKIT=1" in build["env"]
    assert "--platform linux/amd64" in build["build"]
    assert "-f deploy/Dockerfile ." in build["build"]
    assert "org.opencontainers.image.revision={{.Values.sourceCommit}}" in build["build"]
    image = "$Registry/{{.Values.imageRepository}}:{{.Values.imageTag}}"
    assert image in build["build"]
    assert push["push"] == [image]
    assert build["timeout"] <= 900


def test_acr_runbook_repeats_set_for_each_task_value() -> None:
    guide = (ROOT / "docs/zava-hosting-brief.md").read_text()
    for name in ("imageRepository", "imageTag", "sourceCommit"):
        assert f"--set {name}=" in guide

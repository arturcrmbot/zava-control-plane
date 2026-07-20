from __future__ import annotations

from importlib import import_module
from pathlib import Path

import pytest

from tests.api.shared.vertical_pack_fakes import make_test_pack


def _loader():
    return import_module("api.shared.vertical_loader")


@pytest.fixture
def pack_loader(tmp_path):
    return lambda name: make_test_pack(name, tmp_path)


def test_selection_table(tmp_path, pack_loader) -> None:
    loader = _loader()

    assert loader.build_runtime(
        {}, data_root=tmp_path, pack_loader=pack_loader
    ).pack.name == "agency"
    assert loader.build_runtime(
        {"ZAVA_WORLD": "support"},
        data_root=tmp_path,
        pack_loader=pack_loader,
    ).pack.name == "agency"
    assert loader.build_runtime(
        {"ZAVA_WORLD": "telco"},
        data_root=tmp_path,
        pack_loader=pack_loader,
    ).pack.name == "telco"


def test_data_directory_is_namespaced(tmp_path, pack_loader) -> None:
    loader = _loader()

    agency = loader.build_runtime(
        {}, data_root=tmp_path, pack_loader=pack_loader
    )
    telco = loader.build_runtime(
        {"ZAVA_VERTICAL": "telco"},
        data_root=tmp_path,
        pack_loader=pack_loader,
    )

    assert agency.data_dir == tmp_path / "agency"
    assert telco.data_dir == tmp_path / "telco"


def test_world_scale_requires_an_active_owned_world(tmp_path, pack_loader) -> None:
    loader = _loader()

    with pytest.raises(ValueError, match="requires an active world"):
        loader.build_runtime(
            {"ZAVA_WORLD_SCALE": "demo"},
            data_root=tmp_path,
            pack_loader=pack_loader,
        )
    with pytest.raises(ValueError, match="unknown scale 'stress'"):
        loader.build_runtime(
            {
                "ZAVA_VERTICAL": "telco",
                "ZAVA_WORLD_SCALE": "stress",
            },
            data_root=tmp_path,
            pack_loader=pack_loader,
        )


def test_explicit_vertical_world_mismatch_fails(tmp_path, pack_loader) -> None:
    loader = _loader()

    with pytest.raises(
        ValueError,
        match="world 'support' is not owned by vertical 'telco'",
    ):
        loader.build_runtime(
            {
                "ZAVA_VERTICAL": "telco",
                "ZAVA_WORLD": "support",
            },
            data_root=tmp_path,
            pack_loader=pack_loader,
        )


def test_active_runtime_is_process_immutable(
    monkeypatch, tmp_path, pack_loader
) -> None:
    loader = _loader()
    loader.active_runtime.cache_clear()
    monkeypatch.setattr(loader, "load_pack", pack_loader)
    monkeypatch.setenv("ZAVA_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("ZAVA_VERTICAL", "agency")
    first = loader.active_runtime()
    monkeypatch.setenv("ZAVA_VERTICAL", "telco")

    assert loader.active_runtime() is first
    assert loader.active_runtime().pack.name == "agency"
    loader.active_runtime.cache_clear()


def test_discover_pack_modules_returns_agency_and_telco() -> None:
    loader = _loader()
    result = loader.discover_pack_modules()
    assert result["agency"] == "verticals.agency.manifest"
    assert result["telco"] == "verticals.telco.manifest"


def test_discover_pack_modules_includes_fashion() -> None:
    loader = _loader()
    result = loader.discover_pack_modules()
    assert result["fashion"] == "verticals.fashion.manifest"


def test_discover_pack_modules_filters_underscored_and_missing_manifest(
    tmp_path,
) -> None:
    loader = _loader()
    root = tmp_path / "verticals"
    # valid vertical
    retail_manifest = root / "retail" / "manifest.py"
    retail_manifest.parent.mkdir(parents=True)
    retail_manifest.touch()
    # underscore-prefixed directory - should be ignored
    shared_dir = root / "_shared"
    shared_manifest = shared_dir / "manifest.py"
    shared_manifest.parent.mkdir(parents=True)
    shared_manifest.touch()
    # directory without manifest.py - should be ignored
    notes_dir = root / "notes"
    notes_dir.mkdir()

    result = loader.discover_pack_modules(root)
    assert result == {"retail": "verticals.retail.manifest"}

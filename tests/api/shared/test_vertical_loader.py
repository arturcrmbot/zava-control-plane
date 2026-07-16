from __future__ import annotations

from importlib import import_module

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

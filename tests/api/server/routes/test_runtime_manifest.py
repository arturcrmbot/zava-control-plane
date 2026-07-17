from __future__ import annotations

from importlib import import_module

from api.shared.vertical_loader import build_runtime


def test_runtime_payload_defaults_to_agency(tmp_path) -> None:
    runtime_route = import_module("api.server.routes.runtime")
    runtime = build_runtime({}, data_root=tmp_path)

    assert runtime_route.runtime_payload(runtime) == {
        "vertical": {
            "name": "agency",
            "display_name": "Agency",
            "manifest_version": "1",
            "fingerprint": "agency:1",
        },
        "world": None,
        "world_scale": None,
        "capabilities": [
            "blueprint",
            "compose",
            "knowledge",
            "memory",
        ],
        "ui": {
            "lenses": ["agency-operations"],
            "theme": {"accent": "#2563eb", "label": "Agency"},
        },
    }


def test_runtime_payload_exposes_telco_world(tmp_path) -> None:
    runtime_route = import_module("api.server.routes.runtime")
    runtime = build_runtime(
        {"ZAVA_VERTICAL": "telco"},
        data_root=tmp_path,
    )

    payload = runtime_route.runtime_payload(runtime)

    assert payload["vertical"]["name"] == "telco"
    assert payload["world"] == "telco"
    assert payload["world_scale"] == "demo"
    assert payload["ui"]["lenses"] == [
        "telco-network",
        "field-operations",
        "customer-impact",
        "order",
        "control",
    ]

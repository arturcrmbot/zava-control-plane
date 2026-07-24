from __future__ import annotations

import json
from dataclasses import replace
from importlib import import_module

from api.shared.vertical_loader import build_runtime
from api.shared.world_scene_contracts import load_world_scene


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
            "world_scene": False,
        },
    }
    assert runtime_route.runtime_payload(runtime)["ui"]["world_scene"] is False


def test_runtime_payload_exposes_world_scene_metadata_when_registered(tmp_path) -> None:
    runtime_route = import_module("api.server.routes.runtime")
    runtime = build_runtime({}, data_root=tmp_path)

    # Scene lives under an isolated fake pack root (not the real vertical
    # directory) since this test only exercises payload shaping, not
    # pack-ownership validation.
    fake_pack_root = tmp_path / "fake-pack-root"
    scene_path = fake_pack_root / "ui" / "world-scene.json"
    scene_path.parent.mkdir(parents=True, exist_ok=True)
    scene_path.write_text(
        json.dumps(
            {
                "version": "1",
                "title": "Demo Scene",
                "locations": [{"id": "hub", "label": "Hub", "x": 0.1, "y": 0.2}],
                "actor_bindings": [
                    {
                        "collection": "units",
                        "kind": "unit",
                        "id_field": "id",
                        "state_field": "status",
                        "location_field": "current_hub_id",
                    }
                ],
                "event_mappings": [
                    {
                        "event_type": "unit.moved",
                        "animation_type": "move",
                        "actor_id_field": "payload.unit_id",
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    scene = load_world_scene(scene_path, pack_root=fake_pack_root)
    runtime = replace(
        runtime,
        pack=replace(runtime.pack, ui=replace(runtime.pack.ui, world_scene=scene)),
    )

    payload = runtime_route.runtime_payload(runtime)

    assert payload["ui"]["world_scene"] == scene.to_metadata()
    assert json.loads(json.dumps(payload)) == payload


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
        "process-library",
        "field-operations",
        "customer-impact",
        "order",
        "control",
    ]

from __future__ import annotations

from dataclasses import fields
from importlib import import_module

import pytest


def _scene() -> dict:
    return {
        "schema_version": 1,
        "title": "Demo actor world",
        "locations": [
            {
                "id": "LOC-1",
                "label": "Location one",
                "kind": "site",
                "x": 10,
                "y": 20,
                "width": 30,
                "height": 40,
            }
        ],
        "layers": [
            {
                "state_key": "people",
                "kind": "person",
                "label": "People",
                "id_field": "id",
                "location_field": "location_id",
                "status_field": "status",
                "colour": "#2563eb",
            }
        ],
        "event_mappings": [
            {
                "event_type": "person.moved",
                "layer": "people",
                "animation": "move",
            }
        ],
    }


def test_world_registration_owns_an_optional_scene_contract() -> None:
    contracts = import_module("api.shared.world_contracts")

    assert "scene" in {field.name for field in fields(contracts.WorldPackRegistration)}

    registration = contracts.WorldPackRegistration(
        name="demo",
        scales={},
        default_scale="demo",
        objective_routes=(),
        responders={},
        scene=_scene(),
    )
    assert registration.scene["locations"][0]["id"] == "LOC-1"


def test_scene_validator_accepts_journal_backed_spatial_layers() -> None:
    contracts = import_module("api.shared.world_contracts")
    validator = getattr(contracts, "validate_world_scene", None)

    assert callable(validator)
    assert validator(_scene()) == _scene()


@pytest.mark.parametrize(
    ("mutation", "message"),
    [
        (lambda scene: scene.update(schema_version=2), "schema_version"),
        (lambda scene: scene.update(locations=[]), "locations"),
        (
            lambda scene: scene["layers"][0].pop("location_field"),
            "location_field",
        ),
        (
            lambda scene: scene.update(event_mappings=[]),
            "event_mappings",
        ),
    ],
)
def test_scene_validator_rejects_non_spatial_or_unjournalled_contracts(
    mutation,
    message: str,
) -> None:
    contracts = import_module("api.shared.world_contracts")
    validator = getattr(contracts, "validate_world_scene", None)
    assert callable(validator)
    scene = _scene()
    mutation(scene)

    with pytest.raises(ValueError, match=message):
        validator(scene)


def test_runtime_manifest_marks_only_scene_backed_worlds() -> None:
    runtime_route = import_module("api.server.routes.runtime")
    loader = import_module("api.shared.vertical_loader")

    agency = runtime_route.runtime_payload(loader.build_runtime({}))
    telco = runtime_route.runtime_payload(
        loader.build_runtime({"ZAVA_VERTICAL": "telco"})
    )
    fashion = runtime_route.runtime_payload(
        loader.build_runtime({"ZAVA_VERTICAL": "fashion"})
    )

    assert agency["ui"]["world_scene"] is False
    assert telco["ui"]["world_scene"] is False
    assert fashion["ui"]["world_scene"] is True

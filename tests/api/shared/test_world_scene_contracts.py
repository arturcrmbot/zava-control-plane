from __future__ import annotations

import json
from pathlib import Path

import pytest

from api.shared.world_scene_contracts import (
    ActorBinding,
    ActorPositionBinding,
    EventAnimationMapping,
    SceneLocation,
    WorldSceneContract,
    WorldSceneError,
    load_world_scene,
)


def _valid_scene_data() -> dict:
    return {
        "version": "1",
        "title": "Demo Scene",
        "locations": [
            {"id": "hub-a", "label": "Hub A", "x": 0.1, "y": 0.2},
            {"id": "hub-b", "label": "Hub B", "x": 0.8, "y": 0.9},
        ],
        "actor_bindings": [
            {
                "collection": "units",
                "kind": "unit",
                "id_field": "id",
                "state_field": "status",
                "location_field": "current_hub_id",
            },
            {
                "collection": "markers",
                "kind": "marker",
                "id_field": "id",
                "state_field": "status",
                "x_field": "pos_x",
                "y_field": "pos_y",
            },
            {
                "collection": "movers",
                "kind": "mover",
                "id_field": "id",
                "state_field": "status",
                "route_field": "route_id",
                "progress_field": "progress",
            },
        ],
        "event_mappings": [
            {
                "event_type": "unit.dispatched",
                "animation_type": "move",
                "actor_id_field": "payload.unit_id",
            },
            {
                "event_type": "unit.arrived",
                "animation_type": "stop",
                "actor_id": "unit-1",
            },
            {
                "event_type": "marker.highlighted",
                "animation_type": "pulse",
                "target_id": "hub-a",
            },
        ],
    }


def _write_scene(pack_root: Path, data: dict, *, relative: str = "ui/world-scene.json") -> Path:
    source_path = pack_root / relative
    source_path.parent.mkdir(parents=True, exist_ok=True)
    source_path.write_text(json.dumps(data), encoding="utf-8")
    return source_path


def test_load_world_scene_accepts_a_valid_scene(tmp_path: Path) -> None:
    pack_root = tmp_path / "pack"
    source_path = _write_scene(pack_root, _valid_scene_data())

    scene = load_world_scene(source_path, pack_root=pack_root)

    assert isinstance(scene, WorldSceneContract)
    assert scene.version == "1"
    assert scene.title == "Demo Scene"
    assert [loc.id for loc in scene.locations] == ["hub-a", "hub-b"]
    assert scene.source_path == source_path
    assert len(scene.actor_bindings) == 3
    assert len(scene.event_mappings) == 3


def test_load_world_scene_rejects_missing_source(tmp_path: Path) -> None:
    pack_root = tmp_path / "pack"
    pack_root.mkdir()
    missing_path = pack_root / "ui" / "world-scene.json"

    with pytest.raises(WorldSceneError, match="does not exist"):
        load_world_scene(missing_path, pack_root=pack_root)


def test_load_world_scene_rejects_malformed_json(tmp_path: Path) -> None:
    pack_root = tmp_path / "pack"
    source_path = pack_root / "ui" / "world-scene.json"
    source_path.parent.mkdir(parents=True)
    source_path.write_text("{not valid json", encoding="utf-8")

    with pytest.raises(WorldSceneError, match="not valid JSON"):
        load_world_scene(source_path, pack_root=pack_root)


def test_load_world_scene_rejects_unknown_and_missing_keys(tmp_path: Path) -> None:
    pack_root = tmp_path / "pack"

    data_missing = _valid_scene_data()
    del data_missing["title"]
    source_path = _write_scene(pack_root, data_missing)
    with pytest.raises(WorldSceneError, match="missing keys"):
        load_world_scene(source_path, pack_root=pack_root)

    data_unknown = _valid_scene_data()
    data_unknown["mystery"] = True
    source_path = _write_scene(pack_root, data_unknown)
    with pytest.raises(WorldSceneError, match="unknown keys"):
        load_world_scene(source_path, pack_root=pack_root)


def test_load_world_scene_rejects_duplicate_location_ids(tmp_path: Path) -> None:
    pack_root = tmp_path / "pack"
    data = _valid_scene_data()
    data["locations"].append({"id": "hub-a", "label": "Hub A Again", "x": 0.3, "y": 0.4})
    source_path = _write_scene(pack_root, data)

    with pytest.raises(WorldSceneError, match="duplicate location ids"):
        load_world_scene(source_path, pack_root=pack_root)


def test_load_world_scene_rejects_duplicate_actor_bindings(tmp_path: Path) -> None:
    pack_root = tmp_path / "pack"
    data = _valid_scene_data()
    data["actor_bindings"].append(
        {
            "collection": "units",
            "kind": "unit",
            "id_field": "id",
            "state_field": "status",
            "location_field": "current_hub_id",
        }
    )
    source_path = _write_scene(pack_root, data)

    with pytest.raises(WorldSceneError, match="duplicate actor bindings"):
        load_world_scene(source_path, pack_root=pack_root)


def test_load_world_scene_rejects_invalid_actor_position_binding(tmp_path: Path) -> None:
    pack_root = tmp_path / "pack"

    no_strategy = _valid_scene_data()
    no_strategy["actor_bindings"] = [
        {
            "collection": "units",
            "kind": "unit",
            "id_field": "id",
            "state_field": "status",
        }
    ]
    source_path = _write_scene(pack_root, no_strategy, relative="a/world-scene.json")
    with pytest.raises(WorldSceneError, match="exactly one strategy"):
        load_world_scene(source_path, pack_root=pack_root)

    two_strategies = _valid_scene_data()
    two_strategies["actor_bindings"] = [
        {
            "collection": "units",
            "kind": "unit",
            "id_field": "id",
            "state_field": "status",
            "location_field": "current_hub_id",
            "x_field": "pos_x",
            "y_field": "pos_y",
        }
    ]
    source_path = _write_scene(pack_root, two_strategies, relative="b/world-scene.json")
    with pytest.raises(WorldSceneError, match="exactly one strategy"):
        load_world_scene(source_path, pack_root=pack_root)

    partial_route = _valid_scene_data()
    partial_route["actor_bindings"] = [
        {
            "collection": "movers",
            "kind": "mover",
            "id_field": "id",
            "state_field": "status",
            "route_field": "route_id",
        }
    ]
    source_path = _write_scene(pack_root, partial_route, relative="c/world-scene.json")
    with pytest.raises(WorldSceneError, match="route"):
        load_world_scene(source_path, pack_root=pack_root)


def test_load_world_scene_rejects_duplicate_event_mapping_identity(tmp_path: Path) -> None:
    pack_root = tmp_path / "pack"
    data = _valid_scene_data()
    data["event_mappings"].append(
        {
            "event_type": "unit.dispatched",
            "animation_type": "move",
            "actor_id": "unit-2",
        }
    )
    source_path = _write_scene(pack_root, data)

    with pytest.raises(WorldSceneError, match="duplicate event mappings"):
        load_world_scene(source_path, pack_root=pack_root)


def test_load_world_scene_rejects_event_mapping_missing_actor_reference(tmp_path: Path) -> None:
    pack_root = tmp_path / "pack"
    data = _valid_scene_data()
    data["event_mappings"] = [{"event_type": "unit.dispatched", "animation_type": "move"}]
    source_path = _write_scene(pack_root, data)

    with pytest.raises(WorldSceneError, match="exactly one real actor"):
        load_world_scene(source_path, pack_root=pack_root)


def test_load_world_scene_rejects_event_mapping_with_multiple_actor_references(
    tmp_path: Path,
) -> None:
    pack_root = tmp_path / "pack"
    data = _valid_scene_data()
    data["event_mappings"] = [
        {
            "event_type": "unit.dispatched",
            "animation_type": "move",
            "actor_id": "unit-1",
            "target_id": "hub-a",
        }
    ]
    source_path = _write_scene(pack_root, data)

    with pytest.raises(WorldSceneError, match="exactly one real actor"):
        load_world_scene(source_path, pack_root=pack_root)


def test_load_world_scene_rejects_out_of_range_coordinates(tmp_path: Path) -> None:
    pack_root = tmp_path / "pack"
    data = _valid_scene_data()
    data["locations"][0]["x"] = 1.5
    source_path = _write_scene(pack_root, data)

    with pytest.raises(WorldSceneError, match="out-of-range"):
        load_world_scene(source_path, pack_root=pack_root)


def test_load_world_scene_rejects_source_outside_pack_root(tmp_path: Path) -> None:
    pack_root = tmp_path / "pack"
    pack_root.mkdir()
    outside_root = tmp_path / "elsewhere"
    source_path = _write_scene(outside_root, _valid_scene_data())

    with pytest.raises(WorldSceneError, match="outside pack root"):
        load_world_scene(source_path, pack_root=pack_root)


def test_scene_to_metadata_is_json_safe(tmp_path: Path) -> None:
    pack_root = tmp_path / "pack"
    source_path = _write_scene(pack_root, _valid_scene_data())
    scene = load_world_scene(source_path, pack_root=pack_root)

    metadata = scene.to_metadata()

    assert json.loads(json.dumps(metadata)) == metadata
    assert metadata["version"] == "1"
    assert metadata["locations"][0] == {"id": "hub-a", "label": "Hub A", "x": 0.1, "y": 0.2}


def test_scene_location_is_immutable() -> None:
    location = SceneLocation(id="hub-a", label="Hub A", x=0.1, y=0.2)
    with pytest.raises(Exception):
        location.x = 0.9  # type: ignore[misc]


def test_actor_position_binding_requires_exactly_one_strategy() -> None:
    with pytest.raises(WorldSceneError, match="exactly one strategy"):
        ActorPositionBinding()


def test_event_animation_mapping_requires_actor_reference() -> None:
    with pytest.raises(WorldSceneError, match="exactly one real actor"):
        EventAnimationMapping(event_type="unit.dispatched", animation_type="move")


def test_actor_binding_requires_state_and_id_fields() -> None:
    with pytest.raises(WorldSceneError, match="id_field"):
        ActorBinding(
            collection="units",
            kind="unit",
            id_field="",
            state_field="status",
            position=ActorPositionBinding(location_field="current_hub_id"),
        )


def test_load_world_scene_rejects_empty_actor_id_combined_with_actor_id_field(
    tmp_path: Path,
) -> None:
    """An empty 'actor_id' alongside a set 'actor_id_field' must be rejected.

    Truthiness-based validation would treat "" as absent and silently accept
    this, but serialization treats "" as present (not None), which would put
    two reference keys on the wire -- one of them empty and unusable.
    """
    pack_root = tmp_path / "pack"
    data = _valid_scene_data()
    data["event_mappings"] = [
        {
            "event_type": "unit.dispatched",
            "animation_type": "move",
            "actor_id": "",
            "actor_id_field": "payload.unit_id",
        }
    ]
    source_path = _write_scene(pack_root, data)

    with pytest.raises(WorldSceneError, match="empty 'actor_id'"):
        load_world_scene(source_path, pack_root=pack_root)


def test_load_world_scene_rejects_empty_actor_id_field(tmp_path: Path) -> None:
    pack_root = tmp_path / "pack"
    data = _valid_scene_data()
    data["event_mappings"] = [
        {
            "event_type": "unit.dispatched",
            "animation_type": "move",
            "actor_id_field": "",
        }
    ]
    source_path = _write_scene(pack_root, data)

    with pytest.raises(WorldSceneError, match="empty 'actor_id_field'"):
        load_world_scene(source_path, pack_root=pack_root)


def test_load_world_scene_rejects_empty_target_id(tmp_path: Path) -> None:
    pack_root = tmp_path / "pack"
    data = _valid_scene_data()
    data["event_mappings"] = [
        {
            "event_type": "marker.highlighted",
            "animation_type": "pulse",
            "target_id": "",
        }
    ]
    source_path = _write_scene(pack_root, data)

    with pytest.raises(WorldSceneError, match="empty 'target_id'"):
        load_world_scene(source_path, pack_root=pack_root)


def test_event_animation_mapping_rejects_empty_actor_id_directly() -> None:
    with pytest.raises(WorldSceneError, match="empty 'actor_id'"):
        EventAnimationMapping(event_type="unit.dispatched", animation_type="move", actor_id="")


@pytest.mark.parametrize(
    "field_name",
    ["location_field", "x_field", "y_field", "route_field", "progress_field"],
)
def test_load_world_scene_rejects_empty_actor_position_fields(tmp_path: Path, field_name: str) -> None:
    pack_root = tmp_path / "pack"
    data = _valid_scene_data()
    binding: dict = {
        "collection": "units",
        "kind": "unit",
        "id_field": "id",
        "state_field": "status",
    }
    if field_name in ("x_field", "y_field"):
        binding["x_field"] = "pos_x"
        binding["y_field"] = "pos_y"
    elif field_name in ("route_field", "progress_field"):
        binding["route_field"] = "route_id"
        binding["progress_field"] = "progress"
    else:
        binding["location_field"] = "current_hub_id"
    binding[field_name] = ""
    data["actor_bindings"] = [binding]
    source_path = _write_scene(pack_root, data)

    with pytest.raises(WorldSceneError, match=f"empty '{field_name}'"):
        load_world_scene(source_path, pack_root=pack_root)


@pytest.mark.parametrize(
    "field_name",
    ["location_field", "x_field", "y_field", "route_field", "progress_field"],
)
def test_actor_position_binding_rejects_empty_field_directly(field_name: str) -> None:
    kwargs: dict = {}
    if field_name in ("x_field", "y_field"):
        kwargs["x_field"] = "pos_x"
        kwargs["y_field"] = "pos_y"
    elif field_name in ("route_field", "progress_field"):
        kwargs["route_field"] = "route_id"
        kwargs["progress_field"] = "progress"
    else:
        kwargs["location_field"] = "current_hub_id"
    kwargs[field_name] = ""

    with pytest.raises(WorldSceneError, match=f"empty '{field_name}'"):
        ActorPositionBinding(**kwargs)


def test_load_world_scene_valid_strategies_remain_accepted_with_one_metadata_key(
    tmp_path: Path,
) -> None:
    """Each valid exactly-one reference/position strategy still loads, and
    metadata emits exactly one reference key per event mapping."""
    pack_root = tmp_path / "pack"
    source_path = _write_scene(pack_root, _valid_scene_data())

    scene = load_world_scene(source_path, pack_root=pack_root)
    metadata = scene.to_metadata()

    reference_keys = {"actor_id", "target_id", "actor_id_field"}
    for mapping in metadata["event_mappings"]:
        present = reference_keys & set(mapping)
        assert len(present) == 1, f"expected exactly one reference key, got {present}"

    position_keys = {"location_field", "x_field", "y_field", "route_field", "progress_field"}
    expected_strategy_key_counts = {"units": 1, "markers": 2, "movers": 2}
    for binding in metadata["actor_bindings"]:
        present = position_keys & set(binding["position"])
        assert len(present) == expected_strategy_key_counts[binding["collection"]]

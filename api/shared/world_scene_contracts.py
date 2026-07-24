"""Neutral, industry-agnostic contract for a vertical pack's spatial world scene.

A world scene describes a 2D backdrop (named locations), how live actor
snapshots bind onto that backdrop, and how domain events animate those
actors. A pack owns exactly one scene JSON file (registered on its UI
manifest); loading here proves the file exists, is owned by the pack, and
satisfies the structural rules a later generic spatial renderer will rely
on. No industry vocabulary lives in this module -- packs supply their own
location/actor/event names.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any


class WorldSceneError(ValueError):
    """Raised when a world scene source fails to load or validate."""


def _duplicates(values: list[Any]) -> set[Any]:
    seen: set[Any] = set()
    dupes: set[Any] = set()
    for value in values:
        if value in seen:
            dupes.add(value)
        seen.add(value)
    return dupes


@dataclass(frozen=True, slots=True)
class SceneLocation:
    id: str
    label: str
    x: float
    y: float

    def __post_init__(self) -> None:
        if not self.id:
            raise WorldSceneError("scene location is missing an 'id'")
        if not self.label:
            raise WorldSceneError(f"scene location {self.id!r} is missing a 'label'")
        for axis, value in (("x", self.x), ("y", self.y)):
            if not isinstance(value, (int, float)) or not (0.0 <= float(value) <= 1.0):
                raise WorldSceneError(
                    f"scene location {self.id!r} has out-of-range {axis}={value!r}; "
                    "expected a value in [0, 1]"
                )


_POSITION_FIELD_NAMES = (
    "location_field",
    "x_field",
    "y_field",
    "route_field",
    "progress_field",
)


@dataclass(frozen=True, slots=True)
class ActorPositionBinding:
    location_field: str | None = None
    x_field: str | None = None
    y_field: str | None = None
    route_field: str | None = None
    progress_field: str | None = None

    def __post_init__(self) -> None:
        for field_name in _POSITION_FIELD_NAMES:
            value = getattr(self, field_name)
            if value is not None and not value.strip():
                raise WorldSceneError(
                    f"actor position binding has an empty {field_name!r}; "
                    "expected a non-empty string or omit the field"
                )
        if len(self.strategies()) != 1:
            raise WorldSceneError(
                "actor position binding must set exactly one strategy: "
                "'location_field', both 'x_field'/'y_field', or both "
                "'route_field'/'progress_field'"
            )

    def strategies(self) -> tuple[str, ...]:
        found: list[str] = []
        if self.location_field is not None:
            found.append("location")
        has_xy = self.x_field is not None or self.y_field is not None
        if has_xy:
            if self.x_field is None or self.y_field is None:
                raise WorldSceneError(
                    "actor position binding using coordinates requires both "
                    "'x_field' and 'y_field'"
                )
            found.append("coordinates")
        has_route = self.route_field is not None or self.progress_field is not None
        if has_route:
            if self.route_field is None or self.progress_field is None:
                raise WorldSceneError(
                    "actor position binding using a route requires both "
                    "'route_field' and 'progress_field'"
                )
            found.append("route")
        return tuple(found)


@dataclass(frozen=True, slots=True)
class ActorBinding:
    collection: str
    kind: str
    id_field: str
    state_field: str
    position: ActorPositionBinding

    def __post_init__(self) -> None:
        if not self.collection:
            raise WorldSceneError("actor binding is missing a 'collection'")
        if not self.kind:
            raise WorldSceneError(f"actor binding {self.collection!r} is missing a 'kind'")
        if not self.id_field:
            raise WorldSceneError(f"actor binding {self.collection!r} is missing an 'id_field'")
        if not self.state_field:
            raise WorldSceneError(
                f"actor binding {self.collection!r} is missing a 'state_field'"
            )


@dataclass(frozen=True, slots=True)
class EventAnimationMapping:
    event_type: str
    animation_type: str
    actor_id: str | None = None
    target_id: str | None = None
    actor_id_field: str | None = None

    def __post_init__(self) -> None:
        if not self.event_type:
            raise WorldSceneError("event mapping is missing an 'event_type'")
        if not self.animation_type:
            raise WorldSceneError(
                f"event mapping {self.event_type!r} is missing an 'animation_type'"
            )
        for field_name in ("actor_id", "target_id", "actor_id_field"):
            value = getattr(self, field_name)
            if value is not None and not value.strip():
                raise WorldSceneError(
                    f"event mapping {self.event_type!r} -> {self.animation_type!r} "
                    f"has an empty {field_name!r}; expected a non-empty string or "
                    "omit the field"
                )
        references = [
            ref
            for ref in (self.actor_id, self.target_id, self.actor_id_field)
            if ref is not None
        ]
        if len(references) != 1:
            raise WorldSceneError(
                f"event mapping {self.event_type!r} -> {self.animation_type!r} must "
                "reference exactly one real actor via 'actor_id', 'target_id', or "
                f"'actor_id_field'; got {len(references)}"
            )

    @property
    def identity(self) -> tuple[str, str]:
        return (self.event_type, self.animation_type)


@dataclass(frozen=True, slots=True)
class WorldSceneContract:
    version: str
    title: str
    locations: tuple[SceneLocation, ...]
    actor_bindings: tuple[ActorBinding, ...]
    event_mappings: tuple[EventAnimationMapping, ...]
    source_path: Path

    def __post_init__(self) -> None:
        if not self.version:
            raise WorldSceneError("world scene is missing a 'version'")
        if not self.title:
            raise WorldSceneError("world scene is missing a 'title'")

        duplicate_locations = _duplicates([location.id for location in self.locations])
        if duplicate_locations:
            raise WorldSceneError(
                f"world scene has duplicate location ids: {sorted(duplicate_locations)}"
            )

        duplicate_bindings = _duplicates(
            [(binding.collection, binding.kind) for binding in self.actor_bindings]
        )
        if duplicate_bindings:
            raise WorldSceneError(
                "world scene has duplicate actor bindings for "
                f"collection/kind pairs: {sorted(duplicate_bindings)}"
            )

        duplicate_mappings = _duplicates([mapping.identity for mapping in self.event_mappings])
        if duplicate_mappings:
            raise WorldSceneError(
                "world scene has duplicate event mappings for "
                f"event_type/animation_type pairs: {sorted(duplicate_mappings)}"
            )

    def to_metadata(self) -> dict[str, Any]:
        """Return a JSON-safe summary suitable for runtime manifest exposure.

        Contains no filesystem paths so it is safe to send to clients.
        """
        return {
            "version": self.version,
            "title": self.title,
            "locations": [
                {"id": loc.id, "label": loc.label, "x": loc.x, "y": loc.y}
                for loc in self.locations
            ],
            "actor_bindings": [
                {
                    "collection": binding.collection,
                    "kind": binding.kind,
                    "id_field": binding.id_field,
                    "state_field": binding.state_field,
                    "position": {
                        key: value
                        for key, value in (
                            ("location_field", binding.position.location_field),
                            ("x_field", binding.position.x_field),
                            ("y_field", binding.position.y_field),
                            ("route_field", binding.position.route_field),
                            ("progress_field", binding.position.progress_field),
                        )
                        if value is not None
                    },
                }
                for binding in self.actor_bindings
            ],
            "event_mappings": [
                {
                    key: value
                    for key, value in (
                        ("event_type", mapping.event_type),
                        ("animation_type", mapping.animation_type),
                        ("actor_id", mapping.actor_id),
                        ("target_id", mapping.target_id),
                        ("actor_id_field", mapping.actor_id_field),
                    )
                    if value is not None
                }
                for mapping in self.event_mappings
            ],
        }


_REQUIRED_TOP_LEVEL_KEYS = {"version", "title", "locations", "actor_bindings", "event_mappings"}


def load_world_scene(source_path: Path, *, pack_root: Path) -> WorldSceneContract:
    """Load and validate a world scene JSON file owned by a vertical pack.

    Raises WorldSceneError if the source path escapes the pack root, is
    missing, contains malformed JSON, or fails structural validation.
    """
    try:
        source_path.resolve().relative_to(pack_root.resolve())
    except ValueError:
        raise WorldSceneError(
            f"world scene source {str(source_path)!r} is outside pack root "
            f"{str(pack_root)!r}"
        ) from None

    if not source_path.is_file():
        raise WorldSceneError(f"world scene source {str(source_path)!r} does not exist")

    try:
        data = json.loads(source_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise WorldSceneError(
            f"world scene source {str(source_path)!r} is not valid JSON: {exc}"
        ) from exc

    if not isinstance(data, dict):
        raise WorldSceneError(
            f"world scene source {str(source_path)!r} must contain a JSON object"
        )

    missing_keys = _REQUIRED_TOP_LEVEL_KEYS - set(data)
    if missing_keys:
        raise WorldSceneError(
            f"world scene source {str(source_path)!r} is missing keys: "
            f"{sorted(missing_keys)}"
        )
    unknown_keys = set(data) - _REQUIRED_TOP_LEVEL_KEYS
    if unknown_keys:
        raise WorldSceneError(
            f"world scene source {str(source_path)!r} has unknown keys: "
            f"{sorted(unknown_keys)}"
        )

    try:
        locations = tuple(
            SceneLocation(
                id=str(item["id"]),
                label=str(item["label"]),
                x=item["x"],
                y=item["y"],
            )
            for item in data["locations"]
        )
        actor_bindings = tuple(
            ActorBinding(
                collection=str(item["collection"]),
                kind=str(item["kind"]),
                id_field=str(item["id_field"]),
                state_field=str(item["state_field"]),
                position=ActorPositionBinding(
                    location_field=item.get("location_field"),
                    x_field=item.get("x_field"),
                    y_field=item.get("y_field"),
                    route_field=item.get("route_field"),
                    progress_field=item.get("progress_field"),
                ),
            )
            for item in data["actor_bindings"]
        )
        event_mappings = tuple(
            EventAnimationMapping(
                event_type=str(item["event_type"]),
                animation_type=str(item["animation_type"]),
                actor_id=item.get("actor_id"),
                target_id=item.get("target_id"),
                actor_id_field=item.get("actor_id_field"),
            )
            for item in data["event_mappings"]
        )
    except WorldSceneError:
        raise
    except (KeyError, TypeError) as exc:
        raise WorldSceneError(
            f"world scene source {str(source_path)!r} has a malformed entry: {exc}"
        ) from exc

    return WorldSceneContract(
        version=str(data["version"]),
        title=str(data["title"]),
        locations=locations,
        actor_bindings=actor_bindings,
        event_mappings=event_mappings,
        source_path=source_path,
    )

"""Travel's registered actor world must be eligible for the live server."""
from __future__ import annotations

from api.shared.vertical_loader import build_runtime


def test_registered_travel_world_is_eligible_for_actor_service_startup(tmp_path):
    """A selected pack's own registered world is not a hard-coded whitelist."""
    from api.server.services.world_activation import should_start_actor_world

    runtime = build_runtime({"ZAVA_VERTICAL": "travel"}, data_root=tmp_path)

    assert runtime.world_name == "travel"
    assert should_start_actor_world(
        runtime,
        world_name=runtime.world_name,
        actor_world_enabled=True,
    ) is True


def test_actor_world_environment_switch_disables_registered_travel_world(tmp_path):
    """The replay probe can intentionally run the API without the simulator."""
    from api.server.services.world_activation import should_start_actor_world

    runtime = build_runtime({"ZAVA_VERTICAL": "travel"}, data_root=tmp_path)

    assert should_start_actor_world(
        runtime,
        world_name=runtime.world_name,
        actor_world_enabled=False,
    ) is False


def test_blueprint_replay_mask_disables_registered_travel_world(tmp_path):
    """The activation policy must use the effective, replay-masked world."""
    from api.server.services.world_activation import should_start_actor_world

    runtime = build_runtime({"ZAVA_VERTICAL": "travel"}, data_root=tmp_path)

    assert should_start_actor_world(
        runtime,
        world_name=None,
        actor_world_enabled=True,
    ) is False

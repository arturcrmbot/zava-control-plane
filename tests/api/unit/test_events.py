from api.shared.events import wakes_fleet_manager, WAKE_TYPES, FleetEvent


def test_wakes_on_exception_detected():
    e = FleetEvent(type="workflow.exception.detected", workflow_id="A", category="duplicate-invoice", severity="high")
    assert wakes_fleet_manager(e) is True


def test_does_not_wake_on_phase_started():
    e = FleetEvent(type="workflow.phase.started", workflow_id="A", phase="Intake")
    assert wakes_fleet_manager(e) is False


def test_wake_set_size():
    assert len(WAKE_TYPES) == 6

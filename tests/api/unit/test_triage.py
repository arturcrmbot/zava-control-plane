import time
from api.server.services.triage import Triage
from api.shared.events import FleetEvent


def test_does_not_wake_on_phase_started():
    t = Triage()
    e = FleetEvent(type="workflow.phase.started", workflow_id="A", phase="Intake")
    assert t.should_wake(e) is False


def test_wakes_on_exception_detected():
    t = Triage()
    e = FleetEvent(type="workflow.exception.detected", workflow_id="A", category="duplicate-invoice", severity="high")
    assert t.should_wake(e) is True


def test_detects_anomaly_on_3_dups_in_60s():
    t = Triage()
    now = time.time()
    for i in range(3):
        e = FleetEvent(type="workflow.exception.detected", workflow_id=f"W-{i}", category="duplicate-invoice", severity="high")
        t.observe(e, now=now + i)
    a = t.detect_anomaly(now=now + 3)
    assert a is not None
    assert a["pattern"] == "duplicate-burst"

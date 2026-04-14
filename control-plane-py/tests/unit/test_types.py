from src.shared.types import next_phase, PHASE_ORDER


def test_next_phase_returns_next():
    assert next_phase("Intake") == "Validation"
    assert next_phase("Approval") == "Payment"


def test_next_phase_returns_none_at_end():
    assert next_phase("Reconciliation") is None


def test_phase_order_is_six():
    assert len(PHASE_ORDER) == 6

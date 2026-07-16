from api.server.services.world_responders import resolve_responder
from api.shared.vertical_loader import build_runtime


def test_hitl_responders_outlive_approval_gate_and_post_approval_execution(
    tmp_path,
):
    runtime = build_runtime(
        {"ZAVA_VERTICAL": "telco"},
        data_root=tmp_path,
    )
    for objective_type in ("proactive_customer_care", "order_to_activate"):
        responder = resolve_responder(runtime, objective_type)
        assert responder.timeout_seconds >= 900


def test_agency_cannot_resolve_telco_responder(tmp_path):
    runtime = build_runtime({}, data_root=tmp_path)

    try:
        resolve_responder(runtime, "proactive_customer_care")
    except ValueError as error:
        assert "vertical 'agency'" in str(error)
    else:
        raise AssertionError("Agency unexpectedly resolved a Telco responder")

from api.server.services.world_responders import resolve_responder


def test_hitl_responders_outlive_approval_gate_and_post_approval_execution():
    for objective_type in ("proactive_customer_care", "order_to_activate"):
        responder = resolve_responder(objective_type)
        assert responder.timeout_seconds >= 900

"""Verify agent.completed webhook writes to DomainMemory via infer=True."""
from fastapi.testclient import TestClient

from api.server.main import app
from tests.api._helpers.durable_event import signed_post


def test_agent_completed_writes_to_domain_memory():
    """When agent.completed fires for a hiring agent, the bridge calls
    domain_memories['hiring'].add with the agent's response text."""
    captured = {}

    class FakeDomainMemory:
        domain = "hiring"

        def add(self, text, *, agent_skill="", workflow_id=""):
            captured["text"] = text
            captured["agent_skill"] = agent_skill
            captured["workflow_id"] = workflow_id
            return []

    from api.server.routes.internal_durable_event import app_state

    original = getattr(app_state, "domain_memories", {})
    app_state.domain_memories = {"hiring": FakeDomainMemory()}
    try:
        client = TestClient(app)
        response = signed_post(client, {
            "workflow_id": "WF-1",
            "instance_id": None,
            "kind": "agent.completed",
            "payload": {
                "agent_label": "interview_recommender",
                "response_text": "decline: CV empty",
                "tool_calls": [],
                "usage": {"input_tokens": 10, "output_tokens": 5},
            },
        })
        assert response.status_code == 200
        assert captured["agent_skill"] == "interview_recommender"
        assert "CV empty" in captured["text"]
        assert captured["workflow_id"] == "WF-1"
    finally:
        app_state.domain_memories = original

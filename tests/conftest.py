"""Opt-in isolation for the focused harness command."""
from unittest.mock import AsyncMock, Mock

import pytest


@pytest.fixture
def harness_offline(request, monkeypatch):
    # Delivery tests exercise real HTTP client code through their own respx mocks.
    if request.node.path.name == "test_webhook_delivery.py":
        return

    from api.functions import webhook
    from api.functions.graphs import _tracked_executor
    from api.functions.graphs.executors.agents import _wrapper
    from api.functions.workflows import activities

    monkeypatch.setattr(webhook, "emit", AsyncMock())
    monkeypatch.setattr(webhook, "emit_sync", Mock())
    monkeypatch.setattr(_tracked_executor, "emit", AsyncMock())
    monkeypatch.setattr(activities, "emit", AsyncMock())
    monkeypatch.setattr(_wrapper, "_fetch_memories", AsyncMock(return_value=[]))

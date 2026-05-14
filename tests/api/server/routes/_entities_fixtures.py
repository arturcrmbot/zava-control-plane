"""Shared fixture: monkeypatch ``app_state.entities`` with a tmp-path
EntityGraph for the duration of a single test, then restore. Used by the
five ``test_entities_*.py`` route tests so each test gets an isolated graph
without bleeding state between tests.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from api.server.services.entity_graph import EntityGraph
from api.server.state import app_state


@pytest.fixture
def graph(tmp_path: Path, monkeypatch):
    g = EntityGraph(tmp_path / "g.kuzu")
    monkeypatch.setattr(app_state, "entities", g)
    try:
        yield g
    finally:
        g.close()


@pytest.fixture
def client():
    # Lazy import — picks up the (now monkeypatched) app_state.entities at
    # request time via the route handlers.
    from fastapi.testclient import TestClient
    from api.server.main import app
    return TestClient(app)

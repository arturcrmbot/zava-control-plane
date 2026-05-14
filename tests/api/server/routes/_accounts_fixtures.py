"""Shared fixture for the ``/api/accounts/summary`` route tests.

Mirrors the ``_entities_fixtures.py`` pattern: monkeypatches
``app_state.entities`` with a tmp-path EntityGraph for the duration of
a single test, seeds it with the minimal accounts demo dataset via
:func:`seed_account_demo`, and yields a ``TestClient(app)`` whose route
handlers will pick up the patched graph at request time.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from api.server.services.entity_graph import EntityGraph
from api.server.state import app_state
from tests.api.server.fixtures.entity_graph_seed import seed_account_demo


@pytest.fixture
def client_with_seed(tmp_path: Path, monkeypatch):
    g = EntityGraph(tmp_path / "g.kuzu")
    monkeypatch.setattr(app_state, "entities", g)
    seed_account_demo(g)
    try:
        from fastapi.testclient import TestClient
        from api.server.main import app
        yield TestClient(app)
    finally:
        g.close()

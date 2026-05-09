"""Shared helper for Phase 4 IP7+8+9 dispatch tests.

Other test modules in the suite call ``importlib.reload(api.server.state)``
which creates a brand-new ``app_state`` object. Routes that did
``from api.server.state import app_state`` at module load keep their
reference to the ORIGINAL app_state, so by the time my tests run the
state module's ``app_state`` and the routes' ``app_state`` are different
objects. Patching only one would leave reads + writes pointed at
different graphs.

The :func:`fresh_entities` fixture patches the routes' bound app_state
(via :mod:`api.server.routes.workflows`) so the substrate the route
reads matches the substrate this test writes to.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from api.server.routes.workflows import app_state as _routes_app_state
from api.server.services.entity_graph import EntityGraph
from api.server.services.meta_workflow_reflector import MetaWorkflowReflector

_REPO_ROOT = Path(__file__).resolve().parents[3]


@pytest.fixture
def fresh_entities(tmp_path: Path):
    app_state = _routes_app_state
    fresh = EntityGraph(tmp_path / "entities.kuzu")
    fresh.attach(bus=app_state.bus, audit=app_state.audit,
                 governance=app_state.governance)
    try:
        fresh.bootstrap_from_fixtures(
            employees_path=_REPO_ROOT / "data/synthetic/employees.json",
            vendors_path=_REPO_ROOT / "api/server/fixtures/vendors.json",
            agencies_path=_REPO_ROOT / "api/server/fixtures/agencies.json",
        )
    except Exception:
        pass

    prev_entities = getattr(app_state, "entities", None)
    prev_reflector = getattr(app_state, "meta_workflow_reflector", None)
    if prev_reflector is not None:
        try:
            prev_reflector.aclose()
        except Exception:
            pass
    app_state.entities = fresh
    new_reflector = MetaWorkflowReflector(
        bus=app_state.bus, audit=app_state.audit, graph=fresh,
    )
    new_reflector.start()
    app_state.meta_workflow_reflector = new_reflector
    try:
        yield fresh
    finally:
        try:
            new_reflector.aclose()
        except Exception:
            pass
        try:
            fresh.close()
        except Exception:
            pass
        if prev_entities is not None:
            app_state.entities = prev_entities
        if prev_reflector is not None:
            app_state.meta_workflow_reflector = prev_reflector


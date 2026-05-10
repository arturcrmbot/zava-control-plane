"""Tests for /api/workflows/{id}/tree (Phase 4 IP7 TASK-033/-034)."""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from api.server.services.entity_graph import EntityWrite
from tests.api.server._p4_fixtures import fresh_entities  # noqa: F401


@pytest.fixture
def client():
    from api.server.main import app
    return TestClient(app)


def _seed_workflow(graph, wid: str, wtype: str = "demo", status: str = "in_progress"):
    graph.upsert(EntityWrite(
        kind="Workflow", id=wid,
        attrs={"workflow_type": wtype, "status": status},
        source_workflows=(wid,),
    ))


def test_tree_for_unknown_workflow_returns_unknown_status(client, fresh_entities):
    r = client.get("/api/workflows/wf-does-not-exist/tree")
    assert r.status_code == 200
    body = r.json()
    assert body["workflow_id"] == "wf-does-not-exist"
    assert body["status"] == "unknown"
    assert body["children"] == []


def test_tree_two_levels(client, fresh_entities):
    g = fresh_entities
    parent_id = "wf-tree-parent-1"
    c1 = "wf-tree-child-1a"
    c2 = "wf-tree-child-1b"
    grandchild = "wf-tree-gc-1"
    for wid in (parent_id, c1, c2, grandchild):
        _seed_workflow(g, wid)
    g.link(parent_id, "SUB_WORKFLOW_OF", c1)
    g.link(parent_id, "SUB_WORKFLOW_OF", c2)
    g.link(c1, "SUB_WORKFLOW_OF", grandchild)

    r = client.get(f"/api/workflows/{parent_id}/tree")
    assert r.status_code == 200
    body = r.json()
    assert body["workflow_id"] == parent_id
    child_ids = sorted(c["workflow_id"] for c in body["children"])
    assert child_ids == sorted([c1, c2])
    grand = next(
        c["children"] for c in body["children"]
        if c["workflow_id"] == c1
    )
    assert len(grand) == 1
    assert grand[0]["workflow_id"] == grandchild


def test_tree_leaf_returns_empty_children(client, fresh_entities):
    wid = "wf-tree-leaf-1"
    _seed_workflow(fresh_entities, wid)
    r = client.get(f"/api/workflows/{wid}/tree")
    assert r.status_code == 200
    body = r.json()
    assert body["workflow_id"] == wid
    assert body["children"] == []


def test_tree_max_depth_cycle_protection(client, fresh_entities):
    g = fresh_entities
    a, b = "wf-tree-cycle-a", "wf-tree-cycle-b"
    _seed_workflow(g, a)
    _seed_workflow(g, b)
    g.link(a, "SUB_WORKFLOW_OF", b)
    g.link(b, "SUB_WORKFLOW_OF", a)
    r = client.get(f"/api/workflows/{a}/tree?max_depth=4")
    assert r.status_code == 200
    body = r.json()
    assert body["workflow_id"] == a


"""Tests for the /api/memory/* read endpoints surfacing real backend data."""
from __future__ import annotations

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from api.server.services.memory.domain_memory import DomainMemory
from api.server.services.memory.fallback_memory import FallbackMemory


@pytest.fixture
def client(monkeypatch):
    # Stand up a FastAPI app with just the memory routers and a stub
    # app_state.domain_memories backed by FallbackMemory.
    from api.server.routes import memory as memory_route
    from api.server.routes import memory_v2 as memory_v2_route

    app = FastAPI()
    app.include_router(memory_v2_route.router)
    app.include_router(memory_route.router)

    mem = FallbackMemory()
    hiring = DomainMemory(domain="hiring", memory=mem)
    vendor = DomainMemory(domain="vendor_kyc", memory=mem)

    class _Stub:
        domain_memories = {"hiring": hiring, "vendor_kyc": vendor}

    monkeypatch.setattr(memory_route, "_all_domain_memories", lambda: _Stub.domain_memories)
    monkeypatch.setattr(memory_v2_route, "app_state", _Stub())

    # Seed
    hiring.add("approve cv screen", agent_skill="persona:recruiter", workflow_id="w-1")
    hiring.add("reject cv screen", agent_skill="persona:recruiter", workflow_id="w-2")
    hiring.add_distilled(
        "LESSON: 2× reject for cv_screen — voice_score signals",
        metadata={"source": "dream-consolidation", "consolidated_at": "2026-05-21T19:00:00Z"},
    )
    vendor.add("approve KYC", agent_skill="persona:compliance", workflow_id="v-1")

    return TestClient(app)


def test_working_notes_returns_real_entries(client):
    r = client.get("/api/memory/working-notes")
    assert r.status_code == 200
    items = r.json()["items"]
    assert len(items) == 3
    domains = {i["domain"] for i in items}
    assert domains == {"hiring", "vendor_kyc"}
    # Lessons must NOT appear in working notes
    assert not any("LESSON" in (i["memory"] or "") for i in items)


def test_working_notes_filter_by_domain(client):
    r = client.get("/api/memory/working-notes?domain=hiring")
    items = r.json()["items"]
    assert len(items) == 2
    assert all(i["domain"] == "hiring" for i in items)


def test_working_notes_filter_by_agent_skill(client):
    r = client.get("/api/memory/working-notes?agent_skill=persona:compliance")
    items = r.json()["items"]
    assert len(items) == 1
    assert items[0]["domain"] == "vendor_kyc"


def test_lessons_active_returns_distilled(client):
    r = client.get("/api/memory/lessons/active")
    items = r.json()["items"]
    assert len(items) == 1
    assert "LESSON" in items[0]["memory"]
    assert items[0]["source"] == "dream-consolidation"


def test_lessons_active_filter_by_domain(client):
    assert client.get("/api/memory/lessons/active?domain=vendor_kyc").json()["items"] == []
    assert len(client.get("/api/memory/lessons/active?domain=hiring").json()["items"]) == 1


def test_per_persona_groups_correctly(client):
    r = client.get("/api/memory/per-persona")
    items = r.json()["items"]
    by_key = {(i["domain"], i["persona_role"]): i for i in items}
    assert by_key[("hiring", "recruiter")]["working"] == 2
    assert by_key[("hiring", "recruiter")]["lessons"] == 0
    # The lesson has no agent_skill metadata, so groups under _unattributed
    assert by_key[("hiring", "_unattributed")]["lessons"] == 1
    assert by_key[("vendor_kyc", "compliance")]["working"] == 1

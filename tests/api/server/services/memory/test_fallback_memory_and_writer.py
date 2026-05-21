"""Tests for FallbackMemory + fallback_consolidate + WorkingMemoryWriter."""
from __future__ import annotations

import pytest

from api.server.services.memory.domain_memory import (
    DomainMemory,
    build_domain_memories,
)
from api.server.services.memory.fallback_consolidator import (
    fallback_consolidate,
)
from api.server.services.memory.fallback_memory import (
    FallbackMemory,
    get_fallback_memory,
)


class TestFallbackMemory:
    def test_add_and_get_all(self):
        m = FallbackMemory()
        r = m.add(messages="hello world", user_id="domain:x", metadata={"k": "v"})
        assert len(r["results"]) == 1
        assert r["results"][0]["memory"] == "hello world"
        all_ = m.get_all(user_id="domain:x")
        assert len(all_["results"]) == 1
        assert all_["results"][0]["metadata"] == {"k": "v"}

    def test_add_empty_noop(self):
        m = FallbackMemory()
        assert m.add(messages="", user_id="x")["results"] == []

    def test_user_isolation(self):
        m = FallbackMemory()
        m.add(messages="a", user_id="u1")
        m.add(messages="b", user_id="u2")
        assert len(m.get_all(user_id="u1")["results"]) == 1
        assert len(m.get_all(user_id="u2")["results"]) == 1

    def test_search_returns_overlapping(self):
        m = FallbackMemory()
        m.add(messages="approve invoice for vendor acme", user_id="u")
        m.add(messages="reject travel claim for paris", user_id="u")
        r = m.search(query="invoice acme", user_id="u", limit=5)
        assert len(r["results"]) == 1
        assert "invoice" in r["results"][0]["memory"]

    def test_delete(self):
        m = FallbackMemory()
        a = m.add(messages="a", user_id="u")["results"][0]
        m.add(messages="b", user_id="u")
        m.delete(memory_id=a["id"])
        all_ = m.get_all(user_id="u")["results"]
        assert len(all_) == 1
        assert all_[0]["memory"] == "b"

    def test_update(self):
        m = FallbackMemory()
        a = m.add(messages="orig", user_id="u")["results"][0]
        m.update(a["id"], "new")
        assert m.get_all(user_id="u")["results"][0]["memory"] == "new"

    def test_singleton_shared(self):
        s1 = get_fallback_memory()
        s2 = get_fallback_memory()
        assert s1 is s2


class TestDomainMemoryWithFallback:
    def test_kind_metadata_on_add(self):
        mem = FallbackMemory()
        dm = DomainMemory(domain="hiring", memory=mem)
        dm.add("decision text", agent_skill="persona:recruiter", workflow_id="w1")
        items = dm.list_all()
        assert len(items) == 1
        assert items[0]["metadata"]["kind"] == "working"
        assert items[0]["metadata"]["domain"] == "hiring"
        assert items[0]["metadata"]["agent_skill"] == "persona:recruiter"

    def test_distilled_kind_is_lesson(self):
        mem = FallbackMemory()
        dm = DomainMemory(domain="hiring", memory=mem)
        dm.add_distilled(
            "consolidated lesson",
            metadata={"source": "dream-consolidation"},
        )
        items = dm.list_all()
        assert items[0]["metadata"]["kind"] == "lesson"
        assert items[0]["metadata"]["source"] == "dream-consolidation"

    def test_list_by_kind_partitions(self):
        mem = FallbackMemory()
        dm = DomainMemory(domain="hiring", memory=mem)
        dm.add("a", agent_skill="persona:x")
        dm.add("b", agent_skill="persona:y")
        dm.add_distilled("lesson1", metadata={"source": "dream-consolidation"})
        assert len(dm.list_by_kind("working")) == 2
        assert len(dm.list_by_kind("lesson")) == 1
        assert dm.count_working() == 2
        assert dm.count() == 3

    def test_build_domain_memories_with_fallback(self):
        mem = FallbackMemory()
        stores = build_domain_memories(domains=["hiring", "vendor"], memory=mem)
        assert set(stores.keys()) == {"hiring", "vendor"}
        stores["hiring"].add("h1")
        stores["vendor"].add("v1")
        assert stores["hiring"].count() == 1
        assert stores["vendor"].count() == 1


class TestFallbackConsolidator:
    def test_empty_input(self):
        assert fallback_consolidate([]) == []

    def test_single_passes_through(self):
        assert fallback_consolidate(["only one"]) == ["only one"]

    def test_patterned_inputs_compress(self):
        texts = [
            "[recruiter] REJECT for cv_screen — voice_score=1.2 cv_score=2",
            "[recruiter] REJECT for cv_screen — voice_score=1.4 cv_score=1",
            "[recruiter] REJECT for cv_screen — voice_score=1.8 cv_score=2",
            "[recruiter] REJECT for cv_screen — voice_score=1.1 cv_score=3",
            "[recruiter] APPROVE for offer_decision — voice_score=4.5 cv_score=5",
        ]
        out = fallback_consolidate(texts, threshold=0.4)
        assert len(out) < len(texts)
        # First cluster should have produced a LESSON summary
        joined = "\n".join(out)
        assert "LESSON" in joined
        assert "cv_screen" in joined.lower()

    def test_diverse_inputs_preserved(self):
        texts = [
            "alpha bravo charlie",
            "echo foxtrot golf",
            "kilo lima mike",
        ]
        out = fallback_consolidate(texts, threshold=0.5)
        assert len(out) == 3


class TestWorkingMemoryWriter:
    def test_no_op_when_unknown_domain(self, monkeypatch):
        from api.server.services.memory.working_memory_writer import (
            write_decision_memory,
        )
        # Patch _domain_memory_for to return None.
        import api.server.services.memory.working_memory_writer as wmw

        monkeypatch.setattr(wmw, "_domain_memory_for", lambda d: None)
        assert write_decision_memory(
            domain="unknown",
            persona_role="recruiter",
            verdict="approve",
            reason="ok",
            workflow_id="w",
            gate_phase="cv_screen",
        ) is False

    def test_writes_when_store_present(self, monkeypatch):
        from api.server.services.memory.working_memory_writer import (
            write_decision_memory,
            write_summary_memory,
        )
        import api.server.services.memory.working_memory_writer as wmw

        mem = FallbackMemory()
        dm = DomainMemory(domain="hiring", memory=mem)
        monkeypatch.setattr(
            wmw, "_domain_memory_for", lambda d: dm if d == "hiring" else None,
        )

        assert write_decision_memory(
            domain="hiring",
            persona_role="recruiter",
            verdict="reject",
            reason="weak signals",
            workflow_id="W-1",
            gate_phase="cv_screen",
            signals={"voice_score": 1.5, "cv_score": 2},
        ) is True
        assert write_summary_memory(
            domain="hiring",
            persona_role="talent_lead",
            headline="Voice score below 2 strongly predicts reject",
        ) is True
        items = dm.list_all()
        assert len(items) == 2
        # Decision entry should include signals
        decision_text = [
            i["memory"] for i in items if "REJECT" in i["memory"]
        ][0]
        assert "voice_score=1.5" in decision_text
        assert "cv_score=2" in decision_text
        # Summary entry includes the OBSERVATION marker
        summary_text = [
            i["memory"] for i in items if "OBSERVATION" in i["memory"]
        ][0]
        assert "below 2" in summary_text

    def test_swallows_errors(self, monkeypatch):
        from api.server.services.memory.working_memory_writer import (
            write_decision_memory,
        )
        import api.server.services.memory.working_memory_writer as wmw

        class _Boom:
            def add(self, *a, **kw):
                raise RuntimeError("nope")

        monkeypatch.setattr(wmw, "_domain_memory_for", lambda d: _Boom())
        # Should not raise — returns False.
        assert write_decision_memory(
            domain="hiring",
            persona_role="recruiter",
            verdict="approve",
            reason=None,
            workflow_id=None,
            gate_phase=None,
        ) is False

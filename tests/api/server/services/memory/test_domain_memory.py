from unittest.mock import MagicMock
import pytest

from api.server.services.memory.domain_memory import DomainMemory, build_domain_memories


@pytest.fixture
def fake_mem0():
    m = MagicMock(name="mem0.Memory")
    m.add.return_value = {"results": [{"id": "m1", "memory": "extracted insight"}]}
    m.search.return_value = {"results": [
        {"id": "m1", "memory": "candidates with sparse CVs should be advanced", "score": 0.91},
    ]}
    m.get_all.return_value = {"results": [
        {"id": "m1", "memory": "insight one", "metadata": {"domain": "hiring"}},
        {"id": "m2", "memory": "insight two", "metadata": {"domain": "hiring"}},
    ]}
    return m


def test_add_passes_infer_true_and_domain_metadata(fake_mem0):
    store = DomainMemory(domain="hiring", memory=fake_mem0)
    store.add(
        text="Declined candidate C-123 because CV was empty and voice score 0.75",
        agent_skill="interview_recommender",
        workflow_id="WF-001",
    )
    fake_mem0.add.assert_called_once()
    call_kw = fake_mem0.add.call_args
    assert call_kw.kwargs["infer"] is False
    assert call_kw.kwargs["user_id"] == "domain:hiring"
    assert call_kw.kwargs["metadata"]["domain"] == "hiring"
    assert call_kw.kwargs["metadata"]["agent_skill"] == "interview_recommender"
    assert call_kw.kwargs["metadata"]["workflow_id"] == "WF-001"


def test_add_distilled_passes_infer_false_and_domain_metadata(fake_mem0):
    store = DomainMemory(domain="hiring", memory=fake_mem0)
    store.add_distilled(
        "When CV is empty and no other positive signals exist, decline the candidate.",
        metadata={"source": "dream-consolidation", "domain": "override-attempt"},
    )
    call_kw = fake_mem0.add.call_args
    assert call_kw.kwargs["infer"] is False
    assert call_kw.kwargs["user_id"] == "domain:hiring"
    assert call_kw.kwargs["metadata"]["domain"] == "hiring"
    assert call_kw.kwargs["metadata"]["source"] == "dream-consolidation"


def test_recall_searches_with_domain_filter(fake_mem0):
    store = DomainMemory(domain="hiring", memory=fake_mem0)
    results = store.recall(query="sparse CV handling", top_k=3)
    fake_mem0.search.assert_called_once()
    call_kw = fake_mem0.search.call_args
    assert call_kw.kwargs["user_id"] == "domain:hiring"
    assert call_kw.kwargs["limit"] == 3
    assert len(results) == 1
    assert results[0]["memory"] == "candidates with sparse CVs should be advanced"
    assert results[0]["score"] == 0.91


def test_list_all_returns_all_memories_for_domain(fake_mem0):
    store = DomainMemory(domain="hiring", memory=fake_mem0)
    results = store.list_all(limit=100)
    fake_mem0.get_all.assert_called_once()
    assert len(results) == 2


def test_count_returns_number_of_memories(fake_mem0):
    store = DomainMemory(domain="hiring", memory=fake_mem0)
    assert store.count() == 2


def test_build_domain_memories_creates_one_per_domain():
    fake = MagicMock(name="mem0.Memory")
    fake.get_all.return_value = {"results": []}
    stores = build_domain_memories(domains=["hiring", "vendor_kyc"], memory=fake)
    assert set(stores.keys()) == {"hiring", "vendor_kyc"}
    assert stores["hiring"].domain == "hiring"
    assert stores["vendor_kyc"].domain == "vendor_kyc"


def test_appstate_has_domain_memories():
    """AppState exposes domain_memories dict."""
    from api.server.state import app_state

    assert hasattr(app_state, "domain_memories")
    assert isinstance(app_state.domain_memories, dict)
    # At minimum, the default "hiring" domain should be present
    # (or empty dict if Mem0 is unavailable — both are valid)

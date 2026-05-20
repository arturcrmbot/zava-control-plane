from unittest.mock import MagicMock, AsyncMock, call
import pytest

from api.server.services.memory.dream_consolidator import consolidate_memories
from api.server.services.memory.domain_memory import DomainMemory


@pytest.mark.asyncio
async def test_consolidate_deduplicates_and_replaces_store():
    fake_dm = MagicMock()
    fake_dm.domain = "hiring"
    fake_dm.list_all.return_value = [
        {"id": "m1", "memory": "Declined C-123 because CV empty"},
        {"id": "m2", "memory": "Declined C-456 because CV empty"},
        {"id": "m3", "memory": "Advanced C-789 despite low voice score"},
    ]
    fake_dm.add_distilled = MagicMock()

    llm_response = [
        "When CV is empty and no other positive signals exist, decline the candidate.",
        "Low voice score alone is not sufficient reason to decline if other evidence supports advancing.",
    ]

    llm_consolidate = AsyncMock(return_value=llm_response)

    result = await consolidate_memories(
        domain_memory=fake_dm,
        llm_consolidate=llm_consolidate,
    )

    llm_consolidate.assert_awaited_once_with([
        "Declined C-123 because CV empty",
        "Declined C-456 because CV empty",
        "Advanced C-789 despite low voice score",
    ])
    assert result["input_count"] == 3
    assert result["output_count"] == 2
    assert result["domain"] == "hiring"
    # Old memories deleted
    assert fake_dm.delete.call_count == 3
    # New memories written with infer=False through distilled writes
    assert fake_dm.add_distilled.call_count == 2
    for call in fake_dm.add_distilled.call_args_list:
        assert call.kwargs["metadata"]["source"] == "dream-consolidation"


@pytest.mark.asyncio
async def test_consolidate_is_noop_when_no_memories():
    fake_dm = MagicMock()
    fake_dm.domain = "hiring"
    fake_dm.list_all.return_value = []

    result = await consolidate_memories(
        domain_memory=fake_dm,
        llm_consolidate=AsyncMock(return_value=[]),
    )
    assert result["input_count"] == 0
    assert result["output_count"] == 0
    fake_dm.delete.assert_not_called()


@pytest.mark.asyncio
async def test_consolidate_reports_delete_failure_after_writing_replacements():
    fake_dm = MagicMock(spec=DomainMemory)
    fake_dm.domain = "hiring"
    fake_dm.list_all.return_value = [
        {"id": "m1", "memory": "insight one"},
        {"id": "m2", "memory": "insight two"},
    ]
    fake_dm.add_distilled = MagicMock()
    fake_dm.delete.side_effect = [None, RuntimeError("delete failed")]

    result = await consolidate_memories(
        domain_memory=fake_dm,
        llm_consolidate=AsyncMock(return_value=["consolidated insight"]),
    )

    assert result["input_count"] == 2
    assert result["output_count"] == 1
    assert "delete failed" in result["error"]
    fake_dm.add_distilled.assert_called_once()
    fake_dm.delete.assert_has_calls([call("m1"), call("m2")])


@pytest.mark.asyncio
async def test_consolidate_ignores_memories_without_both_id_and_text():
    fake_dm = MagicMock(spec=DomainMemory)
    fake_dm.domain = "hiring"
    fake_dm.list_all.return_value = [
        {"id": "m1", "memory": "valid insight"},
        {"id": "m2", "memory": ""},
        {"memory": "missing id"},
    ]
    fake_dm.add_distilled = MagicMock()

    result = await consolidate_memories(
        domain_memory=fake_dm,
        llm_consolidate=AsyncMock(return_value=["cleaned insight"]),
    )

    assert result["input_count"] == 1
    assert result["output_count"] == 1
    fake_dm.delete.assert_called_once_with("m1")
    fake_dm.add_distilled.assert_called_once()


@pytest.mark.asyncio
async def test_consolidate_keeps_existing_when_llm_returns_empty_list():
    fake_dm = MagicMock(spec=DomainMemory)
    fake_dm.domain = "hiring"
    fake_dm.list_all.return_value = [
        {"id": "m1", "memory": "important insight"},
    ]
    fake_dm.add_distilled = MagicMock()

    result = await consolidate_memories(
        domain_memory=fake_dm,
        llm_consolidate=AsyncMock(return_value=[]),
    )

    assert result["output_count"] == 0
    assert "empty consolidation" in result["error"]
    fake_dm.delete.assert_not_called()
    fake_dm.add_distilled.assert_not_called()


@pytest.mark.asyncio
async def test_consolidate_keeps_existing_when_distilled_write_fails():
    fake_dm = MagicMock(spec=DomainMemory)
    fake_dm.domain = "hiring"
    fake_dm.list_all.return_value = [
        {"id": "m1", "memory": "important insight"},
    ]
    fake_dm.add_distilled = MagicMock(side_effect=[[{"id": "new-1"}], RuntimeError("write failed")])

    result = await consolidate_memories(
        domain_memory=fake_dm,
        llm_consolidate=AsyncMock(return_value=["consolidated one", "consolidated two"]),
    )

    assert result["output_count"] == 0
    assert "write failed" in result["error"]
    fake_dm.delete.assert_called_once_with("new-1")


@pytest.mark.asyncio
async def test_consolidate_keeps_existing_on_llm_failure():
    """If the LLM call raises, don't delete the existing memories."""
    fake_dm = MagicMock()
    fake_dm.domain = "hiring"
    fake_dm.list_all.return_value = [
        {"id": "m1", "memory": "important insight"},
    ]

    result = await consolidate_memories(
        domain_memory=fake_dm,
        llm_consolidate=AsyncMock(side_effect=RuntimeError("LLM down")),
    )

    # Should not delete existing memories on failure
    fake_dm.delete.assert_not_called()
    assert result.get("error") is not None

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

import api.server.services.entity_graph as entity_graph_module
from api.server.services.entity_graph import EntityGraph


@pytest.fixture
def database_mock(monkeypatch: pytest.MonkeyPatch) -> MagicMock:
    monkeypatch.delenv("ENTITY_GRAPH_MAX_DB_SIZE_MB", raising=False)
    database = MagicMock(return_value=object())
    monkeypatch.setattr(entity_graph_module.kuzu, "Database", database)
    monkeypatch.setattr(entity_graph_module.kuzu, "Connection", MagicMock())
    monkeypatch.setattr(EntityGraph, "_bootstrap_schema", lambda self: None)
    return database


@pytest.mark.parametrize("value", [None, ""])
def test_buffer_pool_defaults_to_kuzu_auto_size(
    value: str | None,
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
    database_mock: MagicMock,
) -> None:
    if value is None:
        monkeypatch.delenv("ENTITY_GRAPH_BUFFER_POOL_MB", raising=False)
    else:
        monkeypatch.setenv("ENTITY_GRAPH_BUFFER_POOL_MB", value)

    db_path = tmp_path / "graph.kuzu"
    EntityGraph(db_path)

    database_mock.assert_called_once_with(str(db_path), buffer_pool_size=0)


def test_buffer_pool_converts_megabytes_to_bytes(
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
    database_mock: MagicMock,
) -> None:
    monkeypatch.setenv("ENTITY_GRAPH_BUFFER_POOL_MB", "256")
    db_path = tmp_path / "graph.kuzu"

    EntityGraph(db_path)

    database_mock.assert_called_once_with(
        str(db_path),
        buffer_pool_size=268_435_456,
    )


@pytest.mark.parametrize("value", ["-1", "not-a-number", "true"])
def test_invalid_buffer_pool_fails_before_database_construction(
    value: str,
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
    database_mock: MagicMock,
) -> None:
    monkeypatch.setenv("ENTITY_GRAPH_BUFFER_POOL_MB", value)

    with pytest.raises(ValueError, match="ENTITY_GRAPH_BUFFER_POOL_MB"):
        EntityGraph(tmp_path / "graph.kuzu")

    database_mock.assert_not_called()


def test_max_database_size_is_explicit_and_converted_to_bytes(
    tmp_path, monkeypatch, database_mock,
) -> None:
    monkeypatch.setenv("ENTITY_GRAPH_BUFFER_POOL_MB", "64")
    monkeypatch.setenv("ENTITY_GRAPH_MAX_DB_SIZE_MB", "1024")
    path = tmp_path / "bounded.kuzu"
    EntityGraph(path)
    database_mock.assert_called_once_with(
        str(path), buffer_pool_size=64 * 1024 * 1024, max_db_size=1024 * 1024 * 1024,
    )


@pytest.mark.parametrize("value", ["", "0"])
def test_max_database_size_preserves_library_default_when_not_configured(
    value, tmp_path, monkeypatch, database_mock,
) -> None:
    monkeypatch.setenv("ENTITY_GRAPH_MAX_DB_SIZE_MB", value)
    EntityGraph(tmp_path / "default.kuzu")
    assert "max_db_size" not in database_mock.call_args.kwargs


@pytest.mark.parametrize("value", ["-1", "not-a-number", "1.5"])
def test_invalid_max_database_size_fails_before_opening(
    value, tmp_path, monkeypatch, database_mock,
) -> None:
    monkeypatch.setenv("ENTITY_GRAPH_MAX_DB_SIZE_MB", value)
    with pytest.raises(ValueError, match="ENTITY_GRAPH_MAX_DB_SIZE_MB"):
        EntityGraph(tmp_path / "invalid.kuzu")
    database_mock.assert_not_called()

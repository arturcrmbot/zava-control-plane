"""Tests for AuditLogger blob append + fall-through path.

Per plan/feature-foundry-credibility-friday-1.md TASK-028.
"""
from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest

from api.server.services.audit_logger import AuditLogger


# --- Fall-through path (no env, no blob) ------------------------------------


def test_in_memory_only_when_env_unset(monkeypatch):
    monkeypatch.delenv("AZURE_STORAGE_AUDIT_ACCOUNT", raising=False)
    audit = AuditLogger()
    audit.log("compose-exception.pre", {"workflow_id": "EXP-001"})
    audit.log("compose-exception.emitted",
              {"exception_id": "EXC-1", "workflow_id": "EXP-001"})
    entries = audit.list()
    assert len(entries) == 2
    assert entries[0]["action"] == "compose-exception.pre"
    assert entries[1]["details"]["exception_id"] == "EXC-1"
    assert audit.blob_url_for("EXP-001") is None


def test_in_memory_log_does_not_call_blob_when_no_env(monkeypatch):
    monkeypatch.delenv("AZURE_STORAGE_AUDIT_ACCOUNT", raising=False)
    audit = AuditLogger()
    # _service_client should be None; _append_to_blob is a no-op.
    assert audit._service_client is None
    audit.log("test", {"workflow_id": "X"})
    assert len(audit.list()) == 1


# --- Blob path (env set, mocked clients) -----------------------------------


@pytest.fixture
def mock_blob_setup(monkeypatch):
    """Patch DefaultAzureCredential + BlobServiceClient.

    In azure-storage-blob 12.x the regular `BlobClient` carries the append-
    blob API (`create_append_blob`, `append_block`) — there is no separate
    `AppendBlobClient` class to mock.
    """
    monkeypatch.setenv("AZURE_STORAGE_AUDIT_ACCOUNT", "apexdemo62525")
    monkeypatch.setenv("AZURE_STORAGE_AUDIT_CONTAINER", "audit-ledger")

    fake_credential = MagicMock(name="cred")
    fake_service_client = MagicMock(name="service_client")
    fake_service_client.url = "https://apexdemo62525.blob.core.windows.net"
    fake_service_client.credential = fake_credential
    # get_blob_client returns one BlobClient per (container, blob) call.
    fake_blob_client = MagicMock(name="blob_client")
    fake_blob_client.exists.return_value = False
    fake_blob_client.append_block = MagicMock()
    fake_blob_client.create_append_blob = MagicMock()
    fake_service_client.get_blob_client.return_value = fake_blob_client

    with patch("azure.identity.DefaultAzureCredential", return_value=fake_credential), \
         patch("azure.storage.blob.BlobServiceClient", return_value=fake_service_client):
        yield {
            "service": fake_service_client,
            "blob": fake_blob_client,
        }


def test_log_writes_one_append_block_per_call(mock_blob_setup):
    audit = AuditLogger()
    audit.log("compose-exception.pre", {"workflow_id": "EXP-100"})
    audit.log("compose-exception.emitted",
              {"exception_id": "EXC-9", "workflow_id": "EXP-100"})

    blob = mock_blob_setup["blob"]
    assert blob.append_block.call_count == 2
    raw = blob.append_block.call_args_list[0].args[0]
    assert isinstance(raw, bytes)
    assert raw.endswith(b"\n")
    payload = json.loads(raw.decode("utf-8"))
    assert payload["action"] == "compose-exception.pre"
    assert payload["details"]["workflow_id"] == "EXP-100"
    assert "timestamp" in payload


def test_log_creates_append_blob_once_per_workflow(mock_blob_setup):
    audit = AuditLogger()
    audit.log("a", {"workflow_id": "EXP-200"})
    audit.log("b", {"workflow_id": "EXP-200"})
    audit.log("c", {"workflow_id": "EXP-200"})

    blob = mock_blob_setup["blob"]
    # Cached after first access; subsequent calls reuse it.
    assert blob.create_append_blob.call_count == 1
    assert blob.append_block.call_count == 3


def test_blob_url_for_returns_account_url(mock_blob_setup):
    audit = AuditLogger()
    url = audit.blob_url_for("EXP-300")
    assert url == "https://apexdemo62525.blob.core.windows.net/audit-ledger/EXP-300.jsonl"


def test_log_swallows_blob_failures(mock_blob_setup):
    """Audit must never raise into the agentic workflow."""
    mock_blob_setup["blob"].append_block.side_effect = RuntimeError("network down")
    audit = AuditLogger()
    audit.log("test", {"workflow_id": "EXP-FAIL"})  # must not raise
    assert audit.list()[0]["action"] == "test"


def test_workflow_id_extraction_falls_back_to_unknown(mock_blob_setup):
    audit = AuditLogger()
    audit.log("orphan", {"some_field": 1})
    blob = mock_blob_setup["blob"]
    assert blob.append_block.call_count == 1

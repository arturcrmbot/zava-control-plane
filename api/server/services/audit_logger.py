"""Append-only audit ledger.

History: prior to 2026-05-05 this was an in-memory list (`self._entries`)
with zero persistence — the bid response's "immutable audit + 7-12 year
retention" claim had no lab-side evidence. This rewrite (per
plan/feature-foundry-credibility-friday-1.md TASK-024) dual-writes every
log entry to:

1. An in-memory list (hot read cache, identical contract to before).
2. An Azure Storage append blob, one per workflow id, in container
   `audit-ledger` (version-level-immutability enabled, see TASK-023).

The blob URL becomes the literal proof behind AC #12. Auth via
`DefaultAzureCredential`; no key auth — tenant policy disables it on the
storage account.

If `AZURE_STORAGE_AUDIT_ACCOUNT` env var is unset OR the blob client
fails to construct, falls through to in-memory only with a warning. CI
and unit tests run without the env var and observe the legacy contract.
"""
from __future__ import annotations
import json
import logging
import os
import threading
import time as _time
from typing import Any

log = logging.getLogger(__name__)

_AUDIT_CONTAINER = os.environ.get("AZURE_STORAGE_AUDIT_CONTAINER", "audit-ledger")
_AUDIT_ACCOUNT_ENV = "AZURE_STORAGE_AUDIT_ACCOUNT"
_DEFAULT_WORKFLOW_KEY = "_unknown"


class AuditLogger:
    def __init__(self) -> None:
        self._entries: list[dict] = []
        self._blob_lock = threading.Lock()
        self._append_clients: dict[str, Any] = {}  # {workflow_id: AppendBlobClient}
        self._service_client = self._build_service_client()

    # --- Blob plumbing ------------------------------------------------------

    def _build_service_client(self):
        """Construct the BlobServiceClient or return None for fall-through.

        Single point of failure for the optional cloud path: anything wrong
        (missing env, missing package, auth failure) → log once at WARN and
        keep the legacy in-memory behaviour.

        Auth: when AZURE_TENANT_ID is set we use AzureCliCredential pinned to
        that tenant — same pattern as api/server/eval/foundry_client.py.
        DefaultAzureCredential's tenant kwargs don't constrain the CLI
        sub-credential, so multi-tenant signed-in users can present a token
        for the wrong tenant and the data plane returns AuthorizationFailure
        even when the role assignment is correct.
        """
        account = os.environ.get(_AUDIT_ACCOUNT_ENV, "").strip()
        if not account:
            log.info(
                "audit_logger: %s not set; ledger is in-memory only",
                _AUDIT_ACCOUNT_ENV,
            )
            return None
        try:
            from azure.storage.blob import BlobServiceClient
        except ImportError as ex:
            log.warning("audit_logger: azure-storage-blob missing: %s", ex)
            return None
        try:
            tenant_id = os.environ.get("AZURE_TENANT_ID")
            if tenant_id:
                from azure.identity import AzureCliCredential
                cred = AzureCliCredential(tenant_id=tenant_id)
            else:
                from azure.identity import DefaultAzureCredential
                cred = DefaultAzureCredential(exclude_interactive_browser_credential=True)
            url = f"https://{account}.blob.core.windows.net"
            client = BlobServiceClient(account_url=url, credential=cred)
            log.info("audit_logger: append-blob target → %s/%s",
                     url, _AUDIT_CONTAINER)
            return client
        except Exception as ex:
            log.warning("audit_logger: blob client init failed: %s", ex)
            return None

    def _get_append_client(self, workflow_id: str):
        """Return (and cache) an append-blob-typed BlobClient for this workflow.

        Lazily creates the underlying append blob the first time. Idempotent
        if it already exists. Returns None if the service client is
        unavailable. In azure-storage-blob 12.x there is no separate
        `AppendBlobClient` class — the regular `BlobClient` exposes
        `create_append_blob()` and `append_block()`.
        """
        if self._service_client is None:
            return None
        with self._blob_lock:
            client = self._append_clients.get(workflow_id)
            if client is not None:
                return client
            try:
                blob_name = f"{workflow_id}.jsonl"
                client = self._service_client.get_blob_client(
                    container=_AUDIT_CONTAINER, blob=blob_name,
                )
                if not client.exists():
                    client.create_append_blob()
                self._append_clients[workflow_id] = client
                return client
            except Exception as ex:
                log.warning(
                    "audit_logger: append-blob client for %s failed: %s",
                    workflow_id, ex,
                )
                return None

    def _append_to_blob(self, entry: dict) -> None:
        """Append one JSON line to the workflow's blob; swallow errors.

        Audit writes must NEVER raise into the caller — losing one append
        is acceptable; breaking the agentic workflow is not.
        """
        wid = self._extract_workflow_id(entry)
        client = self._get_append_client(wid)
        if client is None:
            return
        line = (json.dumps(entry, ensure_ascii=False, default=str) + "\n").encode("utf-8")
        try:
            client.append_block(line)
        except Exception as ex:
            log.warning("audit_logger: append_block failed for %s: %s", wid, ex)

    @staticmethod
    def _extract_workflow_id(entry: dict) -> str:
        details = entry.get("details") or {}
        if isinstance(details, dict):
            for k in ("workflow_id", "workflowId"):
                v = details.get(k)
                if v:
                    return str(v)
        return _DEFAULT_WORKFLOW_KEY

    # --- Public contract (unchanged) ---------------------------------------

    def log(self, action: str, details: Any) -> None:
        entry = {
            "action": action,
            "details": details,
            "timestamp": _time.time(),
        }
        self._entries.append(entry)
        self._append_to_blob(entry)

    def list(self) -> list[dict]:
        return list(self._entries)

    # --- Helpers for routes -------------------------------------------------

    def blob_url_for(self, workflow_id: str) -> str | None:
        """Return the blob URL for a workflow's audit ledger, or None when
        the cloud path isn't configured. Used by the WorkflowDetail route to
        surface a clickable "Open in Azure Portal" link.
        """
        if self._service_client is None:
            return None
        account = os.environ.get(_AUDIT_ACCOUNT_ENV, "").strip()
        if not account:
            return None
        return (
            f"https://{account}.blob.core.windows.net/"
            f"{_AUDIT_CONTAINER}/{workflow_id}.jsonl"
        )

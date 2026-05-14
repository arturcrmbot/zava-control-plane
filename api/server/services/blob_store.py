"""Azure Blob client wrapper for CV uploads (candidate portal) and HeyGen
rendered mp4 cache.

Local dev points at Azurite via AZURE_STORAGE_CONNECTION_STRING.

See docs/superpowers/plans/2026-04-30-candidate-portal-plan.md Task 3.
"""
from __future__ import annotations

import datetime as dt

from azure.storage.blob import (
    BlobSasPermissions,
    BlobServiceClient,
    ContentSettings,
    generate_blob_sas,
)


class BlobStore:
    """Thin wrapper around `azure-storage-blob` for the candidate portal.

    Methods:
        put(name, data, *, content_type) -> str
            Uploads (overwriting) and returns the blob URL.
        sas_url(name, *, ttl_seconds) -> str
            Returns a read-only SAS-signed URL valid for `ttl_seconds`.
        exists(name) -> bool
    """

    # Pin to a Storage REST API version that Azurite supports out of the box.
    # The SDK default tracks the latest service release, which can outpace the
    # local Azurite emulator. 2024-11-04 is broadly supported by recent Azurite
    # builds.
    _API_VERSION = "2024-11-04"

    def __init__(self, *, connection_string: str, container: str) -> None:
        self.connection_string = connection_string
        self.container = container
        self._svc = BlobServiceClient.from_connection_string(
            connection_string, api_version=self._API_VERSION
        )
        # NOTE: create_container() is intentionally lazy — see _ensure_container.
        # Calling it here meant any module-level `from api.server.state import
        # app_state` would block on Azurite/Storage being reachable, which is
        # routinely false in unit tests and in any process that doesn't actually
        # touch blob storage.
        self._container_ready = False

    def _ensure_container(self) -> None:
        """Create the container on first use; idempotent and best-effort."""
        if self._container_ready:
            return
        try:
            self._svc.create_container(self.container)
        except Exception:
            # Already exists, or race with another process — fine.
            pass
        self._container_ready = True

    def put(self, name: str, data: bytes, *, content_type: str) -> str:
        self._ensure_container()
        client = self._svc.get_blob_client(self.container, name)
        client.upload_blob(
            data,
            overwrite=True,
            content_settings=ContentSettings(content_type=content_type),
        )
        return client.url

    def sas_url(self, name: str, *, ttl_seconds: int) -> str:
        client = self._svc.get_blob_client(self.container, name)
        cred = self._svc.credential
        # `cred` is a SharedKeyCredentials-like object exposing .account_key
        # when the service was built from a connection string.
        account_key = getattr(cred, "account_key", None)
        if account_key is None:
            raise RuntimeError(
                "BlobStore.sas_url requires a connection-string-backed service"
                " (no SharedKey credential available)"
            )
        sas = generate_blob_sas(
            account_name=client.account_name,
            container_name=self.container,
            blob_name=name,
            account_key=account_key,
            permission=BlobSasPermissions(read=True),
            expiry=dt.datetime.now(dt.timezone.utc) + dt.timedelta(seconds=ttl_seconds),
        )
        return f"{client.url}?{sas}"

    def exists(self, name: str) -> bool:
        return self._svc.get_blob_client(self.container, name).exists()

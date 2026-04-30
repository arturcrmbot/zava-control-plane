"""Azure Blob client wrapper for CV uploads (candidate portal) and HeyGen
rendered mp4 cache. Skeleton — implemented by Stream 1 candidate-portal
subagent (see docs/superpowers/plans/2026-04-30-candidate-portal-plan.md Task 3).

Local dev points at Azurite via AZURE_STORAGE_CONNECTION_STRING.
"""
from __future__ import annotations


class BlobStore:
    """Skeleton — see plan Task 3 for the implementation contract.

    Methods to implement:
        put(name, data, *, content_type) -> str   # returns blob URL
        sas_url(name, *, ttl_seconds) -> str       # returns SAS-signed URL
        exists(name) -> bool
    """

    def __init__(self, *, connection_string: str, container: str) -> None:
        self.connection_string = connection_string
        self.container = container

    def put(self, name: str, data: bytes, *, content_type: str) -> str:
        raise NotImplementedError("Stream 1 subagent: implement per plan Task 3")

    def sas_url(self, name: str, *, ttl_seconds: int) -> str:
        raise NotImplementedError("Stream 1 subagent: implement per plan Task 3")

    def exists(self, name: str) -> bool:
        raise NotImplementedError("Stream 1 subagent: implement per plan Task 3")

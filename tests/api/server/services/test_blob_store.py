"""Tests for the Azure Blob storage wrapper used by the candidate portal.

These tests run against Azurite locally (default well-known dev connection).
If AZURE_STORAGE_CONNECTION_STRING is unset *and* the default Azurite endpoint
is unreachable, the tests skip rather than fail.

See docs/superpowers/plans/2026-04-30-candidate-portal-plan.md Task 3.
"""
from __future__ import annotations

import os
import socket

import pytest

from api.server.services.blob_store import BlobStore


_AZURITE_DEFAULT = (
    "DefaultEndpointsProtocol=http;AccountName=devstoreaccount1;"
    "AccountKey=Eby8vdM02xNOcqFlqUwJPLlmEtlCDXJ1OUzFT50uSRZ6IFsuFq2UVErCz4I6tq/K1SZFPTOtr/KBHBeksoGMGw==;"
    "BlobEndpoint=http://127.0.0.1:10000/devstoreaccount1;"
)

CONN = os.environ.get("AZURE_STORAGE_CONNECTION_STRING", _AZURITE_DEFAULT)


def _azurite_reachable() -> bool:
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(0.5)
    try:
        sock.connect(("127.0.0.1", 10000))
        return True
    except OSError:
        return False
    finally:
        sock.close()


pytestmark = pytest.mark.skipif(
    not _azurite_reachable() and "AZURE_STORAGE_CONNECTION_STRING" not in os.environ,
    reason="Azurite not running on :10000 and AZURE_STORAGE_CONNECTION_STRING unset",
)


def test_put_and_get_url():
    bs = BlobStore(connection_string=CONN, container="test-portal")
    url = bs.put("cv-001.pdf", b"%PDF-1.4 ...", content_type="application/pdf")
    assert url.startswith(
        "http://127.0.0.1:10000/devstoreaccount1/test-portal/cv-001.pdf"
    )


def test_put_then_sas_url_with_ttl():
    bs = BlobStore(connection_string=CONN, container="test-portal")
    bs.put("video-x.mp4", b"\x00\x00\x00\x18ftyp", content_type="video/mp4")
    sas = bs.sas_url("video-x.mp4", ttl_seconds=300)
    assert "se=" in sas  # signed expiry
    assert "sig=" in sas

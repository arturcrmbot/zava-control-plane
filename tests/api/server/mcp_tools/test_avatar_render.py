"""Tests for the avatar_render MCP tool."""
from __future__ import annotations

import pytest

from api.server.mcp_tools import avatar_render
from api.server.services.render_cache import RenderCache


def test_avatar_render_cache_hit_returns_blob_url_without_calling_api(
    monkeypatch, tmp_path
):
    monkeypatch.setenv("AZURE_SPEECH_REGION", "eastus")
    monkeypatch.setenv(
        "AZURE_STORAGE_CONNECTION_STRING",
        "DefaultEndpointsProtocol=https;AccountName=x;AccountKey=Zm9v;"
        "EndpointSuffix=core.windows.net",
    )
    monkeypatch.delenv("AVATAR_TRANSPORT", raising=False)

    cache = RenderCache(db_path=tmp_path / "rc.sqlite")
    cache.put(
        content_hash="abc",
        avatar_id="lisa",
        blob_name="abc.mp4",
        blob_url="https://cached.example/abc.mp4",
    )
    monkeypatch.setattr(avatar_render, "_render_cache", lambda: cache)
    monkeypatch.setattr(
        avatar_render,
        "_speech_client",
        lambda: pytest.fail("should not call client on cache hit"),
    )
    monkeypatch.setattr(
        avatar_render,
        "_blob_store",
        lambda: pytest.fail("should not upload on cache hit"),
    )
    monkeypatch.setattr(avatar_render, "_compute_hash", lambda script, voice: "abc")

    result = avatar_render.avatar_render(script="welcome", avatar_character="lisa")
    assert result.video_url == "https://cached.example/abc.mp4"
    assert result.cached is True
    assert result.result_type == "success"


def test_avatar_render_cache_miss_renders_uploads_caches(monkeypatch, tmp_path):
    monkeypatch.setenv("AZURE_SPEECH_REGION", "eastus")
    monkeypatch.setenv(
        "AZURE_STORAGE_CONNECTION_STRING",
        "DefaultEndpointsProtocol=https;AccountName=x;AccountKey=Zm9v;"
        "EndpointSuffix=core.windows.net",
    )
    monkeypatch.delenv("AVATAR_TRANSPORT", raising=False)

    cache = RenderCache(db_path=tmp_path / "rc.sqlite")
    monkeypatch.setattr(avatar_render, "_render_cache", lambda: cache)
    monkeypatch.setattr(avatar_render, "_compute_hash", lambda script, voice: "fresh")

    render_calls: list[dict] = []

    class _FakeSpeech:
        def render(self, **kw):
            render_calls.append(kw)
            return b"\x00\x00\x00\x18ftyp-mp4-bytes"

    blob_calls: list[tuple] = []

    class _FakeBlob:
        def put(self, name, data, *, content_type):
            blob_calls.append(("put", name, data[:4], content_type))
            return f"https://blob.example/{name}"

        def sas_url(self, name, *, ttl_seconds):
            blob_calls.append(("sas_url", name, ttl_seconds))
            return f"https://blob.example/{name}?sas=signed"

    monkeypatch.setattr(avatar_render, "_speech_client", lambda: _FakeSpeech())
    monkeypatch.setattr(avatar_render, "_blob_store", lambda: _FakeBlob())

    result = avatar_render.avatar_render(
        script="welcome alice", avatar_character="lisa"
    )

    assert result.result_type == "success"
    assert result.cached is False
    assert result.video_url == "https://blob.example/fresh-lisa.mp4?sas=signed"
    # Render was called once with the right script/avatar
    assert len(render_calls) == 1
    assert render_calls[0]["script"] == "welcome alice"
    assert render_calls[0]["avatar_character"] == "lisa"
    # Blob received put + sas_url
    assert blob_calls[0][0] == "put"
    assert blob_calls[0][1] == "fresh-lisa.mp4"
    assert blob_calls[0][3] == "video/mp4"
    assert blob_calls[1][0] == "sas_url"
    # Cache row was written
    row = cache.lookup(content_hash="fresh", avatar_id="lisa")
    assert row is not None
    assert row["blob_url"] == "https://blob.example/fresh-lisa.mp4?sas=signed"


def test_avatar_render_returns_failure_when_unconfigured(monkeypatch):
    monkeypatch.delenv("AZURE_SPEECH_REGION", raising=False)
    monkeypatch.delenv("AZURE_STORAGE_CONNECTION_STRING", raising=False)
    monkeypatch.delenv("AVATAR_TRANSPORT", raising=False)

    result = avatar_render.avatar_render(script="x", avatar_character="lisa")
    assert result.result_type == "failure"
    assert "AZURE_SPEECH_REGION" in (result.error or "")


def test_avatar_render_mock_transport_returns_failure(monkeypatch):
    """AVATAR_TRANSPORT=mock short-circuits is_configured() so the canned
    mocks/heygen-mcp fallback is used instead of real Azure Speech."""
    monkeypatch.setenv("AVATAR_TRANSPORT", "mock")
    monkeypatch.setenv("AZURE_SPEECH_REGION", "eastus")
    monkeypatch.setenv(
        "AZURE_STORAGE_CONNECTION_STRING",
        "DefaultEndpointsProtocol=https;AccountName=x;AccountKey=Zm9v;"
        "EndpointSuffix=core.windows.net",
    )

    result = avatar_render.avatar_render(script="x", avatar_character="lisa")
    assert result.result_type == "failure"
    assert "mock" in (result.error or "").lower()

"""Tests for the avatar render cache (Stream 3 — avatar real)."""
from __future__ import annotations

from api.server.services.render_cache import RenderCache


def test_lookup_miss_returns_none(tmp_path):
    cache = RenderCache(db_path=tmp_path / "rc.sqlite")
    assert cache.lookup(content_hash="abc", avatar_id="lisa") is None


def test_put_then_lookup_hits(tmp_path):
    cache = RenderCache(db_path=tmp_path / "rc.sqlite")
    cache.put(
        content_hash="abc",
        avatar_id="lisa",
        blob_name="abc.mp4",
        blob_url="https://example/abc.mp4",
    )
    row = cache.lookup(content_hash="abc", avatar_id="lisa")
    assert row is not None
    assert row["blob_url"] == "https://example/abc.mp4"
    assert row["blob_name"] == "abc.mp4"
    assert row["content_hash"] == "abc"
    assert row["avatar_id"] == "lisa"


def test_put_overwrites_same_key(tmp_path):
    cache = RenderCache(db_path=tmp_path / "rc.sqlite")
    cache.put(
        content_hash="abc", avatar_id="lisa", blob_name="x.mp4", blob_url="u1"
    )
    cache.put(
        content_hash="abc", avatar_id="lisa", blob_name="x.mp4", blob_url="u2"
    )
    row = cache.lookup(content_hash="abc", avatar_id="lisa")
    assert row is not None
    assert row["blob_url"] == "u2"


def test_lookup_distinct_avatar_ids_isolated(tmp_path):
    """Same content hash, different avatars — independent rows."""
    cache = RenderCache(db_path=tmp_path / "rc.sqlite")
    cache.put(
        content_hash="abc", avatar_id="lisa", blob_name="lisa.mp4", blob_url="u-lisa"
    )
    cache.put(
        content_hash="abc", avatar_id="harry", blob_name="harry.mp4", blob_url="u-harry"
    )
    assert cache.lookup(content_hash="abc", avatar_id="lisa")["blob_url"] == "u-lisa"
    assert cache.lookup(content_hash="abc", avatar_id="harry")["blob_url"] == "u-harry"

from __future__ import annotations

import asyncio
from types import SimpleNamespace

from api.server.routes import blueprint


def test_blueprint_stream_drops_when_queue_is_full_without_raising():
    queue = asyncio.Queue(maxsize=1)
    queue.put_nowait({"type": "first"})

    blueprint._put_nowait_if_space(queue, {"type": "second"})

    assert queue.qsize() == 1
    assert queue.get_nowait() == {"type": "first"}


def test_blueprint_stream_accepts_event_when_queue_has_space():
    queue = asyncio.Queue(maxsize=1)

    blueprint._put_nowait_if_space(queue, {"type": "first"})

    assert queue.get_nowait() == {"type": "first"}


def test_blueprint_stream_queue_tracks_observatory_capacity(monkeypatch):
    monkeypatch.setattr(
        blueprint,
        "_OBSERVATORY_CAP",
        SimpleNamespace(capacity=20),
    )
    assert blueprint._make_event_queue().maxsize == 2_000

    monkeypatch.setattr(
        blueprint,
        "_OBSERVATORY_CAP",
        SimpleNamespace(capacity=10_000),
    )
    assert blueprint._make_event_queue().maxsize == 10_000

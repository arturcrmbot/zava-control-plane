from __future__ import annotations

import asyncio

from api.server.routes.blueprint import _put_nowait_if_space


def test_blueprint_stream_drops_when_queue_is_full_without_raising():
    queue = asyncio.Queue(maxsize=1)
    queue.put_nowait({"type": "first"})

    _put_nowait_if_space(queue, {"type": "second"})

    assert queue.qsize() == 1
    assert queue.get_nowait() == {"type": "first"}


def test_blueprint_stream_accepts_event_when_queue_has_space():
    queue = asyncio.Queue(maxsize=1)

    _put_nowait_if_space(queue, {"type": "first"})

    assert queue.get_nowait() == {"type": "first"}

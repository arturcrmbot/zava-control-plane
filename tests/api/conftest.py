"""Shared fixtures for the api/* test tree.

Sets DURABLE_EVENT_SECRET so /internal/durable-event tests can sign their
requests via :func:`tests.api._helpers.durable_event.signed_post`. The same
secret is used by the helper, so callers don't need to set it manually.

Also disables ChromaDB's anonymised telemetry. Chroma arrives transitively
via mem0 (``api/server/services/lessons/mem0_store.py``) and, left at its
default, every client instantiated by the lessons/dream-pass tests tries to
POST usage events to PostHog. With no reachable endpoint those sockets sit
in CLOSE_WAIT until they time out, which stalls the suite for minutes at a
time and makes runs non-hermetic. Set before any import that can construct
a Chroma client, because chromadb's pydantic ``Settings`` reads the
environment once at instantiation.

Finally, points PORTAL_DATA_DIR at a scratch directory and forces the
in-process memory backend. ``api.server.state`` resolves the Kuzu entity
graph from PORTAL_DATA_DIR at import time, defaulting to the working tree's
``data/portal``. Without this the suite opens — and writes to — whatever
portal graph the developer has accumulated locally. That is not hermetic
(results depend on local data volume) and it is not survivable: a
multi-gigabyte graph pushes RSS past what the OS will allow and pytest dies
with SIGKILL mid-run.

MEMORY_BACKEND=fallback keeps the dream-pass/lessons paths on the
in-process :class:`FallbackMemory` instead of building a real Mem0 stack.
The Mem0 path constructs a Chroma collection whose default embedding
function fetches an ONNX model over the network on first use; with no
cached model that fetch stalls the suite for minutes. ``tests/api/server/
services/replay/conftest.py`` already pins the same value for the same
reason.

All three are ``setdefault``, so an explicit value still wins when you
deliberately want real portal data or a real Mem0 backend, and tests that
exercise the other modes override them per-test via ``monkeypatch``.
"""
from __future__ import annotations

import atexit
import os
import shutil
import tempfile

os.environ.setdefault("ANONYMIZED_TELEMETRY", "False")
os.environ.setdefault("MEMORY_BACKEND", "fallback")

if "PORTAL_DATA_DIR" not in os.environ:
    _scratch_portal = tempfile.mkdtemp(prefix="zava-tests-portal-")
    os.environ["PORTAL_DATA_DIR"] = _scratch_portal
    atexit.register(shutil.rmtree, _scratch_portal, True)

import pytest

from tests.api._helpers.durable_event import DEFAULT_SECRET


@pytest.fixture(autouse=True)
def _durable_event_secret(monkeypatch):
    monkeypatch.setenv("DURABLE_EVENT_SECRET", DEFAULT_SECRET)
    yield

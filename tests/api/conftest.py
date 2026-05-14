"""Shared fixtures for the api/* test tree.

Sets DURABLE_EVENT_SECRET so /internal/durable-event tests can sign their
requests via :func:`tests.api._helpers.durable_event.signed_post`. The same
secret is used by the helper, so callers don't need to set it manually.
"""
from __future__ import annotations

import pytest

from tests.api._helpers.durable_event import DEFAULT_SECRET


@pytest.fixture(autouse=True)
def _durable_event_secret(monkeypatch):
    monkeypatch.setenv("DURABLE_EVENT_SECRET", DEFAULT_SECRET)
    yield

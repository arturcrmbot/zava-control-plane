"""Test helper: sign + post a payload to /internal/durable-event.

The route requires HMAC-SHA256 over the raw request body under
``DURABLE_EVENT_SECRET`` (see api/server/routes/internal_durable_event.py).
Tests that exercise the route's behaviour (not the auth gate itself) use
this helper to keep the signing boilerplate out of the assertions.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import os


DEFAULT_SECRET = "test-durable-event-secret"


def setup_secret(monkeypatch, secret: str = DEFAULT_SECRET) -> str:
    monkeypatch.setenv("DURABLE_EVENT_SECRET", secret)
    return secret


def signed_post(client, body: dict, *, path: str = "/internal/durable-event"):
    """POST ``body`` JSON to ``path`` with a valid X-Durable-Event-Signature.

    Reads the secret from the live ``DURABLE_EVENT_SECRET`` env var so callers
    that have already set it (via monkeypatch or otherwise) get a matching sig.
    Falls back to :data:`DEFAULT_SECRET` when unset (callers that forgot to
    set up the env will see a 401 from the route, not a misleading mismatch).
    """
    raw = json.dumps(body).encode("utf-8")
    secret = os.getenv("DURABLE_EVENT_SECRET") or DEFAULT_SECRET
    sig = hmac.new(secret.encode("utf-8"), raw, hashlib.sha256).hexdigest()
    return client.post(
        path,
        content=raw,
        headers={
            "Content-Type": "application/json",
            "X-Durable-Event-Signature": sig,
        },
    )

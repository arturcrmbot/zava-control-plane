"""Shared HTTP client factory for ``api.server.mcp_tools``.

A hung mock — TCP-accepted but never-replied — would otherwise tie up
the request worker indefinitely because module-level ``httpx.post(...)``
calls inherit no default timeout. Centralising client construction here
lets every tool share a single sensible default and gives us one place
to tweak it later (retry policy, transport, instrumentation).

Use the context-managed factories instead of calling ``httpx.post`` /
``httpx.get`` directly:

>>> from api.server.mcp_tools._http import get_client
>>> with get_client() as client:
...     resp = client.post(url, json=payload)

Both factories accept an optional ``timeout`` override (seconds); the
default is :data:`DEFAULT_TIMEOUT_SECONDS`.

Plan: ``plan/refactor-repo-coherence-remediation-1.md`` — e4.
"""
from __future__ import annotations

import httpx


DEFAULT_TIMEOUT_SECONDS: float = 5.0


def get_client(timeout: float = DEFAULT_TIMEOUT_SECONDS) -> httpx.Client:
    """Return a synchronous :class:`httpx.Client` with a bounded timeout.

    Use as a context manager so the underlying connection pool is
    closed deterministically::

        with get_client() as client:
            resp = client.post(url, json=payload)

    ``timeout`` applies to connect, read, write, and pool acquisition
    (``httpx.Timeout`` constructed from a single float).
    """
    return httpx.Client(timeout=timeout)


def get_async_client(
    timeout: float = DEFAULT_TIMEOUT_SECONDS,
) -> httpx.AsyncClient:
    """Async counterpart to :func:`get_client`.

    Mirrors the sync factory's bounded-timeout default so async tools
    cannot accidentally inherit ``None`` (= no timeout) by going
    through ``httpx.AsyncClient()`` directly.
    """
    return httpx.AsyncClient(timeout=timeout)

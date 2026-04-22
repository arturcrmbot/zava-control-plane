"""Unit tests for api.shared.otel.init_otel."""
from __future__ import annotations
import importlib
import os

import pytest


def _fresh_otel_module():
    """Reload the module so the internal _initialized flag resets between tests."""
    import api.shared.otel as mod
    return importlib.reload(mod)


def test_noop_when_conn_string_missing(monkeypatch):
    monkeypatch.delenv("APPLICATIONINSIGHTS_CONNECTION_STRING", raising=False)
    mod = _fresh_otel_module()
    # Should return silently, not raise, and not attempt Azure Monitor import.
    mod.init_otel("test-service")
    assert mod._initialized is True


def test_idempotent_when_conn_string_missing(monkeypatch):
    monkeypatch.delenv("APPLICATIONINSIGHTS_CONNECTION_STRING", raising=False)
    mod = _fresh_otel_module()
    mod.init_otel("test-service")
    # Second call must also be a no-op.
    mod.init_otel("test-service")
    assert mod._initialized is True


def test_idempotent_when_conn_string_set(monkeypatch):
    """Second call should not reinvoke configure_azure_monitor even if env set."""
    monkeypatch.setenv(
        "APPLICATIONINSIGHTS_CONNECTION_STRING",
        "InstrumentationKey=00000000-0000-0000-0000-000000000000;",
    )
    mod = _fresh_otel_module()

    call_count = {"n": 0}

    def fake_configure_azure_monitor(**kwargs):
        call_count["n"] += 1

    import azure.monitor.opentelemetry as am
    monkeypatch.setattr(am, "configure_azure_monitor", fake_configure_azure_monitor)

    mod.init_otel("test-service")
    mod.init_otel("test-service")
    assert call_count["n"] == 1
    assert mod._initialized is True

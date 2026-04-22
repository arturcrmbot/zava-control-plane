# src/shared/otel.py
"""
Single entry point for OpenTelemetry → Azure Monitor (Foundry App Insights).

Called from FastAPI lifespan and function_app.py module-load. Idempotent and
a no-op when APPLICATIONINSIGHTS_CONNECTION_STRING is not set, so dev/test
runs don't require a connection string.
"""
from __future__ import annotations
import os
import threading

_lock = threading.Lock()
_initialized = False


def init_otel(service_name: str) -> None:
    """Configure Azure Monitor OTEL export. Idempotent; no-op if conn string absent."""
    global _initialized
    with _lock:
        if _initialized:
            return
        conn = os.getenv("APPLICATIONINSIGHTS_CONNECTION_STRING")
        if not conn:
            _initialized = True
            return
        from azure.monitor.opentelemetry import configure_azure_monitor
        configure_azure_monitor(
            connection_string=conn,
            resource_attributes={"service.name": service_name},
        )
        # FastAPI / httpx auto-instrumentation is wired by configure_azure_monitor's
        # distro, but calling explicitly is safe (idempotent) and documents intent.
        try:
            from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor
            HTTPXClientInstrumentor().instrument()
        except Exception:
            pass
        try:
            from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor  # noqa: F401
            # FastAPIInstrumentor.instrument_app(app) happens per-app in main.py if needed;
            # configure_azure_monitor's auto-instrumentation covers the global case.
        except Exception:
            pass
        _initialized = True

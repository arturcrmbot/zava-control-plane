# src/server/mcp_tools/_otel.py
"""
Shared @traced_tool decorator for Fleet Manager MCP tools.

Wraps the tool body in `tool.server.{name}` span with status propagation based on
the returned ToolResult.result_type. Stacks beneath @define_tool from the GHCP SDK.
"""
from __future__ import annotations
import functools
from opentelemetry import trace
from opentelemetry.trace import Status, StatusCode


_tracer = trace.get_tracer("wpp.mcp_tools")


def traced_tool(name: str):
    """Decorator factory. Wraps a tool function body in a `tool.server.{name}` span."""
    def _decorator(fn):
        @functools.wraps(fn)
        def _wrapped(*args, **kwargs):
            with _tracer.start_as_current_span(f"tool.server.{name}") as span:
                span.set_attribute("wpp.tool.name", name)
                try:
                    result = fn(*args, **kwargs)
                except Exception as ex:
                    span.record_exception(ex)
                    span.set_status(Status(StatusCode.ERROR, str(ex)))
                    raise
                # ToolResult.result_type is "success" | "error" | etc.
                rtype = getattr(result, "result_type", None)
                if rtype and rtype != "success":
                    span.set_status(Status(StatusCode.ERROR, str(rtype)))
                return result
        return _wrapped
    return _decorator

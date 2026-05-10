# src/server/mcp_tools/_otel.py
"""
Shared @traced_tool decorator for Fleet Manager MCP tools.

Wraps the tool body in `tool.server.{name}` span with status propagation based on
the returned ToolResult.result_type. Stacks beneath @define_tool from the GHCP SDK.

Governance — TASK-017 of plan/feature-agent-governance-toolkit-1.md:
the decorator routes every call through ``GovernanceKernel.evaluate_tool_call``
BEFORE the wrapped function runs. Phase 2 runs in log-only mode (a deny
is recorded as a span attribute but the tool body still executes); Phase
6 (TASK-047) raises ``GovernanceDenied`` on a deny when ``AGT_ENFORCE=1``.
"""
from __future__ import annotations
import functools
import os
from opentelemetry import trace
from opentelemetry.trace import Status, StatusCode


_tracer = trace.get_tracer("zava.mcp_tools")


def _resolve_actor(span) -> str:
    """Pick the calling agent's id.

    Priority:
      1. ``apex.agent.label`` attribute on the current OTel span — set by
         the upstream graph executor when an agent invokes the tool.
      2. ``AGT_DEFAULT_ACTOR`` env var (matches the chokepoint in
         ``api/functions/graphs/_common.py``).
      3. ``"unknown-agent"`` fallback so a missing actor still produces
         a decision.
    """
    attrs = getattr(span, "attributes", None) or {}
    label = None
    try:
        label = attrs.get("apex.agent.label") if hasattr(attrs, "get") else None
    except Exception:  # pragma: no cover — defensive against SDK churn
        label = None
    if label:
        return str(label)
    return os.environ.get("AGT_DEFAULT_ACTOR", "unknown-agent")


def _extract_args_from_call(args, kwargs) -> dict:
    """Best-effort extraction of the tool's request payload.

    Most MCP tools wrapped by @define_tool receive a single Pydantic
    ``params`` argument. We turn it into a dict for the kernel context;
    if the call shape is unfamiliar we just stash the kwargs.
    """
    if args:
        first = args[0]
        if hasattr(first, "model_dump"):
            try:
                return first.model_dump()  # type: ignore[no-any-return]
            except Exception:
                return {}
        if isinstance(first, dict):
            return dict(first)
    return dict(kwargs) if kwargs else {}


def traced_tool(name: str):
    """Decorator factory. Wraps a tool function body in a `tool.server.{name}`
    span AND a governance-kernel evaluation guard (Phase 2+)."""
    def _decorator(fn):
        @functools.wraps(fn)
        def _wrapped(*args, **kwargs):
            with _tracer.start_as_current_span(f"tool.server.{name}") as span:
                span.set_attribute("zava.tool.name", name)

                # Governance guard — TASK-017. Local import keeps the
                # kernel a soft dep at decorator-application time so a
                # missing governance package can't break test collection.
                try:
                    from api.server.services.governance import (  # noqa: WPS433
                        GovernanceDenied,
                        kernel,
                    )
                except ImportError:  # pragma: no cover — defensive
                    GovernanceDenied = None  # type: ignore[assignment]
                    kernel = None  # type: ignore[assignment]

                if kernel is not None:
                    actor = _resolve_actor(span)
                    decision = kernel().evaluate_tool_call(
                        actor=actor,
                        tool=name,
                        args=_extract_args_from_call(args, kwargs),
                        workflow_id=None,
                    )
                    span.set_attribute(
                        "apex.governance.decision_id", decision.decision_id
                    )
                    span.set_attribute(
                        "apex.governance.policy_version", decision.policy_version
                    )
                    span.set_attribute(
                        "apex.governance.allowed", decision.allowed
                    )
                    if decision.rule_id:
                        span.set_attribute(
                            "apex.governance.rule_id", decision.rule_id
                        )
                    span.set_attribute(
                        "apex.governance.enforcement_mode",
                        decision.enforcement_mode,
                    )
                    if (
                        decision.enforcement_mode == "enforce"
                        and not decision.allowed
                        and GovernanceDenied is not None
                    ):
                        raise GovernanceDenied(decision)

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

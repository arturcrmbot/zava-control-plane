"""AGT-aware permission handler for the GHCP SDK pre-tool hook.

Plan: plan/refactor-substrate-agentic-segments-1.md TASK-001 / TASK-002.

The SDK invokes a ``PermissionHandler`` callable before every tool call.
``approve_all`` (the SDK default) rubber-stamps everything. This handler
delegates to the governance kernel's ``evaluate_tool_call`` so the
per-skill capability allow-list, value ceiling, reversibility, and
kill-switch checks fire on each MCP call originating from the model.

Behaviour:

- When ``AGT_ENFORCE`` is off, the kernel runs in ``log_only`` mode:
  every call is evaluated and recorded in the decision registry, but
  the handler always approves so behaviour is unchanged.
- When ``AGT_ENFORCE`` is on, ``evaluate_tool_call`` raises
  ``GovernanceDenied`` on deny; the handler catches that, writes an
  audit row, and returns a ``denied-by-rules`` result whose ``feedback``
  / ``message`` carry the human-readable reason. The SDK forwards that
  back to the model as a tool error so the agent loop can adapt.

Only MCP / custom-tool permission kinds are gated. Other permission
kinds (shell, file write, URL fetch, memory, hook confirmation) are
not used by our session config; they fall through to ``approve`` so a
future SDK change that surfaces one of them doesn't deadlock the
loop. If the audience for this handler expands, gate those explicitly.
"""
from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from copilot.session import (
    PermissionRequest,
    PermissionRequestResult,
)

from api.server.services.governance.kernel import (
    GovernanceDenied,
    kernel as _governance_kernel,
)

if TYPE_CHECKING:
    pass


log = logging.getLogger(__name__)


# SDK PermissionRequest.kind values that are MCP-shaped — those carry
# tool_name + server_name + args. Other kinds (shell, write, read,
# url, memory, hook) are not used by our session config; approving
# them keeps the loop unblocked if the SDK ever surfaces one we
# haven't gated. Values per copilot.generated.session_events
# .PermissionRequestKind (Enum strings).
_MCP_KINDS: frozenset[str] = frozenset({"mcp", "custom-tool"})


def _compose_tool_id(req: PermissionRequest) -> str | None:
    """Map an SDK PermissionRequest to a ``tools.yaml`` ``id`` string.

    Manifest ids are dot-delimited (``claim.lookup``, ``ocr.extract``,
    ``concur_travel.policy.get_policy``). The SDK gives us
    ``server_name`` + ``tool_name``. Joining with ``.`` matches the
    convention used in ``data/policies/tools.yaml``.

    Returns ``None`` for non-MCP request kinds so callers can fall
    through to approve.
    """
    # request.kind is a PermissionRequestKind enum on the live SDK but
    # tests may pass the raw string. Normalise to the string form.
    kind = getattr(req.kind, "value", req.kind)
    if kind not in _MCP_KINDS:
        return None
    server = (req.server_name or "").strip()
    name = (req.tool_name or "").strip()
    if name and server:
        return f"{server}.{name}"
    return name or None


class AGTPermissionHandler:
    """SDK PermissionHandler that delegates to the governance kernel.

    Bound per session — the constructor takes the ``skill_label`` that
    owns this session and the ``workflow_id`` so audit / decision-
    registry rows can be filtered by workflow. The instance itself is
    callable with the SDK's ``(request, invocation)`` signature.
    """

    def __init__(self, *, skill_label: str, workflow_id: str | None = None) -> None:
        self._actor = skill_label
        self._workflow_id = workflow_id

    def __call__(
        self,
        request: PermissionRequest,
        invocation: dict[str, str],
    ) -> PermissionRequestResult:
        tool_id = _compose_tool_id(request)
        if tool_id is None:
            # Non-MCP permission kind. Approve to avoid loop deadlock.
            return PermissionRequestResult(kind="approved")

        kernel = _governance_kernel()
        args = request.args if isinstance(request.args, dict) else {}

        try:
            decision = kernel.evaluate_tool_call(
                actor=self._actor,
                tool=tool_id,
                args=args,
                workflow_id=self._workflow_id,
            )
        except GovernanceDenied as denied:
            # Enforce mode + deny. The kernel has already registered
            # the decision. Build a structured result the SDK can
            # forward to the model as a tool error.
            reason = denied.decision.reason or "denied by governance"
            log.info(
                "AGTPermissionHandler: deny actor=%s tool=%s rule=%s reason=%s",
                self._actor, tool_id, denied.decision.rule_id, reason,
            )
            return PermissionRequestResult(
                kind="denied-by-rules",
                feedback=reason,
                message=reason,
            )

        if decision.allowed:
            return PermissionRequestResult(kind="approved")

        # Log-only mode + deny. The kernel did not raise; we still
        # approve so behaviour is unchanged when AGT_ENFORCE is off,
        # but the decision is registered for audit.
        log.debug(
            "AGTPermissionHandler: log_only-deny actor=%s tool=%s rule=%s reason=%s",
            self._actor, tool_id, decision.rule_id, decision.reason,
        )
        return PermissionRequestResult(kind="approved")

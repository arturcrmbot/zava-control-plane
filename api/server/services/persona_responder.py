"""Persona responder service.

Subscribes to `workflow.hitl.requested` FleetEvents and closes generated-
domain HITL gates by applying the matching persona's decision policy
deterministically against the parked workflow context, then raising the
external event back to the Durable orchestrator.

A persona is considered handleable iff the suspended-event payload included
`persona`, `external_event`, and `context` fields (the persona-responder
contract — see `compose-domain` SKILL). Hand-built domains (expense /
hiring) omit these fields and route through their own UI flows
(reviewer queue, recruiter portal, candidate portal); their HITL events
are silently ignored here.

The decision policies in this module mirror the prose in each persona's
SKILL.md verbatim. When a persona's prose changes, the matching handler
here changes too. Long-term we want either:
  - codegen from the SKILL.md decision_policy paragraph, or
  - a real GHCP session per persona that evaluates the SKILL.md
    against the parked context.
v1 keeps it deterministic for predictable demos.
"""
from __future__ import annotations

import asyncio
from typing import Any, Callable, Awaitable

from api.server.services.durable_client import raise_orchestration_event
from api.shared.events import FleetEvent


# A persona handler takes the parked context dict and returns the resolving
# event payload (e.g. {"decision": "approve", "reason": "in-policy + low band"}).
PersonaHandler = Callable[[dict[str, Any]], dict[str, Any]]


def _line_manager_decide(context: dict[str, Any]) -> dict[str, Any]:
    """Mirror of api/server/personae/line_manager/SKILL.md decision_policy.

    Approve when policy_fit_check shows policy_fit == "in-policy" AND
    band in {"low", "mid"}. Otherwise reject. State which condition failed
    in one sentence in the rejection reason.
    """
    pfc = (context or {}).get("policy_fit_check") or {}
    fit = pfc.get("policy_fit")
    band = pfc.get("band")

    if not fit or not band:
        return {
            "decision": "reject",
            "reason": "missing policy_fit_check verdict",
        }

    if fit == "in-policy" and band in {"low", "mid"}:
        return {
            "decision": "approve",
            "reason": f"in-policy + {band} band",
        }

    if fit != "in-policy":
        return {
            "decision": "reject",
            "reason": f"out of policy: {pfc.get('violated_clauses') or '?'}",
        }

    return {
        "decision": "reject",
        "reason": f"in-policy but {band} band exceeds line-manager delegation",
    }


# Persona handler registry. Add an entry per persona role as new HITL
# personae get composed. Each key matches the persona's `name:` frontmatter
# in api/server/personae/<role>/SKILL.md.
PERSONA_HANDLERS: dict[str, PersonaHandler] = {
    "line_manager": _line_manager_decide,
}


async def _handle_hitl(event: FleetEvent) -> None:
    """Apply the matching persona's decision policy and raise the resolving event."""
    data = event.model_dump()
    persona = data.get("persona")
    external_event = data.get("external_event")
    instance_id = data.get("instance_id")
    context = data.get("context") or {}

    # Hand-built domains (expense / hiring) omit these fields. Their HITL
    # events are routed through dedicated UI surfaces, not this responder.
    if not (persona and external_event and instance_id):
        return

    handler = PERSONA_HANDLERS.get(persona)
    if handler is None:
        print(f"[persona_responder] no handler for persona={persona!r}; skipping")
        return

    try:
        decision_payload = handler(context)
    except Exception as ex:
        print(f"[persona_responder] handler {persona!r} failed: {ex}")
        return

    print(
        f"[persona_responder] {persona} decided "
        f"{decision_payload.get('decision')!r} for {data.get('workflow_id')} "
        f"({data.get('reason')}); raising {external_event!r}"
    )

    try:
        await raise_orchestration_event(instance_id, external_event, decision_payload)
    except Exception as ex:
        print(
            f"[persona_responder] failed to raise {external_event!r} on "
            f"instance {instance_id}: {ex}"
        )


def attach(bus) -> Callable[[], None]:
    """Subscribe the persona responder to the EventBus.

    Returns an unsubscribe callable for teardown. Wired from
    api/server/main.py lifespan.
    """
    loop = asyncio.get_event_loop()

    def _on_event(event: FleetEvent) -> None:
        if event.type != "workflow.hitl.requested":
            return
        # Schedule the async handler. The bus subscriber is sync; we hop
        # into the running event loop so the durable HTTP call doesn't
        # block the bus.
        try:
            loop.create_task(_handle_hitl(event))
        except RuntimeError:
            # No running loop \u2014 happens during process shutdown. Drop.
            pass

    return bus.on_any(_on_event)

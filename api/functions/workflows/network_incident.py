"""Durable responder that turns a network anomaly into a typed command.

The orchestration receives the failed site, its healthy neighbours (with spare
capacity) and the affected sessions from the authoritative simulation, then runs
two REAL deterministic boundaries in order:

  * **Impact Diagnosis** (``network_incident_impact_activity``) — diagnose the
    blast radius and order the affected sessions.
  * **Reroute Planning** (``network_incident_reroute_activity``) — greedily
    plan each session's assignment to a neighbour with room and emit a typed
    ``reroute_sessions`` command for the later world-application boundary.

Each boundary emits standard ``step.started`` / ``step.completed`` checkpoints so
the operator surfaces (StateStore phases, AG-UI, Blueprint) render the same phase
vocabulary the registry declares. The orchestrator deliberately does NOT emit a
terminal ``workflow.completed`` checkpoint: recovery verification is a later
world-evaluation boundary (Phase 3) that runs after FastAPI's world bridge
validates and applies the command to the real session actors.
"""
from __future__ import annotations

from collections.abc import Generator
from typing import Any

import azure.durable_functions as df

_IMPACT_DIAGNOSIS = "Impact Diagnosis"
_REROUTE_PLANNING = "Reroute Planning"


def network_incident_orchestration(
    context: df.DurableOrchestrationContext,
) -> Generator[Any, Any, dict]:
    """Two deterministic activities: diagnose impact, then plan the reroute."""
    input_dict = context.get_input() or {}
    workflow_id = input_dict.get("workflow_id", "?")
    # Stamped on every checkpoint so internal_durable_event can resolve the
    # domain on downstream FleetEvents (mirrors the generated-domain pattern).
    workflow_type = input_dict.get("type", "network-incident")
    instance_id = context.instance_id

    yield context.call_activity("checkpoint_activity_trigger", {
        "workflow_id": workflow_id, "instance_id": instance_id,
        "kind": "workflow.started", "payload": {"workflow_type": workflow_type},
    })

    # Phase: Impact Diagnosis (deterministic).
    yield context.call_activity("checkpoint_activity_trigger", {
        "workflow_id": workflow_id, "instance_id": instance_id,
        "kind": "step.started",
        "payload": {"step": _IMPACT_DIAGNOSIS, "workflow_type": workflow_type},
    })
    impact = yield context.call_activity(
        "network_incident_impact_activity_trigger", input_dict
    )
    yield context.call_activity("checkpoint_activity_trigger", {
        "workflow_id": workflow_id, "instance_id": instance_id,
        "kind": "step.completed",
        "payload": {"step": _IMPACT_DIAGNOSIS, "workflow_type": workflow_type},
    })

    # Phase: Reroute Planning (deterministic).
    yield context.call_activity("checkpoint_activity_trigger", {
        "workflow_id": workflow_id, "instance_id": instance_id,
        "kind": "step.started",
        "payload": {"step": _REROUTE_PLANNING, "workflow_type": workflow_type},
    })
    reroute = yield context.call_activity(
        "network_incident_reroute_activity_trigger",
        {
            "trace_id": input_dict.get("trace_id"),
            "diagnosis": impact.get("diagnosis"),
            "diagnosis_reasoning": impact.get("reasoning"),
        },
    )
    yield context.call_activity("checkpoint_activity_trigger", {
        "workflow_id": workflow_id, "instance_id": instance_id,
        "kind": "step.completed",
        "payload": {"step": _REROUTE_PLANNING, "workflow_type": workflow_type},
    })

    # No terminal workflow.completed here: recovery verification + effectiveness
    # is the later world-evaluation boundary (Phase 3), after the world bridge
    # applies the reroute command to the real session actors.
    return {
        "status": "completed",
        "instance_id": instance_id,
        "observation": input_dict.get("observation"),
        "command": reroute.get("command"),
        "reasoning": reroute.get("reasoning"),
    }

"""POC3 Creative Campaign orchestration — one workflow end-to-end.

10 phases per plan/feature-poc3-ai-agency-1.md:

  brief_capture (HITL)
    -> Brief Synthesis (agent)
       -> brief_approval (HITL ◆1)
          -> Insight & Audience (agent)
             -> Concept Fan-out (agent)
                -> concept_lock (HITL ◆2)
                   -> Storyboard Render (agent)
                      -> storyboard_approval (HITL ◆3)
                         -> final_signoff (HITL ◆4)
                            -> Package & Handoff (agent)

The five HITL gates (brief_capture + ◆1..◆4) are all owned by the
`creative_director` persona; the persona's `decision_policy` block
branches on `phase` to apply per-gate logic. See
api/server/personae/creative_director/SKILL.md.

Sync generator per the Azure Durable Functions Python convention.
"""
from __future__ import annotations
from collections.abc import Generator
from typing import Any

import azure.durable_functions as df

from api.shared.constants import (
    CREATIVE_BRIEF_CAPTURE_TIMEOUT,
    CREATIVE_BRIEF_APPROVAL_TIMEOUT,
    CREATIVE_CONCEPT_LOCK_TIMEOUT,
    CREATIVE_STORYBOARD_APPROVAL_TIMEOUT,
    CREATIVE_FINAL_SIGNOFF_TIMEOUT,
)


def _suspend(workflow_id: str, instance_id: str, *, phase: str,
             external_event: str, reason: str, persona: str,
             context_payload: dict, workflow_type: str) -> dict:
    """Build a `suspended` checkpoint payload that the persona responder
    + resolve route can both read. Mirrors the shape used by every other
    fleet-* orchestrator."""
    return {
        "workflow_id": workflow_id,
        "instance_id": instance_id,
        "kind": "suspended",
        "payload": {
            "reason": reason,
            "phase": phase,
            "wait_kind": "operator_review",
            "workflow_type": workflow_type,
            "persona": persona,
            "external_event": external_event,
            "context": context_payload,
        },
    }


def _publish_phase_output(workflow_id: str, instance_id: str, *,
                          slot: str, payload_data: dict) -> dict:
    """Emit a `creative.phase.output` checkpoint carrying the agentic phase's
    output dict so the FastAPI side can stash it on `workflow.payload[slot]`
    for the UI's CreativeCampaignArtefacts component to render. The slot
    name matches the keys CreativeCampaignArtefacts looks for:
    brief_synthesis, insight_audience, concept_fanout, storyboard_render,
    package_handoff."""
    # Strip the orchestrator-control fields so we only stash the agent's
    # actual output (the keys the persona's decision_policy reads).
    cleaned = {k: v for k, v in (payload_data or {}).items()
               if k not in ("workflow_id", "instance_id", "phase", "stub")}
    return {
        "workflow_id": workflow_id,
        "instance_id": instance_id,
        "kind": "creative.phase.output",
        "payload": {"slot": slot, "data": cleaned},
    }


def creative_campaign_orchestration(
    context: df.DurableOrchestrationContext,
) -> Generator[Any, Any, dict]:
    """Orchestrate the 10-step creative-campaign flow for one workflow."""
    input_dict = context.get_input() or {}
    workflow_id = input_dict.get("workflow_id", "?")
    workflow_type = input_dict.get("type", "creative-campaign")
    enriched = {**input_dict, "instance_id": context.instance_id}

    yield context.call_activity("checkpoint_activity_trigger", {
        "workflow_id": workflow_id, "instance_id": context.instance_id,
        "kind": "workflow.started",
        "payload": {"domain": "creative-campaign", "workflow_type": workflow_type},
    })

    # Publish the seed brief upfront so the UI's brief scorecard renders
    # before brief_synthesis runs (during the voice-intake suspend the
    # operator can already see what the campaign is about).
    if enriched.get("brief"):
        yield context.call_activity("checkpoint_activity_trigger", _publish_phase_output(
            workflow_id, context.instance_id,
            slot="brief", payload_data=enriched["brief"],
        ))

    # ------------------------------------------------------------------
    # Phase 1: brief_capture — multi-party voice intake (HITL).
    # The persona's brief_capture handler synthesises a deterministic
    # transcript from the seed brief in auto-close mode.
    # ------------------------------------------------------------------
    yield context.call_activity("checkpoint_activity_trigger", _suspend(
        workflow_id, context.instance_id,
        phase="brief_capture",
        external_event="voice_complete",
        reason="awaiting_brief_capture_voice",
        persona="creative_director",
        workflow_type=workflow_type,
        context_payload={"brief": enriched.get("brief")},
    ))
    voice_event = context.wait_for_external_event("voice_complete")
    voice_timer = context.create_timer(
        context.current_utc_datetime + CREATIVE_BRIEF_CAPTURE_TIMEOUT
    )
    voice_winner = yield context.task_any([voice_event, voice_timer])
    if voice_winner == voice_timer:
        yield context.call_activity("checkpoint_activity_trigger", {
            "workflow_id": workflow_id, "instance_id": context.instance_id,
            "kind": "workflow.completed",
            "payload": {"status": "timeout", "phase": "brief_capture",
                        "workflow_type": workflow_type},
        })
        return {"status": "timeout", "phase": "brief_capture"}
    voice_timer.cancel()
    enriched["brief_capture"] = voice_event.result or {}

    yield context.call_activity("checkpoint_activity_trigger", {
        "workflow_id": workflow_id, "instance_id": context.instance_id,
        "kind": "resumed",
        "payload": {"phase": "brief_capture", "workflow_type": workflow_type},
    })

    # ------------------------------------------------------------------
    # Phase 2: Brief Synthesis — agent projects transcript into
    # structured brief JSON the brief_approval gate inspects.
    # ------------------------------------------------------------------
    brief_synthesis_result = yield context.call_activity(
        "creative_brief_synthesis_activity_trigger", enriched,
    )
    enriched["brief_synthesis"] = brief_synthesis_result
    yield context.call_activity("checkpoint_activity_trigger", _publish_phase_output(
        workflow_id, context.instance_id,
        slot="brief_synthesis", payload_data=brief_synthesis_result,
    ))

    # ------------------------------------------------------------------
    # Phase 3: brief_approval — HITL ◆1.
    # ------------------------------------------------------------------
    yield context.call_activity("checkpoint_activity_trigger", _suspend(
        workflow_id, context.instance_id,
        phase="brief_approval",
        external_event="brief_approval_decision",
        reason="awaiting_brief_approval",
        persona="creative_director",
        workflow_type=workflow_type,
        context_payload={"brief_synthesis": brief_synthesis_result},
    ))
    brief_approval_event = context.wait_for_external_event("brief_approval_decision")
    brief_approval_timer = context.create_timer(
        context.current_utc_datetime + CREATIVE_BRIEF_APPROVAL_TIMEOUT
    )
    ba_winner = yield context.task_any([brief_approval_event, brief_approval_timer])
    if ba_winner == brief_approval_timer:
        yield context.call_activity("checkpoint_activity_trigger", {
            "workflow_id": workflow_id, "instance_id": context.instance_id,
            "kind": "workflow.completed",
            "payload": {"status": "timeout", "phase": "brief_approval",
                        "workflow_type": workflow_type},
        })
        return {"status": "timeout", "phase": "brief_approval"}
    brief_approval_timer.cancel()
    enriched["brief_approval_decision"] = brief_approval_event.result

    # Reject short-circuits the whole campaign — analogous to expense
    # claim's reject path. Approve continues; escalate also continues
    # (FM-aware human picks it up but the workflow keeps going).
    if (brief_approval_event.result or {}).get("decision") == "reject":
        yield context.call_activity("checkpoint_activity_trigger", {
            "workflow_id": workflow_id, "instance_id": context.instance_id,
            "kind": "workflow.completed",
            "payload": {"status": "rejected_at_brief_approval",
                        "workflow_type": workflow_type},
        })
        return {"status": "rejected", "phase": "brief_approval"}

    yield context.call_activity("checkpoint_activity_trigger", {
        "workflow_id": workflow_id, "instance_id": context.instance_id,
        "kind": "resumed",
        "payload": {"phase": "brief_approval", "workflow_type": workflow_type},
    })

    # ------------------------------------------------------------------
    # Phase 4: Insight & Audience — agent fan-out (3 sub-agents in real
    # impl; v1 single stub).
    # ------------------------------------------------------------------
    insight_result = yield context.call_activity(
        "creative_insight_audience_activity_trigger", enriched,
    )
    enriched["insight_audience"] = insight_result
    yield context.call_activity("checkpoint_activity_trigger", _publish_phase_output(
        workflow_id, context.instance_id,
        slot="insight_audience", payload_data=insight_result,
    ))

    # ------------------------------------------------------------------
    # Phase 5: Concept Fan-out — agent generates 3 routes; each route
    # carries cached/real stills + brand_fit + distinctiveness scores.
    # ------------------------------------------------------------------
    concept_result = yield context.call_activity(
        "creative_concept_fanout_activity_trigger", enriched,
    )
    enriched["concept_fanout"] = concept_result
    yield context.call_activity("checkpoint_activity_trigger", _publish_phase_output(
        workflow_id, context.instance_id,
        slot="concept_fanout", payload_data=concept_result,
    ))

    # ------------------------------------------------------------------
    # Phase 6: concept_lock — HITL ◆2. CD picks the winning route.
    # ------------------------------------------------------------------
    yield context.call_activity("checkpoint_activity_trigger", _suspend(
        workflow_id, context.instance_id,
        phase="concept_lock",
        external_event="concept_lock_decision",
        reason="awaiting_concept_lock",
        persona="creative_director",
        workflow_type=workflow_type,
        context_payload={"concept_fanout": concept_result},
    ))
    concept_event = context.wait_for_external_event("concept_lock_decision")
    concept_timer = context.create_timer(
        context.current_utc_datetime + CREATIVE_CONCEPT_LOCK_TIMEOUT
    )
    cl_winner = yield context.task_any([concept_event, concept_timer])
    if cl_winner == concept_timer:
        yield context.call_activity("checkpoint_activity_trigger", {
            "workflow_id": workflow_id, "instance_id": context.instance_id,
            "kind": "workflow.completed",
            "payload": {"status": "timeout", "phase": "concept_lock",
                        "workflow_type": workflow_type},
        })
        return {"status": "timeout", "phase": "concept_lock"}
    concept_timer.cancel()
    enriched["concept_lock_decision"] = concept_event.result
    # Publish the lock decision so the UI's concept_tiles component can
    # render the 'locked' state on the chosen route and hide the buttons.
    yield context.call_activity("checkpoint_activity_trigger", _publish_phase_output(
        workflow_id, context.instance_id,
        slot="concept_lock_decision", payload_data=concept_event.result or {},
    ))

    if (concept_event.result or {}).get("decision") == "reject":
        yield context.call_activity("checkpoint_activity_trigger", {
            "workflow_id": workflow_id, "instance_id": context.instance_id,
            "kind": "workflow.completed",
            "payload": {"status": "rejected_at_concept_lock",
                        "workflow_type": workflow_type},
        })
        return {"status": "rejected", "phase": "concept_lock"}

    yield context.call_activity("checkpoint_activity_trigger", {
        "workflow_id": workflow_id, "instance_id": context.instance_id,
        "kind": "resumed",
        "payload": {"phase": "concept_lock", "workflow_type": workflow_type},
    })

    # ------------------------------------------------------------------
    # Phase 7: Storyboard Render — agent renders 6 storyboard frames
    # for the locked route via gpt-image-2 (real) or cached fixtures (v1).
    # ------------------------------------------------------------------
    storyboard_result = yield context.call_activity(
        "creative_storyboard_render_activity_trigger", enriched,
    )
    enriched["storyboard_render"] = storyboard_result
    yield context.call_activity("checkpoint_activity_trigger", _publish_phase_output(
        workflow_id, context.instance_id,
        slot="storyboard_render", payload_data=storyboard_result,
    ))

    # ------------------------------------------------------------------
    # Phase 8: storyboard_approval — HITL ◆3.
    # ------------------------------------------------------------------
    yield context.call_activity("checkpoint_activity_trigger", _suspend(
        workflow_id, context.instance_id,
        phase="storyboard_approval",
        external_event="storyboard_approval_decision",
        reason="awaiting_storyboard_approval",
        persona="creative_director",
        workflow_type=workflow_type,
        context_payload={"storyboard_render": storyboard_result},
    ))
    sb_event = context.wait_for_external_event("storyboard_approval_decision")
    sb_timer = context.create_timer(
        context.current_utc_datetime + CREATIVE_STORYBOARD_APPROVAL_TIMEOUT
    )
    sb_winner = yield context.task_any([sb_event, sb_timer])
    if sb_winner == sb_timer:
        yield context.call_activity("checkpoint_activity_trigger", {
            "workflow_id": workflow_id, "instance_id": context.instance_id,
            "kind": "workflow.completed",
            "payload": {"status": "timeout", "phase": "storyboard_approval",
                        "workflow_type": workflow_type},
        })
        return {"status": "timeout", "phase": "storyboard_approval"}
    sb_timer.cancel()
    enriched["storyboard_approval_decision"] = sb_event.result

    if (sb_event.result or {}).get("decision") == "reject":
        yield context.call_activity("checkpoint_activity_trigger", {
            "workflow_id": workflow_id, "instance_id": context.instance_id,
            "kind": "workflow.completed",
            "payload": {"status": "rejected_at_storyboard_approval",
                        "workflow_type": workflow_type},
        })
        return {"status": "rejected", "phase": "storyboard_approval"}

    yield context.call_activity("checkpoint_activity_trigger", {
        "workflow_id": workflow_id, "instance_id": context.instance_id,
        "kind": "resumed",
        "payload": {"phase": "storyboard_approval", "workflow_type": workflow_type},
    })

    # ------------------------------------------------------------------
    # Phase 9: final_signoff — HITL ◆4. Producer authorises the bundle
    # and the Figma push.
    # ------------------------------------------------------------------
    yield context.call_activity("checkpoint_activity_trigger", _suspend(
        workflow_id, context.instance_id,
        phase="final_signoff",
        external_event="final_signoff_decision",
        reason="awaiting_final_signoff",
        persona="creative_director",
        workflow_type=workflow_type,
        context_payload={
            "storyboard_render": storyboard_result,
            "concept_fanout": concept_result,
        },
    ))
    fs_event = context.wait_for_external_event("final_signoff_decision")
    fs_timer = context.create_timer(
        context.current_utc_datetime + CREATIVE_FINAL_SIGNOFF_TIMEOUT
    )
    fs_winner = yield context.task_any([fs_event, fs_timer])
    if fs_winner == fs_timer:
        yield context.call_activity("checkpoint_activity_trigger", {
            "workflow_id": workflow_id, "instance_id": context.instance_id,
            "kind": "workflow.completed",
            "payload": {"status": "timeout", "phase": "final_signoff",
                        "workflow_type": workflow_type},
        })
        return {"status": "timeout", "phase": "final_signoff"}
    fs_timer.cancel()
    enriched["final_signoff_decision"] = fs_event.result

    if (fs_event.result or {}).get("decision") == "reject":
        yield context.call_activity("checkpoint_activity_trigger", {
            "workflow_id": workflow_id, "instance_id": context.instance_id,
            "kind": "workflow.completed",
            "payload": {"status": "rejected_at_final_signoff",
                        "workflow_type": workflow_type},
        })
        return {"status": "rejected", "phase": "final_signoff"}

    yield context.call_activity("checkpoint_activity_trigger", {
        "workflow_id": workflow_id, "instance_id": context.instance_id,
        "kind": "resumed",
        "payload": {"phase": "final_signoff", "workflow_type": workflow_type},
    })

    # ------------------------------------------------------------------
    # Phase 10: Package & Handoff — agent bundles deliverables and
    # pushes to the demo Figma file (real impl in plan Phase 6; stub
    # returns placeholder figma_file_url).
    # ------------------------------------------------------------------
    package_result = yield context.call_activity(
        "creative_package_handoff_activity_trigger", enriched,
    )
    enriched["package_handoff"] = package_result
    yield context.call_activity("checkpoint_activity_trigger", _publish_phase_output(
        workflow_id, context.instance_id,
        slot="package_handoff", payload_data=package_result,
    ))

    yield context.call_activity("checkpoint_activity_trigger", {
        "workflow_id": workflow_id, "instance_id": context.instance_id,
        "kind": "workflow.completed",
        "payload": {"workflow_type": workflow_type},
    })

    return {
        "status": "completed",
        "brief_synthesis": brief_synthesis_result,
        "insight_audience": insight_result,
        "concept_fanout": concept_result,
        "storyboard_render": storyboard_result,
        "package_handoff": package_result,
        "figma_file_url": package_result.get("figma_file_url"),
    }

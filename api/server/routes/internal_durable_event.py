from __future__ import annotations
import logging
import time
import uuid
from fastapi import APIRouter, Header, HTTPException, Request
from pydantic import BaseModel, ValidationError
from api.server.state import app_state
from api.server.services.exception_factory import (
    compose_hitl_exception, compose_validator_exception
)
from api.server.services import pending_gates
from api.server.services.webhook_auth import verify_hmac_signature
from api.shared.events import FleetEvent
from api.shared.types import Phase, OtelSpan, ActionLedgerEntry, McpCall

# inbound: requires X-Durable-Event-Signature; secret in DURABLE_EVENT_SECRET
# (HMAC-SHA256 of the raw request body, hex-encoded; "sha256=" prefix
# tolerated). Verified in :mod:`api.server.services.webhook_auth`. The
# Functions-host emitter (:mod:`api.functions.webhook`) attaches this
# header automatically when the secret is configured.
router = APIRouter(prefix="/internal")
log = logging.getLogger(__name__)

# Executor span start times, keyed by (workflow_id, executor_name) so we can
# compute end_ms when stage=complete/error arrives. Bounded with FIFO
# eviction so a workflow that misses its `complete` / `error` stage event
# (process crash, redelivery, etc.) cannot leak entries forever.
_SPAN_STARTS_MAX = 10_000
_span_starts: dict[tuple[str, str], float] = {}

# Per-workflow workflow_type cache. Populated on first checkpoint event that
# carries `workflow_type` in its payload (orchestrators stamp it onto every
# emit). Used to enrich every FleetEvent emitted on this workflow's behalf so
# /api/blueprint/stream consumers can resolve `domain` consistently — not
# just on the trickle templates. Cleared on workflow.completed /
# workflow.rejected; bounded as a backstop in case a workflow never reaches
# a terminal event.
_WORKFLOW_TYPES_MAX = 10_000
_workflow_types: dict[str, str] = {}

# Per-workflow orchestration history feeds GET /api/workflows/{id}/orchestration.
# We retain history across the workflow lifetime (the UI renders a
# finished workflow's timeline) but cap both axes so a long-running
# demo or a chatty workflow can't unbounded-grow.
_ORCH_HISTORY_WORKFLOWS_MAX = 5_000   # FIFO eviction across workflows.
_ORCH_HISTORY_PER_WID_MAX = 500       # FIFO truncate within one workflow.


def _bounded_set(d: dict, key, value, max_size: int) -> None:
    """Insertion-order FIFO eviction. dict in CPython 3.7+ preserves
    insertion order; popping the first key gives oldest-first eviction.
    Cheap and good enough for these caches."""
    if key not in d and len(d) >= max_size:
        try:
            d.pop(next(iter(d)))
        except StopIteration:
            pass
    d[key] = value


def _emit(event_type, workflow_id: str, **fields) -> None:
    """Emit a FleetEvent on the bus, automatically stamping the cached
    workflow_type for this workflow_id (if known) so downstream consumers
    can resolve `domain` without the orchestrator stamping it on every
    field."""
    if "workflow_type" not in fields:
        wt = _workflow_types.get(workflow_id)
        if wt:
            fields["workflow_type"] = wt
    app_state.bus.emit(FleetEvent(type=event_type, workflow_id=workflow_id, **fields))


class DurableEventBody(BaseModel):
    workflow_id: str
    instance_id: str | None = None
    kind: str
    payload: dict


def _ledger(wid: str, *, kind: str, actor_id: str, action: str, details: dict, revocable: bool = False) -> None:
    app_state.store.append_ledger(wid, ActionLedgerEntry(
        workflow_id=wid,
        timestamp=time.time(),
        actor_kind=kind,  # type: ignore[arg-type]
        actor_id=actor_id,
        action=action,
        revocable=revocable,
        details=details,
    ))
    # Phase 7 TASK-053: every workflow ledger event also gets hash-chained
    # into the AuditLogger so the EvidencePanel + GET /api/governance/verify
    # see the same activity the workflow timeline already shows. Before this
    # mirror the AGT chain was almost always empty (only compose_exception
    # wrote to it), so the Evidence chip was hidden on most workflows.
    # Stamps actor metadata onto details so _extract_agent_id picks it up
    # for JWS signing without changing existing _ledger call sites.
    audit_details = {
        "workflow_id": wid,
        "actor_kind": kind,
        "actor_id": actor_id,
        "revocable": revocable,
        **(details if isinstance(details, dict) else {"value": details}),
    }
    try:
        app_state.audit.log(action, audit_details)
    except (TypeError, ValueError) as exc:
        # AuditLogger._append_to_blob already swallows storage IO errors; the
        # narrow set we expect to escape is JSON-serialisation failures from
        # _canonical_entry_hash on a non-serialisable details dict. Audit
        # writes must never break the caller (workflow continuation > one
        # missed ledger row), but log loudly so we can fix the source.
        log.warning(
            "ledger: audit.log failed for %s action=%s: %s", wid, action, exc,
            exc_info=True,
        )


def _auto_resolve_open(workflow_id: str, resolved_by: str) -> None:
    """Mark every still-open exception for a workflow as resolved. Used on
    resumed / workflow.completed / workflow.rejected so the operator queue
    doesn't leak stale entries once the orchestrator has moved past HITL or
    finished the run."""
    for e in app_state.store.list_exceptions(include_resolved=False):
        if e.workflow_id == workflow_id:
            app_state.store.resolve_exception(e.id, resolved_by)


@router.post("/durable-event")
async def receive_durable_event(
    request: Request,
    x_durable_event_signature: str | None = Header(default=None),
):
    raw = await request.body()
    verify_hmac_signature(
        secret_env="DURABLE_EVENT_SECRET",
        signature=x_durable_event_signature,
        body=raw,
    )
    try:
        body = DurableEventBody.model_validate_json(raw)
    except ValidationError as exc:
        raise HTTPException(status_code=422, detail=exc.errors())
    wid = body.workflow_id
    now = time.time()

    # First-sight cache: if this event carries workflow_type, remember it for
    # all subsequent events on this workflow_id. Generated-domain orchestrators
    # stamp it on every checkpoint payload; the cache means we only need it
    # once.
    wt_in = body.payload.get("workflow_type")
    if wt_in and wid not in _workflow_types:
        _bounded_set(_workflow_types, wid, wt_in, _WORKFLOW_TYPES_MAX)

    # orchestration_history feeds GET /api/workflows/{id}/orchestration so
    # WorkflowDetail can render a finished workflow's timeline. We can't
    # drop entries on workflow.completed without breaking that view, so
    # bound (a) the per-workflow list length to keep one runaway workflow
    # from ballooning memory, and (b) the dict cardinality to keep
    # uvicorn --reload + long demos from leaking state across cycles.
    hist = app_state.orchestration_history.get(wid)
    if hist is None:
        if len(app_state.orchestration_history) >= _ORCH_HISTORY_WORKFLOWS_MAX:
            try:
                app_state.orchestration_history.pop(
                    next(iter(app_state.orchestration_history))
                )
            except StopIteration:
                pass
        hist = []
        app_state.orchestration_history[wid] = hist
    hist.append({"kind": body.kind, "payload": body.payload, "at": now})
    if len(hist) > _ORCH_HISTORY_PER_WID_MAX:
        # FIFO: keep the most recent N events. The UI shows the full
        # history but is happy with the last 500 in practice; truncating
        # the head loses old phase.started entries which are also in the
        # phase table on the workflow record itself.
        del hist[: len(hist) - _ORCH_HISTORY_PER_WID_MAX]
    app_state.hub.broadcast("orchestration", {
        "kind": body.kind, "workflow_id": wid, "payload": body.payload
    })

    if body.kind == "workflow.started":
        # Emit BOTH the legacy workflow.started (consumers haven't migrated
        # yet) and the rich durable.workflow.started the observatory +
        # recorder expect. The substrate-fix design names durable.* as
        # canonical; workflow.started stays as a deprecated alias for
        # one release so existing subscribers keep working.
        _emit("workflow.started", wid)
        _emit("durable.workflow.started", wid)
        _ledger(wid, kind="agent", actor_id="orchestrator",
                action="workflow.started", details={})

    elif body.kind == "step.started":
        step = body.payload.get("step")
        if step:
            # Idempotent: Durable Functions may replay; skip if phase exists.
            if not any(p.name == step for p in app_state.store.get_phases(wid)):
                app_state.store.append_phase(wid, Phase(
                    workflow_id=wid, name=step,  # type: ignore[arg-type]
                    status="in_progress", started_at=now,
                ))
            # Sync the workflow's current_phase so the UI reflects progression
            # past Intake. The orchestrator advances through phases internally,
            # but nothing was lifting that state up to the workflow record.
            w = app_state.store.get_workflow(wid)
            if w:
                w.current_phase = step  # type: ignore[assignment]
            # Emit both legacy + canonical names. Observatory consumes the
            # canonical durable.step.started; legacy alias kept until
            # consumers migrate.
            _emit("workflow.phase.started", wid, phase=step)
            _emit("durable.step.started", wid, phase=step, step=step)

    elif body.kind == "step.completed":
        step = body.payload.get("step")
        dur = body.payload.get("duration_ms", 0)
        if step:
            app_state.store.update_phase(wid, step, status="completed", completed_at=now)
            _ledger(wid, kind="agent", actor_id=f"phase:{step}",
                    action=f"phase.completed:{step}", details={"duration_ms": dur})
            _emit("workflow.phase.completed", wid, phase=step, durationMs=dur)
            _emit("durable.step.completed", wid, phase=step, step=step, duration_ms=dur)

    elif body.kind == "executor.invoked":
        name = str(body.payload.get("name", "?"))
        stage = body.payload.get("stage")
        etype = str(body.payload.get("type", "?"))
        # Emit on the bus before the bookkeeping so the observatory can
        # render the executor pulse in near-real-time.
        # Skill label: for agent executors the `name` IS the skill identity
        # (e.g. "agent_rag_classifier"); strip the conventional "agent_"
        # prefix so the page renders the bare skill folder name. Validators
        # also surface as `skill` so the orbit lights up the validator
        # node distinctly. Deterministic executors leave skill null.
        skill_label = None
        if etype == "agent":
            skill_label = name[len("agent_"):] if name.startswith("agent_") else name
        elif etype == "validator":
            skill_label = name
        # Per-call tool labels come via a separate `tool.invoked` webhook
        # the agent wrapper fires per TOOL_EXECUTION_*; this branch is for
        # the executor pulse itself, not the tool fan-out.
        attrs = body.payload.get("attributes") or {}
        _emit(
            "durable.executor.invoked", wid,
            name=name,
            executor_type=etype,
            stage=stage,
            phase=body.payload.get("stage_label") or body.payload.get("phase"),
            skill=attrs.get("skill") or attrs.get("skill_label") or skill_label,
            tool=attrs.get("tool"),
            duration_ms=int(body.payload.get("duration_ms", 0)),
        )
        if stage == "start":
            _bounded_set(_span_starts, (wid, name), now, _SPAN_STARTS_MAX)
        elif stage in ("complete", "error"):
            dur_ms = int(body.payload.get("duration_ms", 0))
            dur_s = dur_ms / 1000.0
            start = _span_starts.pop((wid, name), now - dur_s)
            app_state.store.append_span(OtelSpan(
                trace_id=wid,  # group all spans under the workflow id as trace
                span_id=uuid.uuid4().hex[:16],
                name=f"executor.{name}",
                start_ms=start * 1000,
                end_ms=(start + dur_s) * 1000,
                attributes={
                    "workflow.id": wid,
                    "executor.name": name,
                    "executor.type": etype,
                },
                status="error" if stage == "error" else "ok",
            ))
            # Synthesize an MCP-call entry per executor so the Timeline tab
            # populates with per-step records. The actual HTTP traffic happens
            # inside GHCP SDK tool invocations and isn't currently captured —
            # this gives the operator the same per-step inspection surface
            # (executor name, type, phase, duration, outcome) for both agents
            # and validators / deterministic steps.
            phase = body.payload.get("stage_label") or body.payload.get("phase")
            request_preview: dict = {"executor": name, "type": etype}
            if phase:
                request_preview["phase"] = phase
            extra = body.payload.get("attributes")
            if isinstance(extra, dict):
                request_preview.update(
                    {k: v for k, v in extra.items() if k not in ("tool",)}
                )
            inferred_url = (
                f"local://tool/{extra.get('tool')}" if isinstance(extra, dict) and extra.get("tool")
                else f"local://executor/{name}"
            )
            response_preview: dict = {
                "duration_ms": dur_ms,
                "outcome": "error" if stage == "error" else "ok",
            }
            app_state.store.append_mcp_call(McpCall(
                workflow_id=wid,
                timestamp=now,
                tool=name,
                url=inferred_url,
                method="EXEC",
                request=request_preview,
                response=response_preview,
                status_code=500 if stage == "error" else 200,
                duration_ms=dur_ms,
            ))

    elif body.kind == "mcp.call":
        p = body.payload
        app_state.store.append_mcp_call(McpCall(
            workflow_id=wid,
            timestamp=now,
            tool=p.get("tool", "?"),
            url=p.get("url", ""),
            method=p.get("method", "POST"),
            request=p.get("request", {}),
            response=p.get("response", {}),
            status_code=int(p.get("status_code", 0)),
            duration_ms=int(p.get("duration_ms", 0)),
        ))
        # Phase 7 TASK-053: write a compact governance record into the
        # AuditLogger hash chain so the EvidencePanel "decisions" chip
        # has something to resolve. We deliberately strip the request /
        # response blobs (they're already on the McpCall surface and
        # would balloon the chain), keeping just the routing facts +
        # the governance decision_id / policy_version envelope. No-op
        # when the emitter didn't attach a `governance` block (legacy
        # call sites).
        gov = p.get("governance") if isinstance(p.get("governance"), dict) else None
        if gov and isinstance(gov.get("decision_id"), str) and gov["decision_id"]:
            app_state.audit.log("mcp.call", {
                "workflow_id": wid,
                "tool": p.get("tool", "?"),
                "status_code": int(p.get("status_code", 0)),
                "duration_ms": int(p.get("duration_ms", 0)),
                "governance": {
                    "decision_id": gov.get("decision_id"),
                    "policy_version": gov.get("policy_version"),
                    "allowed": gov.get("allowed"),
                    "rule_id": gov.get("rule_id"),
                    "action": gov.get("action"),
                    "enforcement_mode": gov.get("enforcement_mode"),
                    "actor": gov.get("actor"),
                },
            })

    elif body.kind == "tool.invoked":
        # Per-tool fan-out from the agent wrapper's TOOL_EXECUTION_*
        # session callback. Translates to durable.executor.invoked with
        # tool name populated, so the observatory orbit can flare the
        # skill -> tool edge in near-real time. Replays losslessly via
        # the recorder.
        p = body.payload or {}
        _emit(
            "durable.executor.invoked", wid,
            name=f"tool:{p.get('tool', '?')}",
            executor_type="tool",
            stage=p.get("stage"),
            skill=p.get("skill"),
            tool=p.get("tool"),
            duration_ms=int(p.get("duration_ms", 0)),
        )

    elif body.kind == "claim_routed":
        verdict = (body.payload.get("verdict") or "").lower()
        if verdict in {"green", "amber", "red"}:
            _emit(
                f"claim.routed.{verdict}",  # type: ignore[arg-type]
                wid,
                routed_to=body.payload.get("routed_to"),
                escalation_tier=body.payload.get("escalation_tier"),
            )

    elif body.kind == "validator.blocked":
        compose_validator_exception(
            app_state.store, wid,
            body.payload.get("validator") or body.payload.get("name", "unknown"),
            body.payload.get("reason", "validation failed"),
        )
        _ledger(wid, kind="agent",
                actor_id=f"validator:{body.payload.get('name', 'unknown')}",
                action="validator.blocked",
                details={"reason": body.payload.get("reason", "validation failed")})
        # Emit both legacy + canonical. The validator-blocked event is
        # what the page uses to flash the red line on the orbit.
        _emit(
            "workflow.exception.detected", wid,
            category="validator-blocked", severity="high",
        )
        _emit(
            "durable.validator.blocked", wid,
            name=body.payload.get("name", "unknown"),
            reason=body.payload.get("reason", "validation failed"),
        )

    elif body.kind == "suspended":
        # Platform contract: every suspended event declares a `wait_kind` —
        # `operator_review` (someone in our org must act; goes on the operator
        # exception queue, ages against our SLA) or `external_party` (someone
        # outside our org must act; admin sees it as informational only, no
        # exception composed). Default to operator_review for safety on any
        # legacy suspended events that haven't been updated yet.
        reason = body.payload.get("reason", "approval")
        wait_kind = body.payload.get("wait_kind", "operator_review")
        is_external_party = wait_kind == "external_party"
        if not is_external_party:
            compose_hitl_exception(app_state.store, wid, reason)
        _ledger(wid, kind="agent", actor_id="orchestrator",
                action="suspended",
                details={"reason": reason, "wait_kind": wait_kind})
        # Cache the active gate so the operator-resolve route knows which
        # external_event to raise on the orchestration when this exception
        # is closed. Cleared on resumed / workflow.completed below.
        pending_gates.record(
            wid,
            phase=body.payload.get("phase"),
            external_event=body.payload.get("external_event"),
        )
        w = app_state.store.get_workflow(wid)
        if w:
            w.status = "awaiting_hitl"
            # Stash neutral metadata for downstream consumers. Domain-specific
            # surfaces (recruiter portal, reviewer queue) translate these into
            # domain-friendly copy; the generic admin shell uses the wait_kind
            # alone ("Awaiting external party" vs "Awaiting operator review").
            w.metadata = dict(w.metadata or {})
            w.metadata["awaiting_reason"] = reason
            w.metadata["wait_kind"] = wait_kind
        # Forward persona-responder fields onto the FleetEvent. Generated
        # domains stash `persona`, `external_event`, and `context` in the
        # suspended payload so the responder can close the gate without a
        # human in the loop. Hand-built domains (expense / hiring) omit
        # these fields, so the responder ignores their HITL events.
        # Inject `phase` into the context dict so multi-gate personae
        # (e.g. creative_director) can branch on it. The orchestrator
        # carries `phase` at the same level as `context` in its suspended
        # payload; merging it into `context` here means SKILL.md
        # decision_policy blocks can read `context["phase"]` without
        # caring about the FleetEvent shape.
        _enriched_context = dict(body.payload.get("context") or {})
        _phase = body.payload.get("phase")
        if _phase and "phase" not in _enriched_context:
            _enriched_context["phase"] = _phase
        _emit(
            "workflow.hitl.requested", wid,
            reason=reason, wait_kind=wait_kind,
            instance_id=body.instance_id,
            persona=body.payload.get("persona"),
            external_event=body.payload.get("external_event"),
            context=_enriched_context,
        )
        # Canonical durable.suspended carries the same payload so the
        # observatory can render the pause + the recorder can capture it.
        _emit(
            "durable.suspended", wid,
            reason=reason, wait_kind=wait_kind,
            phase=body.payload.get("phase"),
            persona=body.payload.get("persona"),
            external_event=body.payload.get("external_event"),
        )

    elif body.kind == "resumed":
        _ledger(wid, kind="agent", actor_id="orchestrator",
                action="resumed", details={})
        # Gate is closed; drop its cache entry so a stale pending row
        # doesn't bleed into a later suspend on a different gate.
        pending_gates.clear(wid)
        w = app_state.store.get_workflow(wid)
        if w:
            w.status = "in_progress"
            # Clear the awaiting markers so the UI doesn't keep showing the
            # wait state after the orchestration has resumed.
            if w.metadata:
                w.metadata = {k: v for k, v in w.metadata.items()
                              if k not in {"awaiting_reason", "wait_kind"}}
        # When the orchestrator resumes via raiseEvent, the HITL exception that
        # gated the suspension is defunct. Resolve any still-open exceptions
        # for this workflow so the operator queue doesn't leak stale entries.
        _auto_resolve_open(wid, "auto-resolved:resumed")
        # Canonical durable.resumed lights the orbit ring back up after the
        # persona responder closes the gate.
        _emit("durable.resumed", wid, phase=body.payload.get("phase"))

    elif body.kind == "agent_output":
        # POC2 §4.21 AG-UI: cross-process bridge for structured agent
        # outputs. The Functions-host triage executor emits this with
        # {"agent": "cv_crystalliser", "output": {profile, component_spec, ...}};
        # we lift it onto the workflow ledger so WorkflowDetail can render
        # the candidate scorecard.
        p = body.payload or {}
        agent = str(p.get("agent") or "")
        output = p.get("output") or {}
        if agent and isinstance(output, dict):
            app_state.store.append_agent_output(wid, agent, output)

    elif body.kind == "creative.phase.output":
        # POC3 Phase 5: per-phase output stash for the creative-campaign
        # WorkflowDetail surface. The orchestrator emits one of these after
        # every agentic phase carrying {slot, data}; we merge into
        # workflow.payload[slot] so CreativeCampaignArtefacts can read the
        # brief scorecard, concept tiles, storyboard strip, etc. without
        # waiting for the workflow to complete.
        p = body.payload or {}
        slot = str(p.get("slot") or "")
        data = p.get("data") or {}
        if slot:
            w = app_state.store.get_workflow(wid)
            if w is not None:
                # Workflow.payload is a dict[str, Any] on every domain. Merge
                # this slot in (overwriting prior value for the same slot).
                if not isinstance(w.payload, dict):
                    w.payload = {}
                w.payload[slot] = data
                app_state.store.upsert_workflow(w)
        # Emit a lightweight observatory event so the SSE stream / blueprint
        # mind-map can pulse the right phase ring.
        _emit("creative.phase.output", wid, slot=slot)

    elif body.kind in {
        "concept_lock_decision",
        "brief_approval_decision",
        "storyboard_approval_decision",
        "final_signoff_decision",
    }:
        # POC3 Phase 5: UI-driven HITL gate resolution for creative-campaign.
        # The CreativeCampaignArtefacts component's "Lock route" button (and
        # the equivalent Approve/Reject buttons for the other three gates)
        # POST here directly with the decision payload; we raise the
        # corresponding Durable orchestration event so the workflow advances.
        # The persona auto-close path (used by the demo's autonomous loop)
        # goes via persona_responder instead — both code paths converge on
        # the same wait_for_external_event in the orchestrator.
        from api.server.services.durable_client import raise_orchestration_event
        from api.server.services import pending_gates as _pending
        w = app_state.store.get_workflow(wid)
        if w is not None:
            payload_to_raise = dict(body.payload or {})
            # Stash the decision onto workflow.payload so the UI's
            # CreativeCampaignArtefacts component reflects the locked
            # state immediately (same shape the orchestrator would emit
            # via creative.phase.output once Functions is in the loop).
            if not isinstance(w.payload, dict):
                w.payload = {}
            w.payload[body.kind] = payload_to_raise
            app_state.store.upsert_workflow(w)
            if w.orchestration_instance_id:
                try:
                    await raise_orchestration_event(
                        w.orchestration_instance_id, body.kind, payload_to_raise,
                    )
                except Exception as ex:
                    print(f"[creative] failed to raise {body.kind} for {wid}: {ex}")
            _ledger(wid, kind="human",
                    actor_id=str(payload_to_raise.get("resolved_by") or "operator"),
                    action=f"creative.{body.kind}",
                    details=payload_to_raise)
            _auto_resolve_open(wid, f"auto-resolved:{body.kind}")
            _pending.clear(wid)

    elif body.kind == "offer_letter_ready":
        # Cross-process bridge: agent_offer_personaliser renders the offer
        # letter PDF in the Functions worker, then sends this webhook so
        # FastAPI's app_state gets workflow.metadata.offer_letter_url set
        # before the orchestrator suspends at awaiting_offer_approval.
        # Without this the candidate portal sits forever showing
        # "Offer letter is being generated…" because the worker's app_state
        # write was process-local.
        p = body.payload or {}
        offer_letter_url = p.get("offer_letter_url")
        wf = app_state.store.get_workflow(wid)
        if wf and offer_letter_url:
            wf.metadata = dict(wf.metadata or {})
            wf.metadata["offer_letter_url"] = offer_letter_url
            app_state.store.upsert_workflow(wf)

    elif body.kind == "onboarding_video_ready":
        # Cross-process bridge: agent_onboarding renders the avatar video
        # in the Functions worker, then sends this webhook so FastAPI's
        # app_state gets workflow.metadata.onboarding_video_url updated.
        # Without this the candidate portal sits forever showing
        # "Welcome video being prepared" because the worker's app_state
        # write was process-local.
        p = body.payload or {}
        video_url = p.get("video_url")
        wf = app_state.store.get_workflow(wid)
        if wf and video_url:
            wf.metadata = dict(wf.metadata or {})
            wf.metadata["onboarding_video_url"] = video_url
            app_state.store.upsert_workflow(wf)

    elif body.kind == "agent.completed":
        # Cross-process bridge: agent.completed is emitted in the Functions
        # host's _wrapper.run_agent_session and arrives here as a webhook.
        # Four downstream consumers:
        #   1. The bus — api.server.eval.online_subscriber scores it.
        #   2. portal_orchestration — issues magic-link + email when
        #      cv_crystalliser passes the shortlist threshold.
        #   3. The workflow ledger — store.append_agent_reasoning persists
        #      the full trace (messages + tool_calls + extracted_json) so
        #      the admin Traces tab and any domain view can show what the
        #      AI thought, not just that it ran.
        #   4. economics.compute() — needs a gen_ai.generate_content span
        #      with `gen_ai.usage.*` attributes in *this* process's store.
        #      The wrapper's own OTEL span lives in the Functions host
        #      process, so we synthesize one here from the webhook payload.
        payload = {k: v for k, v in (body.payload or {}).items() if k != "type"}
        app_state.store.append_agent_reasoning(wid, payload)
        usage = payload.get("usage") or {}
        in_tok = usage.get("input_tokens")
        out_tok = usage.get("output_tokens")
        # Fallback: GHCP SDK frequently doesn't surface `usage` on
        # response events. When that happens, estimate token counts so
        # cost telemetry isn't silently zeroed out. Estimate inputs as
        # the union of everything that crosses the model boundary:
        #   - the skill SKILL.md (system message, 2-5k chars typically)
        #   - the user prompt
        #   - tool call args + results that the model sees back
        #   - inline image attachments (~1.1k tokens/image for low-detail
        #     gpt-4.1 vision; we use a fixed 1100 token allowance per
        #     attachment which is closer to reality than chars/4 of zero)
        # Conversion: ~4 chars/token (standard tiktoken English+code
        # approximation). `gen_ai.usage.source` records provenance.
        usage_source = "sdk"
        if in_tok is None:
            input_chars = len(payload.get("prompt") or "")
            input_chars += int(payload.get("skill_chars") or 0)
            for tc in payload.get("tool_calls") or []:
                input_chars += len(str(tc.get("args") or ""))
                input_chars += len(str(tc.get("result") or ""))
            in_tok = max(1, input_chars // 4)
            in_tok += 1100 * int(payload.get("attachment_count") or 0)
            usage_source = "estimated_from_chars"
        if out_tok is None:
            out_tok = max(1, len(payload.get("response_text") or "") // 4)
            usage_source = "estimated_from_chars"
        latency_ms = int(payload.get("latency_ms") or 0)
        end_ms = now * 1000
        start_ms = end_ms - latency_ms
        attrs: dict = {
            "workflow.id": wid,
            "gen_ai.system": "github_copilot",
            "gen_ai.request.model": payload.get("model") or "gpt-4.1",
            "gen_ai.agent.name": payload.get("agent_label") or "finance-agent",
            "gen_ai.usage.input_tokens": int(in_tok),
            "gen_ai.usage.output_tokens": int(out_tok),
            "gen_ai.usage.source": usage_source,
        }
        if payload.get("agent_label"):
            attrs["zava.skill"] = payload["agent_label"]
        app_state.store.append_span(OtelSpan(
            trace_id=wid,
            span_id=uuid.uuid4().hex[:16],
            name="gen_ai.generate_content",
            start_ms=start_ms,
            end_ms=end_ms,
            attributes=attrs,
        ))
        # Working-memory capture bridge — see Memory Layer Visualisation
        # plan. The Functions-host wrapper calls WorkingMemoryCapture
        # locally too, but that writes into the Functions process's own
        # _DEFAULT store, invisible to this process's /api/memory route.
        # Re-capture here from the same payload so the FastAPI process's
        # app_state.working_memory_store sees LLM agent activity.
        try:
            from api.server.services.lessons.working_memory_capture import (
                WorkingMemoryCapture,
            )
            WorkingMemoryCapture(store=app_state.working_memory_store).on_agent_completed(
                workflow_id=wid,
                agent_skill=str(payload.get("agent_label") or "unknown"),
                response_text=str(payload.get("response_text") or ""),
                tool_calls=payload.get("tool_calls") or [],
                used_lesson_ids=payload.get("used_lesson_ids") or [],
            )
        except Exception:
            log.exception("agent.completed: working-memory capture bridge failed")
        _emit("agent.completed", wid, **payload)

    elif body.kind == "workflow.completed":
        _ledger(wid, kind="agent", actor_id="orchestrator",
                action="workflow.completed", details={})
        w = app_state.store.get_workflow(wid)
        if w:
            w.status = "completed"
        _auto_resolve_open(wid, "auto-resolved:completed")
        # Canonical durable.workflow.completed marks the orbit terminal.
        # Legacy workflow.resolved kept for the existing UI consumer.
        _emit("durable.workflow.completed", wid, status="completed")
        _emit("workflow.resolved", wid, resolution="completed")
        # Drop the workflow_type cache entry; the workflow is done.
        _workflow_types.pop(wid, None)
        for k in [k for k in _span_starts if k[0] == wid]:
            _span_starts.pop(k, None)
        pending_gates.clear(wid)

    elif body.kind == "log.action":
        # Ledger-only event from the UI (Fork/Rollback illustrative stubs).
        # Must not mutate workflow.status or current_phase.
        _ledger(wid, kind="human",
                actor_id=body.payload.get("by") or "operator",
                action=str(body.payload.get("action") or "log.action"),
                details={})

    elif body.kind == "workflow.rejected":
        _ledger(wid, kind="human",
                actor_id=body.payload.get("by") or "operator",
                action="workflow.rejected",
                details={"reason": body.payload.get("reason", "operator rejected")})
        app_state.bus.emit(FleetEvent(
            type="workflow.resolved", workflow_id=wid, resolution="rejected"
        ))
        # C3: top-level workflow.failed makes the FM exception widget +
        # cosmic-lens completion handler treat rejection as a terminal
        # failure rather than a benign resolution.
        _emit("workflow.failed", wid, reason=body.payload.get("reason", "operator rejected"))
        w = app_state.store.get_workflow(wid)
        if w:
            w.status = "failed"
            # NOTE: legacy invoice-p2p code used to overwrite current_phase
            # to "Approval" here; that was a P2P-specific assumption that's
            # now wrong for hiring (Interview/Offer rejection) and the six
            # fleet-* domains (each has its own gate names). Keep
            # current_phase as whatever it was when the rejection landed.
            #
            # Clear the awaiting markers so the WorkflowDetail header tile
            # shows the terminal "Rejected" status instead of a stale
            # "Awaiting operator review" pill from when the gate was open.
            if w.metadata:
                w.metadata = {k: v for k, v in w.metadata.items()
                              if k not in {"awaiting_reason", "wait_kind"}}
            w.metadata = dict(w.metadata or {})
            w.metadata["rejected_at_phase"] = w.current_phase
            w.metadata["rejected_by"] = body.payload.get("by") or "operator"
        _auto_resolve_open(wid, "auto-resolved:rejected")
        pending_gates.clear(wid)
        # Drop the workflow_type cache entry + any leftover span starts
        # for this workflow; it has reached a terminal state. Mirrors the
        # cleanup on workflow.completed above. Without this, rejected
        # workflows accumulate forever in the per-process caches.
        _workflow_types.pop(wid, None)
        for k in [k for k in _span_starts if k[0] == wid]:
            _span_starts.pop(k, None)

    return {"received": True}

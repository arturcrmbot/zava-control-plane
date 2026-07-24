from __future__ import annotations
import datetime as dt
import logging
import math
import time
from fastapi import APIRouter, HTTPException
from api.server.state import app_state
from api.server.services import economics, exception_narrative
from api.shared.types import Workflow
from api.shared import domains as _registry

router = APIRouter(prefix="/api/workflows")
log = logging.getLogger(__name__)

_TERMINAL_PHASE_STATUSES = {"completed", "failed"}
_MIN_PLAUSIBLE_UNIX_SECONDS = 946684800.0  # 2000-01-01T00:00:00Z


def _timestamp(value, fallback: float) -> float:
    if value is None:
        return float(fallback)
    if isinstance(value, str):
        try:
            parsed = dt.datetime.fromisoformat(value.replace("Z", "+00:00"))
            return parsed.timestamp()
        except ValueError:
            return float(fallback)
    try:
        return float(value)
    except (TypeError, ValueError):
        return float(fallback)


def _first(mapping: dict, *keys: str):
    return next((mapping[key] for key in keys if mapping.get(key) is not None), None)


def _build_timeline_rows(
    workflow: Workflow,
    *,
    phases=None,
    spans=None,
    mcp_calls=None,
) -> list[dict]:
    """Build the shared, chronological workflow execution transcript."""
    created_at = float(workflow.created_at)
    lifecycle_row = {
        "id": f"workflow:{workflow.id}",
        "ts": created_at,
        "kind": "workflow",
        "label": "workflow.started",
        "status": "started",
        "currentPhase": workflow.current_phase,
        "startedAt": created_at,
    }
    rows: list[dict] = [lifecycle_row]

    timeline_phases = list(
        phases if phases is not None else app_state.store.get_phases(workflow.id)
    )
    phase_completion_rows: dict[str, dict] = {}
    for index, phase in enumerate(timeline_phases):
        data = phase.model_dump(by_alias=True, mode="json")
        started = getattr(phase, "started_at", None)
        completed = getattr(phase, "completed_at", None)
        status = getattr(phase, "status", "?")
        timestamp = (
            completed
            if status in _TERMINAL_PHASE_STATUSES and completed is not None
            else started
        )
        duration_ms = (
            (float(completed) - float(started)) * 1_000
            if started is not None and completed is not None
            else None
        )
        phase_row = {
            "id": f"phase:{index}:{phase.name}",
            "ts": _timestamp(timestamp, created_at),
            "kind": "phase",
            "label": phase.name,
            "status": status,
            "startedAt": started,
            "completedAt": completed,
            "completed_at": completed,
            "durationMs": duration_ms,
            "agentId": data.get("agentId"),
            "toolCalls": data.get("toolCalls", []),
            "spanIds": data.get("spanIds", []),
        }
        rows.append(phase_row)
        if status in _TERMINAL_PHASE_STATUSES:
            phase_completion_rows[f"phase.completed:{phase.name}"] = phase_row

    timeline_spans = spans if spans is not None else app_state.store.get_spans(workflow.id)
    span_rows: dict[int, dict] = {}
    for index, span in enumerate(timeline_spans):
        attributes = dict(span.attributes or {})
        started_at = float(span.start_ms) / 1_000
        completed_at = float(span.end_ms) / 1_000
        executor_type = _first(
            attributes,
            "executor.type",
            "zava.executor.type",
        )
        executor_name = _first(
            attributes,
            "executor.name",
            "zava.executor.name",
        )
        skill = _first(attributes, "zava.skill", "skill.name", "executor.skill", "agent.skill")
        agent = _first(
            attributes,
            "agent.name",
            "agent.label",
            "gen_ai.agent.name",
        )
        if agent is None and executor_type == "agent":
            agent = executor_name
        model = _first(attributes, "gen_ai.request.model", "llm.model", "model")
        if executor_type == "agent" or agent is not None or skill is not None or model is not None:
            span_kind = "agent"
        elif executor_type == "tool" or _first(attributes, "zava.tool.name", "tool.name"):
            span_kind = "tool"
        else:
            span_kind = "system"
        tokens_in = _first(
            attributes,
            "gen_ai.usage.input_tokens",
            "gen_ai.usage.prompt_tokens",
            "tokens.in",
        )
        tokens_out = _first(
            attributes,
            "gen_ai.usage.output_tokens",
            "gen_ai.usage.completion_tokens",
            "tokens.out",
        )
        cost_usd = _first(
            attributes,
            "gen_ai.usage.cost_usd",
            "gen_ai.cost_usd",
            "cost.usd",
        )
        span_row = {
            "id": f"span:{span.span_id or index}",
            "ts": started_at,
            "kind": span_kind,
            "label": span.name,
            "name": span.name,
            "status": span.status,
            "agent": agent,
            "skill": skill,
            "model": model,
            "startedAt": started_at,
            "completedAt": completed_at,
            "completed_at": completed_at,
            "durationMs": float(span.end_ms) - float(span.start_ms),
            "tokens": (
                (tokens_in or 0) + (tokens_out or 0)
                if tokens_in is not None or tokens_out is not None
                else None
            ),
            "tokensIn": tokens_in,
            "tokensOut": tokens_out,
            "costUsd": cost_usd,
            "traceId": span.trace_id,
            "spanId": span.span_id,
            "parentSpanId": span.parent_span_id,
            "attributes": attributes,
        }
        span_rows[index] = span_row
        rows.append(span_row)

    for index, call in enumerate(
        mcp_calls if mcp_calls is not None else app_state.store.get_mcp_calls(workflow.id)
    ):
        status = "ok" if 200 <= call.status_code < 400 else "error"
        tool_call_id = call.tool_call_id
        row = {
            "id": tool_call_id or f"mcp:{index}:{call.tool}:{call.timestamp}",
            "ts": _timestamp(call.timestamp, created_at),
            "kind": "tool",
            "label": call.tool,
            "mcpCallIndex": index,
            "status": status,
            "tool": call.tool,
            "method": call.method,
            "url": call.url,
            "statusCode": call.status_code,
            "durationMs": call.duration_ms,
            "timestamp": call.timestamp,
            "resultSummary": None,
            "result_summary": None,
        }
        if tool_call_id is not None:
            row["toolCallId"] = tool_call_id
        rows.append(row)

    matched_reasoning_spans: set[int] = set()
    matched_reasoning_indices: set[int] = set()
    reasoning_entries = app_state.store.get_agent_reasoning(workflow.id)

    def _agent_identity(value) -> str | None:
        if value is None:
            return None
        identity = str(value).strip().lower().replace("_", "-")
        for prefix in ("executor.", "agent.", "agent-"):
            if identity.startswith(prefix):
                identity = identity[len(prefix):]
        return identity or None

    def _span_agent_identity(span) -> str | None:
        attributes = dict(span.attributes or {})
        identity = _first(
            attributes,
            "zava.skill",
            "skill.name",
            "executor.skill",
            "agent.skill",
            "gen_ai.agent.name",
            "agent.name",
            "agent.label",
        )
        if identity is None and _first(attributes, "executor.type", "zava.executor.type") == "agent":
            identity = _first(attributes, "executor.name", "zava.executor.name")
        return _agent_identity(identity)

    def _span_category(span) -> str | None:
        if span.name == "gen_ai.generate_content":
            return "gen_ai"
        attributes = dict(span.attributes or {})
        if _first(attributes, "executor.type", "zava.executor.type") == "agent":
            return "executor"
        return None

    def _normalized_phase(value) -> str | None:
        if value is None:
            return None
        phase = str(value).strip().lower().replace("_", "-")
        return phase or None

    def _span_phase_value(span):
        attributes = dict(span.attributes or {})
        return _first(
            attributes,
            "workflow.phase",
            "zava.workflow.phase",
            "phase",
            "stage.label",
        )

    def _span_phase(span) -> str | None:
        return _normalized_phase(_span_phase_value(span))

    def _span_agent_run_ids(span) -> set[str]:
        attributes = dict(span.attributes or {})
        return {
            str(attributes[key])
            for key in (
                "gen_ai.agent.run.id",
                "gen_ai.agent.run_id",
                "agent.run.id",
                "agent_run_id",
                "gen_ai.response.id",
            )
            if attributes.get(key) is not None
        }

    def _span_parent_invocation_ids(span) -> set[str]:
        attributes = dict(span.attributes or {})
        return {
            str(attributes[key])
            for key in ("zava.invocation.id", "invocation.id")
            if attributes.get(key) is not None
        }

    def _span_invocation_ids(span) -> set[str]:
        return _span_agent_run_ids(span) | _span_parent_invocation_ids(span)

    def _reasoning_agent_run_ids(reasoning: dict) -> set[str]:
        return {
            str(reasoning[key])
            for key in (
                "agent_run_id",
                "agentRunId",
                "response_id",
                "responseId",
            )
            if reasoning.get(key) is not None
        }

    def _reasoning_parent_invocation_ids(reasoning: dict) -> set[str]:
        return {
            str(reasoning[key])
            for key in ("invocation_id", "invocationId")
            if reasoning.get(key) is not None
        }

    def _reasoning_invocation_ids(reasoning: dict) -> set[str]:
        return (
            _reasoning_agent_run_ids(reasoning)
            | _reasoning_parent_invocation_ids(reasoning)
        )

    def _reasoning_temporal_context(
        reasoning: dict,
    ) -> tuple[float | None, float | None]:
        started = _first(reasoning, "started_at", "startedAt")
        completed = _first(
            reasoning,
            "completed_at",
            "completedAt",
            "timestamp",
        )
        latency = _first(reasoning, "latency_ms", "latencyMs")
        started_at = (
            _timestamp(started, created_at)
            if started is not None
            else None
        )
        completed_at = (
            _timestamp(completed, created_at)
            if completed is not None
            else None
        )
        if started_at is None and completed_at is not None and latency is not None:
            started_at = completed_at - float(latency) / 1_000
        return started_at, completed_at

    def _legacy_reasoning_candidates_for_span(span_index: int) -> list[int]:
        span = timeline_spans[span_index]
        if _span_category(span) != "executor" or _span_invocation_ids(span):
            return []
        span_phase = _span_phase(span)
        if span_phase is None:
            return []
        span_start = float(span.start_ms) / 1_000
        span_end = float(span.end_ms) / 1_000
        candidates: list[int] = []
        for reasoning_index, reasoning in enumerate(reasoning_entries):
            if reasoning_index in matched_reasoning_indices:
                continue
            if _reasoning_invocation_ids(reasoning):
                continue
            if _normalized_phase(reasoning.get("phase")) != span_phase:
                continue
            started_at, completed_at = _reasoning_temporal_context(reasoning)
            if started_at is None and completed_at is None:
                continue
            reasoning_start = started_at if started_at is not None else completed_at
            reasoning_end = completed_at if completed_at is not None else started_at
            if span_end < reasoning_start - 1.0 or span_start > reasoning_end + 1.0:
                continue
            candidates.append(reasoning_index)
        return candidates

    def _identity_match_rank(
        expected: str | None,
        actual: str | None,
    ) -> int | None:
        if expected is None or actual is None:
            return None
        if expected == actual:
            return 0
        shorter, longer = sorted((expected, actual), key=len)
        suffix_tokens = shorter.split("-")
        if (
            len(suffix_tokens) >= 3
            and longer.endswith(f"-{shorter}")
        ):
            return 1
        return None

    def _phase_less_identity_match_rank(
        expected: str | None,
        actual: str | None,
    ) -> int | None:
        if expected is None or actual is None:
            return None
        if expected == actual:
            return 0
        shorter, longer = sorted((expected, actual), key=len)
        if len(shorter.split("-")) == 1 and longer.split("-")[0] == shorter:
            return 1
        return None

    def _phase_less_reasoning_candidates_for_span(span_index: int) -> list[int]:
        span = timeline_spans[span_index]
        if _span_category(span) != "executor" or _span_invocation_ids(span):
            return []
        if _span_phase(span) is not None:
            return []
        span_identity = _span_agent_identity(span)
        if span_identity is None:
            return []
        span_start = float(span.start_ms) / 1_000
        span_end = float(span.end_ms) / 1_000
        candidates: list[int] = []
        for reasoning_index, reasoning in enumerate(reasoning_entries):
            if reasoning_index in matched_reasoning_indices:
                continue
            if _normalized_phase(reasoning.get("phase")) is not None:
                continue
            reasoning_identity = _agent_identity(
                _first(reasoning, "agent_label", "agentLabel")
            )
            if _phase_less_identity_match_rank(reasoning_identity, span_identity) is None:
                continue
            started_at, completed_at = _reasoning_temporal_context(reasoning)
            if started_at is None and completed_at is None:
                continue
            reasoning_start = started_at if started_at is not None else completed_at
            reasoning_end = completed_at if completed_at is not None else started_at
            if span_end < reasoning_start - 1.0 or span_start > reasoning_end + 1.0:
                continue
            candidates.append(reasoning_index)
        return candidates

    def _matching_span_indices(
        agent_label: str,
        started_at: float | None,
        completed_at: float | None,
        phase: str | None,
        agent_run_ids: set[str],
        parent_invocation_ids: set[str],
        reasoning_index: int,
    ) -> list[int]:
        candidates: list[tuple[int, int, float, int]] = []
        identity = _agent_identity(agent_label)
        reasoning_phase = _normalized_phase(phase)
        for span_index, span in enumerate(timeline_spans):
            category = _span_category(span)
            if category is None:
                continue
            span_agent_run_ids = _span_agent_run_ids(span)
            span_parent_invocation_ids = _span_parent_invocation_ids(span)
            span_invocation_ids = _span_invocation_ids(span)
            invocation_ids = agent_run_ids | parent_invocation_ids
            span_identity = _span_agent_identity(span)
            span_phase = _span_phase(span)
            if (
                agent_run_ids
                and span_agent_run_ids
                and not agent_run_ids & span_agent_run_ids
            ):
                continue
            shared_agent_run = bool(agent_run_ids & span_agent_run_ids)
            shared_parent = bool(
                parent_invocation_ids & span_parent_invocation_ids
            )
            shared_legacy_id = bool(invocation_ids & span_invocation_ids)
            if (
                invocation_ids
                and span_invocation_ids
                and not shared_legacy_id
            ):
                continue
            if span_index in matched_reasoning_spans and not (
                category == "executor" and shared_parent
            ):
                continue
            if shared_agent_run:
                invocation_rank = 0
                identity_rank = 0
            elif shared_parent or shared_legacy_id:
                invocation_rank = 1
                identity_rank = 0
            elif reasoning_phase is None and span_phase is None:
                invocation_rank = 2
                identity_rank = _phase_less_identity_match_rank(identity, span_identity)
                if identity_rank is None:
                    continue
                if (
                    identity_rank > 0
                    and _phase_less_reasoning_candidates_for_span(span_index)
                    != [reasoning_index]
                ):
                    continue
            else:
                invocation_rank = 2
                identity_rank = _identity_match_rank(
                    identity,
                    span_identity,
                )
                if identity_rank is None:
                    if (
                        invocation_ids
                        or span_invocation_ids
                        or _legacy_reasoning_candidates_for_span(span_index)
                        != [reasoning_index]
                    ):
                        continue
                    identity_rank = 2
            span_start = float(span.start_ms) / 1_000
            span_end = float(span.end_ms) / 1_000
            if (
                reasoning_phase is not None
                and span_phase is not None
                and reasoning_phase != span_phase
            ):
                continue
            has_temporal_context = started_at is not None or completed_at is not None
            if (
                started_at is not None
                and completed_at is not None
                and (span_end < started_at - 1.0 or span_start > completed_at + 1.0)
            ):
                continue
            if (
                identity_rank > 0
                and not has_temporal_context
                and not (
                    reasoning_phase is not None
                    and span_phase == reasoning_phase
                )
            ):
                continue
            if completed_at is not None:
                distance = abs(span_end - completed_at)
            elif started_at is not None:
                distance = abs(span_start - started_at)
            else:
                distance = float(span_index)
            candidates.append((
                invocation_rank,
                identity_rank,
                distance,
                span_index,
            ))
        return [span_index for _, _, _, span_index in sorted(candidates)]

    tool_metadata_keys = (
        "name",
        "tool",
        "tool_name",
        "toolName",
        "tool_call_id",
        "toolCallId",
        "call_id",
        "callId",
        "id",
        "success",
        "status",
        "latency_ms",
        "latencyMs",
        "duration_ms",
        "durationMs",
    )

    def _tool_call_metadata(tool_calls) -> list[dict]:
        metadata: list[dict] = []
        identity_keys = {"tool_call_id", "toolCallId", "call_id", "callId"}
        for tool_call in (tool_calls or []):
            if not isinstance(tool_call, dict):
                continue
            item = {
                key: tool_call[key]
                for key in tool_metadata_keys
                if key in tool_call and key not in identity_keys
            }
            tool_call_id = _first(
                tool_call,
                "tool_call_id",
                "toolCallId",
                "call_id",
                "callId",
            )
            if tool_call_id is not None:
                item["toolCallId"] = str(tool_call_id)
            metadata.append(item)
        return metadata

    for index, reasoning in enumerate(reasoning_entries):
        usage = reasoning.get("usage") or {}
        started = _first(reasoning, "started_at", "startedAt")
        completed = _first(reasoning, "completed_at", "completedAt", "timestamp")
        latency = _first(reasoning, "latency_ms", "latencyMs")
        agent_label = _first(reasoning, "agent_label", "agentLabel") or "unknown"
        reasoning_phase = reasoning.get("phase")
        reasoning_agent_run_ids = _reasoning_agent_run_ids(reasoning)
        reasoning_parent_invocation_ids = _reasoning_parent_invocation_ids(
            reasoning
        )
        started_timestamp = _timestamp(started, created_at) if started is not None else None
        completed_timestamp = _timestamp(completed, created_at) if completed is not None else None
        if completed is None:
            for span_index in _matching_span_indices(
                agent_label,
                started_timestamp,
                None,
                reasoning_phase,
                reasoning_agent_run_ids,
                reasoning_parent_invocation_ids,
                index,
            ):
                span = timeline_spans[span_index]
                if _span_category(span) == "gen_ai":
                    completed = float(span.end_ms) / 1_000
                    completed_timestamp = float(completed)
                    break
        if started is None and completed is not None and latency is not None:
            started = _timestamp(completed, created_at) - float(latency) / 1_000
            started_timestamp = float(started)

        correlated_by_category: dict[str, int] = {}
        for span_index in _matching_span_indices(
            agent_label,
            started_timestamp,
            completed_timestamp,
            reasoning_phase,
            reasoning_agent_run_ids,
            reasoning_parent_invocation_ids,
            index,
        ):
            category = _span_category(timeline_spans[span_index])
            if category is not None and category not in correlated_by_category:
                correlated_by_category[category] = span_index
        correlated_indices = list(correlated_by_category.values())
        matched_reasoning_spans.update(correlated_indices)
        if correlated_indices:
            matched_reasoning_indices.add(index)
        correlated_rows = [span_rows[span_index] for span_index in correlated_indices]
        correlated_phases: dict[str, str] = {}
        for span_index in correlated_indices:
            phase_value = _span_phase_value(timeline_spans[span_index])
            normalized_phase = _normalized_phase(phase_value)
            if normalized_phase is not None:
                correlated_phases.setdefault(normalized_phase, str(phase_value))
        if _normalized_phase(reasoning_phase) is None and len(correlated_phases) == 1:
            reasoning_phase = next(iter(correlated_phases.values()))
        primary_span = next(
            (
                span_rows[span_index]
                for category, span_index in correlated_by_category.items()
                if category == "gen_ai"
            ),
            correlated_rows[0] if correlated_rows else None,
        )
        agent_run_id = _first(reasoning, "agent_run_id", "agentRunId")
        invocation_id = _first(reasoning, "invocation_id", "invocationId")
        run_id = agent_run_id or index
        rows.append({
            "id": f"reasoning:{run_id}",
            "ts": _timestamp(started or completed, created_at),
            "kind": "reasoning",
            "label": agent_label,
            "status": reasoning.get("status", "completed"),
            "agent": agent_label,
            **(
                {"agentRunId": agent_run_id}
                if agent_run_id is not None
                else {}
            ),
            **(
                {"invocationId": invocation_id}
                if invocation_id is not None
                else {}
            ),
            "phase": reasoning_phase,
            "coveredPhases": _first(
                reasoning,
                "covered_phases",
                "coveredPhases",
            ),
            "model": reasoning.get("model") or (primary_span or {}).get("model"),
            "skill": (primary_span or {}).get("skill"),
            "messages": reasoning.get("messages", []),
            "toolCalls": _tool_call_metadata(
                _first(reasoning, "tool_calls", "toolCalls")
            ),
            "extractedJson": _first(reasoning, "extracted_json", "extractedJson"),
            "latencyMs": latency,
            "durationMs": latency,
            "tokensIn": _first(reasoning, "tokens_in", "tokensIn") or usage.get("input_tokens"),
            "tokensOut": _first(reasoning, "tokens_out", "tokensOut") or usage.get("output_tokens"),
            "costUsd": (primary_span or {}).get("costUsd"),
            "startedAt": started,
            "completedAt": completed,
            "traceId": (primary_span or {}).get("traceId"),
            "spanId": (primary_span or {}).get("spanId"),
            "spanIds": [
                span_rows[span_index]["spanId"]
                for span_index in correlated_indices
                if span_rows[span_index].get("spanId")
            ],
        })

    if matched_reasoning_spans:
        correlated_row_ids = {
            span_rows[span_index]["id"] for span_index in matched_reasoning_spans
        }
        rows[:] = [row for row in rows if row["id"] not in correlated_row_ids]

    for index, (agent_label, output) in enumerate((workflow.agent_outputs or {}).items()):
        details = output if isinstance(output, dict) else {"value": output}
        timestamp = app_state.store.get_agent_output_recorded_at(
            workflow.id,
            agent_label,
        )
        if timestamp is None:
            timestamp = _first(
                details,
                "completed_at",
                "completedAt",
                "started_at",
                "startedAt",
                "timestamp",
                "created_at",
                "createdAt",
            )
        rows.append({
            "id": f"agent-output:{agent_label}:{index}",
            "ts": _timestamp(timestamp, created_at),
            "kind": "agentOutput",
            "label": agent_label,
            "status": details.get("status"),
            "agent": agent_label,
            "details": output,
        })

    for index, entry in enumerate(workflow.action_ledger or []):
        action = entry.action
        timestamp = created_at if action == "workflow.started" else _timestamp(entry.timestamp, created_at)
        details = entry.details or {}
        row = {
            "id": f"ledger:{entry.entry_hash or entry.decision_id or index}",
            "ts": timestamp,
            "kind": "ledger",
            "label": action,
            "status": details.get("status"),
            "actor": entry.actor_id,
            "actorKind": entry.actor_kind,
            "revocable": entry.revocable,
            "details": details,
            "timestamp": entry.timestamp,
            "decisionId": entry.decision_id,
            "policyVersion": entry.policy_version,
            "enforcementMode": entry.enforcement_mode,
            "prevHash": entry.prev_hash,
            "entryHash": entry.entry_hash,
            "actorJws": entry.actor_jws,
        }
        terminal_status = {
            "workflow.completed": "completed",
            "workflow.failed": "failed",
            "workflow.rejected": "rejected",
        }.get(action)
        if terminal_status is not None and row["status"] is None:
            row["status"] = terminal_status
        if action == "workflow.started":
            lifecycle_row.update({
                key: value
                for key, value in row.items()
                if key not in {"id", "ts", "kind", "label", "status"}
            })
            continue
        matching_phase = phase_completion_rows.get(action) or phase_completion_rows.get(
            action.replace("phase.failed:", "phase.completed:")
        )
        if matching_phase is not None:
            matching_phase.update({
                "revocable": entry.revocable,
                "timestamp": entry.timestamp,
                "decisionId": entry.decision_id,
                "policyVersion": entry.policy_version,
                "enforcementMode": entry.enforcement_mode,
                "prevHash": entry.prev_hash,
                "entryHash": entry.entry_hash,
                "actorJws": entry.actor_jws,
                "ledger": entry.model_dump(by_alias=True, mode="json"),
            })
            continue
        if action == "workflow.sub_spawned":
            row["childWorkflowId"] = _first(details, "child_workflow_id", "childWorkflowId")
            row["childWorkflowType"] = _first(details, "child_workflow_type", "childWorkflowType")
        rows.append(row)

    decisions = workflow.payload.get("decisions") if isinstance(workflow.payload, dict) else []
    for index, decision in enumerate(decisions or []):
        timestamp = _first(decision, "decided_at", "decidedAt", "timestamp")
        actor = _first(decision, "persona_role", "personaRole", "actor")
        rows.append({
            "id": f"decision:{decision.get('id', index)}",
            "ts": _timestamp(timestamp, created_at),
            "kind": "decision",
            "label": decision.get("phase") or decision.get("label") or "decision",
            "status": decision.get("status"),
            "actor": actor,
            "phase": decision.get("phase"),
            "personaRole": actor,
            "verdict": decision.get("verdict"),
            "reason": decision.get("reason"),
            "decidedAt": timestamp,
            "details": decision,
        })

    payload = workflow.payload if isinstance(workflow.payload, dict) else {}

    def _valid_evidence_timestamp(value) -> float | None:
        try:
            timestamp = float(value)
        except (TypeError, ValueError):
            return None
        return timestamp if math.isfinite(timestamp) and timestamp > 0 else None

    def _plausible_wall_clock_timestamp(value) -> float | None:
        timestamp = _valid_evidence_timestamp(value)
        if timestamp is None or timestamp < _MIN_PLAUSIBLE_UNIX_SECONDS:
            return None
        return timestamp

    def _ledger_timestamp(*actions: str) -> float | None:
        timestamps = [
            timestamp
            for entry in workflow.action_ledger or []
            if entry.action in actions
            if (timestamp := _valid_evidence_timestamp(entry.timestamp)) is not None
        ]
        return max(timestamps, default=None)

    latest_evidence_timestamp = max(
        [
            timestamp
            for timestamp in (
                *(
                    _valid_evidence_timestamp(phase.completed_at)
                    for phase in timeline_phases
                    if phase.status in _TERMINAL_PHASE_STATUSES
                ),
                *(
                    _valid_evidence_timestamp(entry.timestamp)
                    for entry in workflow.action_ledger or []
                ),
            )
            if timestamp is not None
        ],
        default=None,
    )

    terminal_label = None
    terminal_status = None
    if workflow.status == "completed":
        terminal_label = "workflow.completed"
        terminal_status = "completed"
    elif workflow.status == "failed":
        if (workflow.metadata or {}).get("rejected"):
            terminal_label = "workflow.rejected"
            terminal_status = "rejected"
        else:
            terminal_label = "workflow.failed"
            terminal_status = "failed"
    if terminal_label is not None and not any(
        row["label"] in {"workflow.completed", "workflow.failed", "workflow.rejected"}
        for row in rows
    ):
        rows.append({
            "id": f"workflow:{workflow.id}:terminal",
            "ts": latest_evidence_timestamp or created_at,
            "kind": "ledger",
            "label": terminal_label,
            "status": terminal_status,
        })

    def _output_row(
        *,
        output_id: str,
        label: str,
        details,
        fallback_timestamp: float | None,
    ) -> None:
        detail_map = details if isinstance(details, dict) else {}
        timestamp = _first(
            detail_map,
            "completed_at",
            "completedAt",
            "decided_at",
            "decidedAt",
            "timestamp",
            "created_at",
            "createdAt",
        )
        explicit_timestamp = _plausible_wall_clock_timestamp(timestamp)
        resolved_fallback = (
            _valid_evidence_timestamp(fallback_timestamp)
            or latest_evidence_timestamp
            or created_at
        )
        row = {
            "id": f"output:{output_id}",
            "ts": explicit_timestamp if explicit_timestamp is not None else resolved_fallback,
            "kind": "output",
            "label": label,
            "status": _first(detail_map, "status", "verdict"),
            "details": details,
        }
        rows.append(row)

    decision_output = payload.get("decision")
    if decision_output is not None:
        _output_row(
            output_id="decision",
            label="decision.output",
            details=decision_output,
            fallback_timestamp=(
                _ledger_timestamp("responder.decided")
                or latest_evidence_timestamp
            ),
        )
    else:
        direct_output = {
            key: payload[key]
            for key in ("command", "reasoning", "results")
            if key in payload
        }
        if direct_output:
            _output_row(
                output_id="execution",
                label="workflow.output",
                details=direct_output,
                fallback_timestamp=_ledger_timestamp(
                    "responder.decided",
                    "workflow.completed",
                    "workflow.failed",
                ) or latest_evidence_timestamp,
            )

    outcome = payload.get("outcome")
    if outcome is not None:
        _output_row(
            output_id="outcome",
            label="workflow.outcome",
            details=outcome,
            fallback_timestamp=_ledger_timestamp(
                "workflow.completed",
                "workflow.failed",
            ) or latest_evidence_timestamp,
        )

    kind_rank = {
        "workflow": 0,
        "agent": 2,
        "reasoning": 2,
        "agentOutput": 3,
        "tool": 2,
        "output": 3,
        "decision": 4,
    }

    def _rank(row: dict) -> int:
        if row["label"] in {"workflow.completed", "workflow.failed", "workflow.rejected"}:
            return 5
        if row["kind"] == "phase":
            return 3 if row.get("status") in _TERMINAL_PHASE_STATUSES else 1
        if row["kind"] == "output":
            return 4
        return kind_rank.get(row["kind"], 3)

    rows.sort(key=lambda row: (row["ts"], _rank(row), row["id"]))
    return rows


def _synthesize_workflow(workflow_id: str) -> Workflow | None:
    """Last-resort stub for a workflow that isn't in the store.

    Phase 2 of feature-fleet-domain-substrate-1 made every spawner upsert
    into app_state.store, so this path should rarely fire. Kept as a
    defensive fallback for workflows that arrive via webhook before the
    spawn path runs (e.g. recorded blueprint replays). Resolves the
    workflow_type via the domain registry by workflow_id prefix.
    """
    domain = _registry.by_prefix(workflow_id)
    if domain is None:
        return None
    excs = [
        e for e in app_state.store.list_exceptions(include_resolved=True)
        if e.workflow_id == workflow_id
    ]
    open_exc = next((e for e in excs if not e.resolved_at), None)
    created_at = min((e.created_at for e in excs), default=time.time())
    return Workflow(
        id=workflow_id,
        type=domain.workflow_type,
        status="awaiting_hitl" if open_exc else "in_progress",
        current_phase="Intake",
        created_at=created_at,
        sla_due_at=created_at + 7 * 86400,
        jurisdiction="London-Zava",
        agency="Zava",
        active_exception_id=open_exc.id if open_exc else None,
    )


@router.get("")
@router.get("/", include_in_schema=False)
async def list_workflows(status: str | None = None, phase: str | None = None,
                         agency: str | None = None, has_exception: bool | None = None):
    items = app_state.store.list_workflows(status=status, phase=phase, agency=agency, has_exception=has_exception)
    return [w.model_dump(by_alias=True) for w in items]  # camelCase for UI


@router.get("/{id}")
async def get_workflow(id: str):
    w = app_state.store.get_workflow(id)
    if not w:
        w = _synthesize_workflow(id)
        if not w:
            raise HTTPException(404)
    active = (
        app_state.store.get_exception(w.active_exception_id)
        if w.active_exception_id else None
    )
    spans = app_state.store.get_spans(id)
    mcp_calls = app_state.store.get_mcp_calls(id)
    phases = app_state.store.get_phases(id)
    eco = economics.compute(w, spans=spans, mcp_calls=mcp_calls)
    narrative = (
        exception_narrative.compose(w, active, w.action_ledger)
        if active else None
    )
    # Optional pack-owned enrichment (Task 7 Required B): any vertical may
    # register `VerticalPack.workflow_detail_hook` to expose a richer,
    # per-workflow-type detail payload than the generic fields above carry
    # (e.g. trigger evidence, ordered phase records, reasoning, HITL,
    # command, evaluation). Merged under one namespaced key with zero
    # vertical-specific branching here. A hook returning `None` is the one
    # legitimate, truthful "no applicable detail" signal; a hook that
    # *raises* has a genuine bug and that exception is left to propagate
    # (surfacing as a real error) rather than being swallowed into the same
    # success-shaped `packDetail: null` response a legitimate absence would
    # produce.
    pack_detail = None
    hook = getattr(getattr(app_state.runtime, "pack", None), "workflow_detail_hook", None)
    if hook is not None:
        pack_detail = hook(w, app_state)
    return {
        "workflow": w.model_dump(by_alias=True, exclude={"agent_reasoning"}),
        "phases": [p.model_dump(by_alias=True) for p in phases],
        "spans": [s.model_dump(by_alias=True) for s in spans],
        "amplifications": [a.model_dump(by_alias=True) for a in app_state.store.get_amplifications(id)],
        "activeException": active.model_dump(by_alias=True) if active else None,
        "mcpCalls": [c.model_dump(by_alias=True) for c in mcp_calls],
        "economics": eco,
        "narrative": narrative,
        "timeline": _build_timeline_rows(
            w,
            phases=phases,
            spans=spans,
            mcp_calls=mcp_calls,
        ),
        # Live append-blob URL for AC #12 immutable audit. None when the
        # cloud audit path isn't configured (CI / unit tests).
        "auditBlobUrl": app_state.audit.blob_url_for(id),
        "packDetail": pack_detail,
    }


@router.get("/{id}/tree")
async def get_workflow_tree(id: str, max_depth: int = 16):
    """Recursive sub-orchestrator tree (Phase 4 IP7 TASK-033, DEC-OQ5).

    Walks the ``Workflow -> Workflow`` self-relation
    (``SUB_WORKFLOW_OF`` rel table) starting from ``id`` and returns
    a JSON tree of ``{workflow_id, workflow_type, status, children: [...]}``.

    Leaf workflows (no SUB_WORKFLOW_OF rels) and ids unknown to the
    entity graph both surface a single-node tree with ``status="unknown"``
    — this is intentional: the entity graph only sees workflows that
    have been spawned via the meta-workflow path or otherwise written
    to the Workflow node table. Cycle protection short-circuits at
    ``max_depth`` and on any id revisit (defensive — graph should not
    contain cycles).
    """
    seen: set[str] = set()

    def _node(node_dict: dict | None, wid: str) -> dict:
        if node_dict is None:
            return {
                "workflow_id": wid,
                "workflow_type": None,
                "status": "unknown",
                "children": [],
            }
        return {
            "workflow_id": node_dict.get("id", wid),
            "workflow_type": node_dict.get("workflow_type"),
            "status": node_dict.get("status") or "unknown",
            "children": [],
        }

    def _walk(wid: str, depth: int) -> dict:
        if wid in seen or depth >= max_depth:
            return _node(app_state.entities.get(wid), wid)
        seen.add(wid)
        node = _node(app_state.entities.get(wid), wid)
        try:
            children = app_state.entities.linked(wid, rel="SUB_WORKFLOW_OF")
        except Exception:
            children = []
        for row in children:
            child = row.get("node") if isinstance(row, dict) else None
            child_id = child.get("id") if isinstance(child, dict) else None
            if not child_id:
                continue
            node["children"].append(_walk(child_id, depth + 1))
        return node

    return _walk(id, 0)


# ---------------------------------------------------------------------------
# Org Ops v2 — endpoints used by the live operator views (Control Room,
# Conversations, Workflow River). All three views share these.
# ---------------------------------------------------------------------------

def _function_for_workflow_type(workflow_type: str) -> str | None:
    """workflow_type -> function key (e.g. 'vendor-kyc' -> 'finance')."""
    try:
        from api.shared.functions import FUNCTIONS
    except Exception:
        return None
    for fn_key, fn_spec in FUNCTIONS.items():
        if workflow_type in (fn_spec.owns_domains or ()):
            return fn_key
    return None


def _last_actor(workflow) -> dict | None:
    """Best-effort summary of who/what last touched the workflow.

    Walks action_ledger tail (most recent first) and surfaces a small dict
    {kind: 'agent'|'tool'|'persona'|'system', name: str, at: float} so the
    operator views can show 'currently: ap_clerk thinking 4s' in the rail.
    """
    ledger = list(getattr(workflow, "action_ledger", None) or [])
    if not ledger:
        return None
    tail = ledger[-1]
    actor_id = getattr(tail, "actor_id", None) or "?"
    actor_kind = getattr(tail, "actor_kind", None) or "system"
    return {
        "kind": str(actor_kind),
        "name": str(actor_id),
        "at": float(getattr(tail, "timestamp", 0.0)),
    }


@router.get("/index/in-flight")
async def list_in_flight():
    """Every non-terminal workflow with phase, age, current actor, SLA position.

    Used by Approach A's left rail, Approach B's channel list, and Approach C's
    chip pool. Terminal statuses excluded: ``completed`` and ``failed``.
    """
    now = time.time()
    items = []
    for w in app_state.store.list_workflows():
        if w.status in {"completed", "failed"}:
            continue
        age_s = now - float(w.created_at or now)
        sla_due = float(w.sla_due_at or w.created_at + 7 * 86400)
        sla_total = max(1.0, sla_due - float(w.created_at or now))
        sla_pct = max(0.0, min(1.0, (now - float(w.created_at or now)) / sla_total))
        items.append({
            "id": w.id,
            "workflow_type": w.type,
            "function": _function_for_workflow_type(w.type),
            "status": w.status,
            "phase": w.current_phase,
            "created_at": w.created_at,
            "age_s": round(age_s, 2),
            "sla_pct": round(sla_pct, 3),
            "active_exception_id": w.active_exception_id,
            "last_actor": _last_actor(w),
        })
    items.sort(key=lambda r: (
        # awaiting_hitl first, then by age descending so the oldest unattended
        # workflow tops the list
        0 if r["status"] == "awaiting_hitl" else 1,
        -r["age_s"],
    ))
    return items


@router.get("/index/timeline/{id}")
async def workflow_timeline(id: str):
    """Chronological list of every event and canonical MCP evidence.

    Composed from: phases (deterministic per-phase rows), spans (skill/agent
    activity), mcp_calls (tool invocations), action_ledger (persona + system
    interventions), and decisions stashed on payload. Heavy MCP request and
    response payloads live once in ``mcpCalls``; new tool rows reference them
    by persistent ``toolCallId`` while legacy rows retain ``mcpCallIndex``.
    The timeline is sorted ascending for transcript rendering.
    """
    w = app_state.store.get_workflow(id)
    if not w:
        raise HTTPException(404)
    mcp_calls = app_state.store.get_mcp_calls(id)
    return {
        "workflow": w.model_dump(by_alias=True, exclude={"agent_reasoning"}),
        "mcpCalls": [call.model_dump(by_alias=True) for call in mcp_calls],
        "timeline": _build_timeline_rows(w, mcp_calls=mcp_calls),
    }

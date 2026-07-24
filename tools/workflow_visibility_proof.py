#!/usr/bin/env python3
from __future__ import annotations

import argparse
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
import json
from pathlib import Path
import sys
from typing import Any
import urllib.error
import urllib.parse
import urllib.request

from api.shared.domain_contracts import Domain
from api.shared.vertical_loader import build_runtime


class ProofError(ValueError):
    pass


_TERMINAL_LABELS = {
    "completed": "workflow.completed",
    "failed": "workflow.failed",
    "rejected": "workflow.rejected",
}
_TERMINAL_PHASE_STATUSES = {"completed", "failed", "rejected", "skipped"}
_VOLATILE_TIMELINE_FIELDS = {
    "ts",
    "timestamp",
    "startedAt",
    "started_at",
    "completedAt",
    "completed_at",
}
_VOLATILE_DURATION_FIELDS = {
    "durationMs",
    "duration_ms",
    "latencyMs",
    "latency_ms",
}
_VOLATILE_WORKFLOW_FIELDS = {
    "createdAt",
    "created_at",
    "updatedAt",
    "updated_at",
    "startedAt",
    "started_at",
    "completedAt",
    "completed_at",
}


@dataclass(frozen=True)
class WorkflowSnapshot(Sequence[dict]):
    source_mode: str
    details: tuple[dict, ...]

    def __post_init__(self) -> None:
        if self.source_mode not in {"live", "replay"}:
            raise ProofError(
                "snapshot sourceMode must be 'live' or 'replay'; "
                f"found {self.source_mode!r}"
            )
        object.__setattr__(self, "details", tuple(self.details))
        if not all(isinstance(detail, dict) for detail in self.details):
            raise ProofError("snapshot details must be objects")

    def __getitem__(self, index):
        return self.details[index]

    def __len__(self) -> int:
        return len(self.details)


@dataclass(frozen=True)
class VisibilityContract:
    domain: Domain
    persona_roles: frozenset[str] = frozenset()

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "persona_roles",
            frozenset(str(role) for role in self.persona_roles),
        )


WorkflowContract = VisibilityContract


def _safe_url(url: str) -> str:
    parsed = urllib.parse.urlsplit(url)
    host = parsed.hostname or ""
    if parsed.port is not None:
        host = f"{host}:{parsed.port}"
    return urllib.parse.urlunsplit((parsed.scheme, host, parsed.path, "", ""))


def read_url_json(url: str):
    try:
        with urllib.request.urlopen(url, timeout=15) as response:
            return json.load(response)
    except urllib.error.HTTPError as error:
        reason = f"HTTP {error.code}"
    except urllib.error.URLError:
        reason = "connection error"
    except TimeoutError:
        reason = "timeout"
    except OSError:
        reason = "I/O error"
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        reason = f"invalid JSON: {error}"
    raise ProofError(f"GET {_safe_url(url)} failed: {reason}")


def fetch_url_details(
    base_url: str,
    contracts: Mapping[str, WorkflowContract],
    *,
    workflow_ids: Iterable[str] | None = None,
    read_json=read_url_json,
) -> WorkflowSnapshot:
    base_url = base_url.rstrip("/")
    replay_meta = read_json(f"{base_url}/api/replay/meta")
    if not isinstance(replay_meta, dict):
        raise ProofError("GET /api/replay/meta did not return an object")
    source_mode = replay_meta.get("mode")
    if source_mode not in {"live", "replay"}:
        raise ProofError(
            "GET /api/replay/meta returned invalid mode; "
            "expected 'live' or 'replay'"
        )

    if workflow_ids is None:
        listing = read_json(f"{base_url}/api/workflows")
        if not isinstance(listing, list):
            raise ProofError("GET /api/workflows did not return a list")
        selected_ids: list[str] = []
        for item in listing:
            if not isinstance(item, dict):
                raise ProofError(
                    "GET /api/workflows returned a non-object item"
                )
            if item.get("type") not in contracts:
                continue
            workflow_id = str(item.get("id") or "")
            if not workflow_id:
                raise ProofError(
                    "GET /api/workflows returned an active workflow without an id"
                )
            selected_ids.append(workflow_id)
    else:
        selected_ids = [str(workflow_id) for workflow_id in workflow_ids]

    if len(set(selected_ids)) != len(selected_ids):
        raise ProofError("workflow source contains duplicate ids")

    details: list[dict] = []
    for workflow_id in selected_ids:
        encoded_id = urllib.parse.quote(workflow_id, safe="")
        detail = read_json(f"{base_url}/api/workflows/{encoded_id}")
        if not isinstance(detail, dict):
            raise ProofError(
                f"GET /api/workflows/{encoded_id} did not return an object"
            )
        workflow = detail.get("workflow")
        if (
            not isinstance(workflow, dict)
            or str(workflow.get("id") or "") != workflow_id
        ):
            raise ProofError(
                f"GET /api/workflows/{encoded_id} returned the wrong workflow"
            )
        details.append(detail)
    return WorkflowSnapshot(source_mode, tuple(details))


def save_snapshot(
    path: Path | str,
    vertical: str,
    details: Iterable[dict] | WorkflowSnapshot,
    *,
    source_mode: str | None = None,
) -> None:
    root = Path(path)
    root.mkdir(parents=True, exist_ok=True)
    if isinstance(details, WorkflowSnapshot):
        if (
            source_mode is not None
            and source_mode != details.source_mode
        ):
            raise ProofError(
                "snapshot sourceMode argument does not match captured provenance"
            )
        source_mode = details.source_mode
    if source_mode not in {"live", "replay"}:
        raise ProofError(
            "saving workflow details requires source_mode='live' or 'replay'"
        )

    detail_list = list(details)
    seen: set[str] = set()
    for detail in detail_list:
        workflow = _workflow(detail, "snapshot")
        workflow_id = str(workflow.get("id") or "")
        workflow_type = str(workflow.get("type") or "")
        if not workflow_id or not workflow_type:
            raise ProofError("snapshot workflow is missing id or type")
        if workflow_id in seen:
            raise ProofError(
                f"snapshot contains duplicate workflow id {workflow_id}"
            )
        seen.add(workflow_id)

    payload = {
        "schemaVersion": 2,
        "vertical": vertical,
        "sourceMode": source_mode,
        "details": detail_list,
    }
    (root / "workflow-details.json").write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def load_snapshot(
    path: Path | str,
    expected_vertical: str,
) -> WorkflowSnapshot:
    detail_path = Path(path) / "workflow-details.json"
    try:
        payload = json.loads(detail_path.read_text(encoding="utf-8"))
    except FileNotFoundError as error:
        raise ProofError(
            f"saved workflow details are missing: {detail_path}"
        ) from error
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ProofError(
            f"cannot read saved workflow details {detail_path}: {error}"
        ) from error
    if not isinstance(payload, dict):
        raise ProofError(f"invalid saved workflow details: {detail_path}")
    if payload.get("schemaVersion") != 2:
        raise ProofError(
            f"saved workflow details {detail_path} lacks required "
            "sourceMode provenance (schemaVersion 2); recapture it"
        )
    if payload.get("vertical") != expected_vertical:
        raise ProofError(
            "saved workflow-detail vertical "
            f"{payload.get('vertical')!r} does not match "
            f"{expected_vertical!r}"
        )
    details = payload.get("details")
    if not isinstance(details, list) or not all(
        isinstance(detail, dict) for detail in details
    ):
        raise ProofError(
            f"saved workflow details are not a list of objects: {detail_path}"
        )
    source_mode = payload.get("sourceMode")
    if source_mode not in {"live", "replay"}:
        raise ProofError(
            f"saved workflow details {detail_path} has invalid or missing "
            "sourceMode provenance"
        )
    return WorkflowSnapshot(source_mode, tuple(details))


def _registry_roles(registry: Any) -> set[str]:
    if not isinstance(registry, Mapping):
        return set()
    roles = {str(key) for key in registry}
    roles.update(
        str(value.role)
        for value in registry.values()
        if getattr(value, "role", None) is not None
    )
    return roles


def contracts_for_pack(pack: Any) -> dict[str, WorkflowContract]:
    persona_roles = frozenset(
        _registry_roles(getattr(pack, "personas", {}))
        | _registry_roles(getattr(pack, "authority", {}))
    )
    return {
        workflow_type: WorkflowContract(
            domain=domain,
            persona_roles=persona_roles,
        )
        for workflow_type, domain in pack.domains.items()
        if not domain.stub
    }


def _workflow(detail: dict, source: str) -> dict:
    workflow = detail.get("workflow")
    if not isinstance(workflow, dict):
        raise ProofError(f"{source} detail has no workflow object")
    return workflow


def _mapping(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _visible(value: Any) -> bool:
    if isinstance(value, str):
        return bool(value.strip())
    return value is not None and value not in ((), [], {})


def _declared_phase_names(domain: Domain) -> set[str]:
    phases = list(domain.phases)
    for overlay in domain.region_overlays.values():
        phases.extend(overlay.extra_phases)
    return {str(phase.name) for phase in phases}


def _declared_agent_phases(domain: Domain) -> set[str]:
    phases = list(domain.phases)
    for overlay in domain.region_overlays.values():
        phases.extend(overlay.extra_phases)
    return {
        str(phase.name)
        for phase in phases
        if phase.kind == "agent"
    }


def _declared_hitl_phases(domain: Domain) -> set[str]:
    phases = list(domain.phases)
    for overlay in domain.region_overlays.values():
        phases.extend(overlay.extra_phases)
    return {
        str(phase.name)
        for phase in phases
        if phase.kind == "hitl"
    }


def _covered_phases(
    row: Mapping[str, Any],
    *,
    source: str,
    workflow_id: str,
) -> tuple[str, ...]:
    value = row.get("coveredPhases")
    if value is None:
        return ()
    if not isinstance(value, (list, tuple)) or not all(
        _visible(phase) for phase in value
    ):
        raise ProofError(
            f"{source} workflow {workflow_id}: row {row.get('id')!r} "
            "coveredPhases must be a list of phase names"
        )
    return tuple(str(phase) for phase in value)


def _validate_phase_references(
    timeline: list[Mapping[str, Any]],
    declared_phases: set[str],
    *,
    source: str,
    workflow_id: str,
) -> None:
    for row in timeline:
        references: list[str] = []
        if row.get("kind") == "phase":
            references.append(str(row.get("label") or ""))
        if row.get("phase") is not None:
            references.append(str(row["phase"]))
        references.extend(
            _covered_phases(
                row,
                source=source,
                workflow_id=workflow_id,
            )
        )
        undeclared = sorted({
            phase
            for phase in references
            if phase not in declared_phases
        })
        if undeclared:
            raise ProofError(
                f"{source} workflow {workflow_id}: row {row.get('id')!r} "
                f"references undeclared phase {undeclared[0]!r}"
            )


def _tool_call_id(record: Mapping[str, Any]) -> str | None:
    value = next(
        (
            record[field]
            for field in (
                "toolCallId",
                "tool_call_id",
                "callId",
                "call_id",
            )
            if field in record
        ),
        None,
    )
    if value is None:
        return None
    identifier = str(value).strip()
    return identifier or None


def _tool_name(record: Mapping[str, Any]) -> str | None:
    value = next(
        (
            record[field]
            for field in ("tool", "name", "toolName", "tool_name")
            if field in record and record[field] is not None
        ),
        None,
    )
    if value is None:
        return None
    name = str(value).strip()
    return name or None


def _tool_records_by_id(
    records: Iterable[Any],
    *,
    source: str,
    workflow_id: str,
    collection: str,
    timeline_rows: bool = False,
) -> dict[str, tuple[int, Mapping[str, Any]]]:
    indexed: dict[str, tuple[int, Mapping[str, Any]]] = {}
    for index, record in enumerate(records):
        if not isinstance(record, Mapping):
            raise ProofError(
                f"{source} workflow {workflow_id}: "
                f"{collection}[{index}] is not an object"
            )
        identifier = _tool_call_id(record)
        if identifier is None:
            raise ProofError(
                f"{source} workflow {workflow_id}: "
                f"{collection}[{index}] is missing persistent toolCallId"
            )
        if timeline_rows and str(record.get("id") or "") != identifier:
            raise ProofError(
                f"{source} workflow {workflow_id}: {collection}[{index}] "
                f"id {record.get('id')!r} does not match "
                f"toolCallId {identifier!r}"
            )
        if identifier in indexed:
            raise ProofError(
                f"{source} workflow {workflow_id}: {collection} contains "
                f"duplicate tool call id {identifier!r}"
            )
        indexed[identifier] = (index, record)
    return indexed


_TOOL_VALUE_ALIASES = {
    "request": ("request", "args", "arguments"),
    "response": ("response", "result"),
    "duration": ("durationMs", "duration_ms", "latencyMs", "latency_ms"),
}
_SUCCESS_STATUSES = {"ok", "success", "succeeded", "completed"}
_FAILURE_STATUSES = {"error", "failed", "failure", "rejected"}


def _tool_values(
    record: Mapping[str, Any],
    aliases: Sequence[str],
) -> list[tuple[str, Any]]:
    return [
        (field, record[field])
        for field in aliases
        if field in record
    ]


def _normalized_tool_status(
    record: Mapping[str, Any],
) -> tuple[int | None, bool | None]:
    codes: list[int] = []
    outcomes: list[bool] = []
    for field in ("statusCode", "status_code"):
        if field not in record:
            continue
        value = record[field]
        if not isinstance(value, int) or isinstance(value, bool):
            raise ValueError(f"{field} is not an integer")
        codes.append(value)
        outcomes.append(200 <= value < 400)
    if "success" in record:
        value = record["success"]
        if not isinstance(value, bool):
            raise ValueError("success is not a boolean")
        outcomes.append(value)
    if "status" in record:
        value = record["status"]
        if isinstance(value, int) and not isinstance(value, bool):
            codes.append(value)
            outcomes.append(200 <= value < 400)
        elif isinstance(value, bool):
            outcomes.append(value)
        elif isinstance(value, str):
            normalized = value.strip().lower()
            if normalized in _SUCCESS_STATUSES:
                outcomes.append(True)
            elif normalized in _FAILURE_STATUSES:
                outcomes.append(False)
            else:
                raise ValueError(f"status {value!r} is not recognized")
        else:
            raise ValueError("status is not comparable")
    if len(set(codes)) > 1 or len(set(outcomes)) > 1:
        raise ValueError("status fields disagree")
    return (
        codes[0] if codes else None,
        outcomes[0] if outcomes else None,
    )


def _row_value(row: Mapping[str, Any], key: str) -> Any:
    if row.get(key) is not None:
        return row[key]
    return _mapping(row.get("details")).get(key)


def _validate_optional_rows(
    timeline: list[Mapping[str, Any]],
    *,
    source: str,
    workflow_id: str,
) -> None:
    for row in timeline:
        label = str(row.get("label") or "")
        if label == "workflow.sub_spawned":
            if not _visible(_row_value(row, "childWorkflowId")):
                raise ProofError(
                    f"{source} workflow {workflow_id}: child lineage row "
                    f"{row.get('id')!r} is missing childWorkflowId"
                )
            if not _visible(_row_value(row, "childWorkflowType")):
                raise ProofError(
                    f"{source} workflow {workflow_id}: child lineage row "
                    f"{row.get('id')!r} is missing childWorkflowType"
                )
        elif row.get("kind") == "output" and not _visible(row.get("details")):
            raise ProofError(
                f"{source} workflow {workflow_id}: output row "
                f"{row.get('id')!r} has empty details"
            )
        elif label == "workflow.retry_scheduled":
            details = _mapping(row.get("details"))
            if not _visible(details.get("attempt")):
                raise ProofError(
                    f"{source} workflow {workflow_id}: retry row "
                    f"{row.get('id')!r} is missing attempt"
                )
            if not _visible(details.get("reason") or details.get("error")):
                raise ProofError(
                    f"{source} workflow {workflow_id}: retry row "
                    f"{row.get('id')!r} is missing reason or error"
                )
        elif label == "workflow.exception.detected":
            details = _mapping(row.get("details"))
            if not _visible(
                row.get("reason")
                or row.get("error")
                or details.get("reason")
                or details.get("error")
            ):
                raise ProofError(
                    f"{source} workflow {workflow_id}: error row "
                    f"{row.get('id')!r} is missing reason or error"
                )


def _validate_reasoning(
    timeline: list[Mapping[str, Any]],
    contract: WorkflowContract,
    declared_phases: set[str],
    *,
    source: str,
    workflow_id: str,
) -> list[Mapping[str, Any]]:
    reasoning_rows = [
        row for row in timeline if row.get("kind") == "reasoning"
    ]
    if _declared_agent_phases(contract.domain) and not reasoning_rows:
        raise ProofError(
            f"{source} workflow {workflow_id}: executable workflow "
            "requires at least 1 canonical reasoning row"
        )

    for row in reasoning_rows:
        if not _visible(row.get("agentRunId")):
            raise ProofError(
                f"{source} workflow {workflow_id}: canonical reasoning row "
                f"{row.get('id')!r} is missing stable agentRunId"
            )
        if not _visible(row.get("completedAt")):
            raise ProofError(
                f"{source} workflow {workflow_id}: canonical reasoning row "
                f"{row.get('id')!r} is missing completedAt"
            )
        phase = row.get("phase")
        covered = _covered_phases(
            row,
            source=source,
            workflow_id=workflow_id,
        )
        if not _visible(phase) and not covered:
            raise ProofError(
                f"{source} workflow {workflow_id}: canonical reasoning row "
                f"{row.get('id')!r} requires a declared phase or "
                "coveredPhases"
            )
        references = {
            *((str(phase),) if _visible(phase) else ()),
            *covered,
        }
        if not references <= declared_phases:
            raise ProofError(
                f"{source} workflow {workflow_id}: canonical reasoning row "
                f"{row.get('id')!r} references an undeclared phase"
            )
        if not isinstance(row.get("toolCalls"), list):
            raise ProofError(
                f"{source} workflow {workflow_id}: canonical reasoning row "
                f"{row.get('id')!r} toolCalls is not a list"
            )
    return reasoning_rows


def _validate_hitl_decisions(
    timeline: list[Mapping[str, Any]],
    contract: WorkflowContract,
    *,
    source: str,
    workflow_id: str,
) -> None:
    hitl_phases = _declared_hitl_phases(contract.domain)
    for row in timeline:
        if row.get("kind") != "decision":
            continue
        phase = row.get("phase")
        if phase is None and row.get("label") in hitl_phases:
            phase = row.get("label")
        if phase not in hitl_phases:
            continue
        persona = row.get("personaRole") or row.get("actor")
        for field, value in (
            ("personaRole", persona),
            ("verdict", row.get("verdict")),
            ("reason", row.get("reason")),
        ):
            if not _visible(value):
                raise ProofError(
                    f"{source} workflow {workflow_id}: HITL decision row "
                    f"{row.get('id')!r} is missing {field}"
                )
        if str(persona) not in contract.persona_roles:
            raise ProofError(
                f"{source} workflow {workflow_id}: HITL decision persona "
                f"{persona!r} does not resolve in the active pack"
            )


def _validate_tools(
    detail: dict,
    timeline: list[Mapping[str, Any]],
    reasoning_rows: list[Mapping[str, Any]],
    *,
    source: str,
    workflow_id: str,
) -> list[Mapping[str, Any]]:
    raw_calls = detail.get("mcpCalls")
    if not isinstance(raw_calls, list):
        raise ProofError(
            f"{source} workflow {workflow_id}: mcpCalls is not a list"
        )

    reasoning_tool_calls: list[Any] = []
    for row in reasoning_rows:
        reasoning_tool_calls.extend(row["toolCalls"])
    canonical_tool_rows = [
        row
        for row in timeline
        if row.get("kind") == "tool"
        and not str(row.get("id") or "").startswith("span:")
    ]

    reasoning_by_id = _tool_records_by_id(
        reasoning_tool_calls,
        source=source,
        workflow_id=workflow_id,
        collection="reasoning.toolCalls",
    )
    calls_by_id = _tool_records_by_id(
        raw_calls,
        source=source,
        workflow_id=workflow_id,
        collection="mcpCalls",
    )
    rows_by_id = _tool_records_by_id(
        canonical_tool_rows,
        source=source,
        workflow_id=workflow_id,
        collection="timeline Tool rows",
        timeline_rows=True,
    )
    identities = {
        "reasoning": set(reasoning_by_id),
        "mcpCalls": set(calls_by_id),
        "timeline": set(rows_by_id),
    }
    if len({frozenset(ids) for ids in identities.values()}) != 1:
        rendered = ", ".join(
            f"{name}={sorted(ids)}" for name, ids in identities.items()
        )
        raise ProofError(
            f"{source} workflow {workflow_id}: tool call ids differ; "
            f"{rendered}"
        )

    for identifier in sorted(calls_by_id):
        _, call = calls_by_id[identifier]
        _, reasoning_call = reasoning_by_id[identifier]
        _, tool_row = rows_by_id[identifier]
        canonical_values: dict[str, Any] = {}
        for field, aliases in _TOOL_VALUE_ALIASES.items():
            values = _tool_values(call, aliases)
            if not values:
                raise ProofError(
                    f"{source} workflow {workflow_id}: tool call "
                    f"{identifier!r} is missing canonical {field}"
                )
            canonical = values[0][1]
            if any(value != canonical for _, value in values[1:]):
                raise ProofError(
                    f"{source} workflow {workflow_id}: tool call "
                    f"{identifier!r} canonical {field} aliases do not match"
                )
            canonical_values[field] = canonical

        for record_name, record, required_fields in (
            ("reasoning", reasoning_call, ()),
            ("Tool row", tool_row, ("duration",)),
        ):
            for field, aliases in _TOOL_VALUE_ALIASES.items():
                values = _tool_values(record, aliases)
                if field in required_fields and not values:
                    raise ProofError(
                        f"{source} workflow {workflow_id}: {record_name} "
                        f"{identifier!r} is missing {field}"
                    )
                if any(
                    value != canonical_values[field]
                    for _, value in values
                ):
                    observed_field = values[0][0]
                    raise ProofError(
                        f"{source} workflow {workflow_id}: tool call "
                        f"{identifier!r} {observed_field} does not match "
                        f"mcpCalls {field}"
                    )

        try:
            call_code, call_succeeded = _normalized_tool_status(call)
        except ValueError as error:
            raise ProofError(
                f"{source} workflow {workflow_id}: tool call "
                f"{identifier!r} canonical status does not match: {error}"
            ) from error
        if call_succeeded is None:
            raise ProofError(
                f"{source} workflow {workflow_id}: tool call "
                f"{identifier!r} is missing canonical status"
            )
        for record_name, record, required in (
            ("reasoning", reasoning_call, False),
            ("Tool row", tool_row, True),
        ):
            try:
                observed_code, observed_succeeded = _normalized_tool_status(
                    record
                )
            except ValueError as error:
                raise ProofError(
                    f"{source} workflow {workflow_id}: tool call "
                    f"{identifier!r} {record_name} status does not match "
                    f"mcpCalls: {error}"
                ) from error
            if required and observed_succeeded is None:
                raise ProofError(
                    f"{source} workflow {workflow_id}: {record_name} "
                    f"{identifier!r} is missing status"
                )
            if (
                observed_code is not None
                and call_code is not None
                and observed_code != call_code
            ) or (
                observed_succeeded is not None
                and observed_succeeded != call_succeeded
            ):
                raise ProofError(
                    f"{source} workflow {workflow_id}: tool call "
                    f"{identifier!r} {record_name} status does not match "
                    "mcpCalls status"
                )

        call_name = _tool_name(call)
        if (
            call_name is None
            or _tool_name(reasoning_call) != call_name
            or _tool_name(tool_row) != call_name
        ):
            raise ProofError(
                f"{source} workflow {workflow_id}: tool call "
                f"{identifier!r} name does not match"
            )
    return list(raw_calls)


def _without_volatile(
    record: Mapping[str, Any],
    fields: set[str],
) -> dict[str, Any]:
    return {
        key: value
        for key, value in record.items()
        if key not in fields
    }


def _evidence(
    detail: dict,
    contract: WorkflowContract,
    source: str,
) -> dict:
    workflow = _workflow(detail, source)
    workflow_id = str(workflow.get("id") or "")
    raw_timeline = detail.get("timeline")
    if not isinstance(raw_timeline, list) or not raw_timeline:
        raise ProofError(f"{source} workflow {workflow_id}: timeline is empty")
    if not all(
        isinstance(row, Mapping)
        and _visible(row.get("id"))
        and _visible(row.get("kind"))
        and _visible(row.get("label"))
        for row in raw_timeline
    ):
        raise ProofError(
            f"{source} workflow {workflow_id}: timeline has an invalid row"
        )
    timeline: list[Mapping[str, Any]] = list(raw_timeline)

    started_rows = [
        row
        for row in timeline
        if row.get("label") == "workflow.started"
    ]
    if len(started_rows) != 1:
        raise ProofError(
            f"{source} workflow {workflow_id}: expected 1 workflow.started "
            f"lifecycle row, found {len(started_rows)}"
        )

    status = str(workflow.get("status") or "")
    expected_terminal = _TERMINAL_LABELS.get(status)
    if expected_terminal is None:
        raise ProofError(
            f"{source} workflow {workflow_id}: non-terminal status "
            f"{status!r}"
        )
    terminal_rows = [
        row
        for row in timeline
        if row.get("label") in _TERMINAL_LABELS.values()
    ]
    if len(terminal_rows) != 1:
        raise ProofError(
            f"{source} workflow {workflow_id}: expected 1 terminal "
            f"lifecycle row, found {len(terminal_rows)}"
        )
    allowed_terminals = {expected_terminal}
    if status == "failed":
        allowed_terminals.add("workflow.rejected")
    if terminal_rows[0].get("label") not in allowed_terminals:
        raise ProofError(
            f"{source} workflow {workflow_id}: expected 1 "
            f"{expected_terminal} terminal lifecycle row, found 0"
        )

    declared_phases = _declared_phase_names(contract.domain)
    phase_rows = [
        row for row in timeline if row.get("kind") == "phase"
    ]
    if not phase_rows:
        raise ProofError(
            f"{source} workflow {workflow_id}: phase rows are empty"
        )
    _validate_phase_references(
        timeline,
        declared_phases,
        source=source,
        workflow_id=workflow_id,
    )
    for row in phase_rows:
        if row.get("status") not in _TERMINAL_PHASE_STATUSES:
            raise ProofError(
                f"{source} workflow {workflow_id}: phase "
                f"{row.get('label')!r} is not terminal or skipped "
                f"(status {row.get('status')!r})"
            )

    reasoning_rows = _validate_reasoning(
        timeline,
        contract,
        declared_phases,
        source=source,
        workflow_id=workflow_id,
    )
    _validate_hitl_decisions(
        timeline,
        contract,
        source=source,
        workflow_id=workflow_id,
    )
    _validate_optional_rows(
        timeline,
        source=source,
        workflow_id=workflow_id,
    )
    calls = _validate_tools(
        detail,
        timeline,
        reasoning_rows,
        source=source,
        workflow_id=workflow_id,
    )

    stable_rows = [
        _without_volatile(
            row,
            _VOLATILE_TIMELINE_FIELDS
            | (
                set()
                if row.get("kind") == "tool"
                else _VOLATILE_DURATION_FIELDS
            ),
        )
        for row in timeline
    ]
    return {
        "workflow": _without_volatile(
            workflow,
            _VOLATILE_WORKFLOW_FIELDS,
        ),
        "timeline": stable_rows,
        "mcpCalls": [
            _without_volatile(call, {"timestamp"})
            for call in calls
        ],
    }


def verify_details(
    details: Iterable[dict],
    contracts: Mapping[str, WorkflowContract],
    *,
    source: str,
) -> dict[str, dict]:
    if not contracts:
        raise ProofError(
            f"{source} active pack has no required workflow contracts"
        )
    evidence_by_id: dict[str, dict] = {}
    inspected_types: set[str] = set()
    for detail in details:
        if not isinstance(detail, dict):
            raise ProofError(
                f"{source} workflow detail is not an object"
            )
        workflow = _workflow(detail, source)
        workflow_type = workflow.get("type")
        if workflow_type not in contracts:
            continue
        workflow_id = str(workflow.get("id") or "")
        if not workflow_id:
            raise ProofError(
                f"{source} {workflow_type!r} workflow has no id"
            )
        if workflow_id in evidence_by_id:
            raise ProofError(
                f"{source} contains duplicate workflow id {workflow_id}"
            )
        inspected_types.add(str(workflow_type))
        evidence_by_id[workflow_id] = {
            "workflowType": workflow_type,
            "evidence": _evidence(
                detail,
                contracts[str(workflow_type)],
                source,
            ),
        }

    missing_types = sorted(set(contracts) - inspected_types)
    if missing_types:
        raise ProofError(
            f"{source} missing required workflow types: "
            f"{', '.join(missing_types)}"
        )
    return evidence_by_id


def verify_live_and_replay(
    live_details: WorkflowSnapshot,
    replay_details: WorkflowSnapshot,
    contracts: Mapping[str, WorkflowContract],
) -> dict[str, dict]:
    if not isinstance(live_details, WorkflowSnapshot):
        raise ProofError(
            "live snapshot lacks sourceMode provenance; load or capture "
            "a schemaVersion 2 snapshot"
        )
    if live_details.source_mode != "live":
        raise ProofError(
            "live snapshot sourceMode must be 'live'; "
            f"found {live_details.source_mode!r}"
        )
    if not isinstance(replay_details, WorkflowSnapshot):
        raise ProofError(
            "replay snapshot lacks sourceMode provenance; load or capture "
            "a schemaVersion 2 snapshot"
        )
    if replay_details.source_mode != "replay":
        raise ProofError(
            "replay snapshot sourceMode must be 'replay'; "
            f"found {replay_details.source_mode!r}"
        )

    live = verify_details(live_details, contracts, source="live")
    replay = verify_details(replay_details, contracts, source="replay")
    missing_ids = sorted(set(live) - set(replay))
    extra_ids = sorted(set(replay) - set(live))
    if missing_ids or extra_ids:
        raise ProofError(
            "live/replay workflow ids differ: "
            f"missing={missing_ids}, extra={extra_ids}"
        )
    for workflow_id in sorted(live):
        if live[workflow_id] != replay[workflow_id]:
            raise ProofError(
                f"workflow {workflow_id}: live/replay evidence differs"
            )
    return replay


def _workflow_ids(details: Iterable[dict]) -> tuple[str, ...]:
    return tuple(
        str(_workflow(detail, "snapshot").get("id") or "")
        for detail in details
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Verify active-pack workflow detail evidence, with optional "
            "live/replay parity."
        )
    )
    parser.add_argument("--vertical", required=True)
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--base-url")
    source.add_argument("--details-dir", type=Path)
    parser.add_argument("--save-dir", type=Path)
    parser.add_argument(
        "--compare-dir",
        type=Path,
        help="Saved live details to re-check and compare with this source.",
    )
    args = parser.parse_args(argv)

    try:
        pack = build_runtime({"ZAVA_VERTICAL": args.vertical}).pack
        contracts = contracts_for_pack(pack)
        live_details = (
            load_snapshot(args.compare_dir, args.vertical)
            if args.compare_dir is not None
            else None
        )
        if (
            live_details is not None
            and live_details.source_mode != "live"
        ):
            raise ProofError(
                "live snapshot sourceMode must be 'live'; "
                f"found {live_details.source_mode!r}"
            )
        if args.base_url is not None:
            details = fetch_url_details(
                args.base_url,
                contracts,
                workflow_ids=(
                    _workflow_ids(live_details)
                    if live_details is not None
                    else None
                ),
            )
        else:
            details = load_snapshot(args.details_dir, args.vertical)

        expected_mode = "replay" if live_details is not None else "live"
        role = "replay" if live_details is not None else "live"
        if details.source_mode != expected_mode:
            raise ProofError(
                f"{role} snapshot sourceMode must be {expected_mode!r}; "
                f"found {details.source_mode!r}"
            )
        if args.save_dir is not None:
            save_snapshot(args.save_dir, args.vertical, details)

        evidence = (
            verify_details(details, contracts, source="live")
            if live_details is None
            else verify_live_and_replay(
                live_details,
                details,
                contracts,
            )
        )
    except (OSError, ProofError, ValueError) as error:
        print(
            f"workflow visibility proof failed: {error}",
            file=sys.stderr,
        )
        return 1

    print(json.dumps({
        "result": "PASS",
        "sourceMode": details.source_mode,
        "vertical": args.vertical,
        "workflowInstances": len(evidence),
        "workflowTypes": len(contracts),
    }, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

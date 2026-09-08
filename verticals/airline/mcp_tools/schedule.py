"""Airline Hero 3 – Preemptive Schedule Resilience synthetic MCP tools.

These tools are read-only, bounded, and operate on synthetic data only.
No active-world mutation, no network calls.
"""
from __future__ import annotations

import json
import math
from typing import Any

from copilot.tools import ToolResult, define_tool
from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    JsonValue,
    StrictInt,
    StrictStr,
    field_validator,
)


TOOL_NAMES = {
    "airline_read_schedule_risk_evidence",
    "airline_rank_admitted_resilience_options",
}

_PROHIBITED_CONTEXT_KEYS = {
    "live_data",
    "live_system",
    "recommended_action",
    "selected_option_id",
    "source_mode",
}


def _validate_identity_list(values: list[str], *, field_name: str) -> list[str]:
    if not values:
        raise ValueError(f"{field_name} must not be empty")
    if any(not value.strip() for value in values):
        raise ValueError(f"{field_name} entries must not be empty")
    if len(set(values)) != len(values):
        raise ValueError(f"{field_name} entries must be unique")
    return values


def _validate_versions(versions: dict[str, int]) -> dict[str, int]:
    if not versions:
        raise ValueError("evidence_versions must not be empty")
    for actor_id, version in versions.items():
        if not isinstance(actor_id, str) or not actor_id.strip():
            raise ValueError("evidence_versions keys must not be empty")
        if isinstance(version, bool) or not isinstance(version, int) or version < 0:
            raise ValueError("evidence_versions values must be non-negative integers")
    return versions


def _validate_bounded_json(
    value: JsonValue,
    *,
    path: str,
    depth: int = 0,
) -> None:
    if depth > 6:
        raise ValueError(f"{path} exceeds the maximum nesting depth")
    if isinstance(value, dict):
        if len(value) > 50:
            raise ValueError(f"{path} contains too many fields")
        for key, item in value.items():
            if key in _PROHIBITED_CONTEXT_KEYS:
                raise ValueError(f"{path} contains prohibited field {key!r}")
            _validate_bounded_json(item, path=f"{path}.{key}", depth=depth + 1)
    elif isinstance(value, list):
        if len(value) > 100:
            raise ValueError(f"{path} contains too many items")
        for index, item in enumerate(value):
            _validate_bounded_json(
                item,
                path=f"{path}[{index}]",
                depth=depth + 1,
            )
    elif isinstance(value, str) and len(value) > 2_000:
        raise ValueError(f"{path} contains an overlong string")
    elif isinstance(value, float) and not math.isfinite(value):
        raise ValueError(f"{path} contains a non-finite number")


class SchedRiskObservation(BaseModel):
    model_config = ConfigDict(extra="allow", strict=True)

    story_id: StrictStr = Field(min_length=1)
    risk_signal_id: StrictStr = Field(min_length=1)
    affected_sector_ids: list[StrictStr]
    affected_slot_ids: list[StrictStr]
    evidence_versions: dict[StrictStr, StrictInt]

    @field_validator("affected_sector_ids")
    @classmethod
    def validate_sector_ids(cls, values: list[str]) -> list[str]:
        return _validate_identity_list(values, field_name="affected_sector_ids")

    @field_validator("affected_slot_ids")
    @classmethod
    def validate_slot_ids(cls, values: list[str]) -> list[str]:
        return _validate_identity_list(values, field_name="affected_slot_ids")

    @field_validator("evidence_versions")
    @classmethod
    def validate_evidence_versions(cls, versions: dict[str, int]) -> dict[str, int]:
        return _validate_versions(versions)


class ReadScheduleRiskEvidenceParams(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    observation: SchedRiskObservation


class RankAdmittedResilienceOptionsParams(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    admitted_options: list[dict[StrictStr, JsonValue]] = Field(
        min_length=1,
        max_length=100,
    )
    ranking_context: dict[StrictStr, JsonValue] = Field(max_length=50)

    @field_validator("admitted_options")
    @classmethod
    def validate_admitted_options(
        cls,
        admitted_options: list[dict[str, JsonValue]],
    ) -> list[dict[str, JsonValue]]:
        option_ids: list[str] = []
        for index, admitted_option in enumerate(admitted_options):
            if admitted_option.get("feasible", True) is not True:
                raise ValueError(f"option at index {index} is not admitted (infeasible)")
            if admitted_option.get("admitted", True) is not True:
                raise ValueError(f"option at index {index} is not admitted")

            option_id = admitted_option.get("option_id")
            if not isinstance(option_id, str) or not str(option_id).strip():
                raise ValueError(f"option at index {index} requires a non-empty option_id")
            if not isinstance(admitted_option.get("actions"), list):
                raise ValueError(f"option {option_id!r} requires an actions list")
            versions = admitted_option.get("evidence_versions")
            if not isinstance(versions, dict):
                raise ValueError(f"option {option_id!r} requires evidence_versions")
            _validate_versions({str(k): v for k, v in versions.items()})  # type: ignore[arg-type]
            _validate_bounded_json(
                admitted_option,
                path=f"admitted_options[{index}]",
            )
            option_ids.append(str(option_id))

        if len(set(option_ids)) != len(option_ids):
            raise ValueError("admitted_options contains duplicate option IDs")
        return admitted_options

    @field_validator("ranking_context")
    @classmethod
    def validate_ranking_context(
        cls,
        ranking_context: dict[str, JsonValue],
    ) -> dict[str, JsonValue]:
        _validate_bounded_json(ranking_context, path="ranking_context")
        return ranking_context


def _tool_result(payload: dict[str, Any]) -> ToolResult:
    return ToolResult(text_result_for_llm=json.dumps(payload, sort_keys=True))


@define_tool(
    name="airline_read_schedule_risk_evidence",
    description="Read supplied versioned synthetic schedule-risk observation.",
)
def airline_read_schedule_risk_evidence(
    params: ReadScheduleRiskEvidenceParams,
) -> ToolResult:
    observation = params.observation.model_dump(exclude_none=True)
    return _tool_result({"source_mode": "simulated", **observation})


@define_tool(
    name="airline_rank_admitted_resilience_options",
    description=(
        "Return deterministically admitted synthetic schedule resilience options "
        "unchanged with bounded ranking context."
    ),
)
def airline_rank_admitted_resilience_options(
    params: RankAdmittedResilienceOptionsParams,
) -> ToolResult:
    return _tool_result(
        {
            "source_mode": "simulated",
            "admitted_options": params.admitted_options,
            "ranking_context": params.ranking_context,
        }
    )

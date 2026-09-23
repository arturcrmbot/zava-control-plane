"""Supporting-process entity projection (mule investigation, merchant risk).

Shared by both supporting workflow types. The store persists ``case`` from
the spawner, ``hitl_context`` while the gate is open, and the persona
decisions under ``decisions``. These processes hold no actor-world records,
so no world entities are claimed.
"""
from __future__ import annotations

import json
from collections.abc import Generator
from datetime import datetime, timezone
from typing import Any

from api.server.services.entity_graph import DecisionWrite, EntityWrite, RelWrite
from verticals.banking.support_constants import (
    MERCHANT_WORKFLOW_TYPE,
    MULE_WORKFLOW_TYPE,
)

WORKFLOW_TYPES = (MULE_WORKFLOW_TYPE, MERCHANT_WORKFLOW_TYPE)


def _json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, default=str)


def _dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def project(workflow: Any) -> Generator[EntityWrite | RelWrite | DecisionWrite, None, None]:
    workflow_id = getattr(workflow, "id", None)
    if not isinstance(workflow_id, str) or not workflow_id:
        return
    payload = _dict(getattr(workflow, "payload", None))
    hitl = _dict(payload.get("hitl_context"))
    case = _dict(payload.get("case")) or _dict(_dict(hitl.get("observation")).get("case"))
    if not case.get("id"):
        return

    sources = (workflow_id,)
    case_id = str(case["id"])
    subject_id = str(case.get("subject_id") or "")
    subject_kind = str(case.get("subject_kind") or "subject")

    yield EntityWrite(
        kind="Asset",
        id=case_id,
        attrs={
            "kind": "case",
            "identifier": case_id,
            "status": str(getattr(workflow, "status", "") or "open"),
            "attributes": _json(
                {
                    "risk_band": case.get("risk_band"),
                    "subject_kind": subject_kind,
                    "sector": case.get("sector"),
                }
            ),
        },
        source_workflows=sources,
    )

    if subject_id:
        if subject_kind == "merchant":
            yield EntityWrite(
                kind="Organisation",
                id=subject_id,
                attrs={
                    "name": subject_id,
                    "kind": "merchant",
                    "risk_band": str(case.get("risk_band") or ""),
                    "attributes": _json({"sector": case.get("sector")}),
                },
                source_workflows=sources,
            )
        else:
            yield EntityWrite(
                kind="Account",
                id=subject_id,
                attrs={
                    "name": subject_id,
                    "type": "beneficiary",
                    "currency": "GBP",
                    "attributes": _json(
                        {"risk_band": case.get("risk_band"), "status": "under_review"}
                    ),
                },
                source_workflows=sources,
            )
        yield RelWrite(src_id=case_id, rel="TOUCHED", dst_id=subject_id)

    governing_rule = _dict(hitl.get("authority")).get("governing_rule_id")
    decided_on = (case_id,) + ((subject_id,) if subject_id else ())
    for entry in _list(payload.get("decisions")):
        if not isinstance(entry, dict) or not entry.get("verdict"):
            continue
        yield DecisionWrite(
            workflow_id=workflow_id,
            phase=str(entry.get("phase") or hitl.get("phase") or "Approve"),
            persona_role=str(entry.get("persona_role") or hitl.get("persona") or ""),
            verdict=str(entry["verdict"]),
            reason=str(entry.get("reason") or ""),
            decided_at=str(entry.get("decided_at") or datetime.now(timezone.utc).isoformat()),
            source_event=str(entry.get("source_event") or hitl.get("external_event") or ""),
            attributes={
                "governing_rule_id": governing_rule,
                "decided_via": "persona",
            },
            decided_on=decided_on,
        )

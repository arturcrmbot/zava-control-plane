from __future__ import annotations

import json
from datetime import datetime, timezone

from api.server.services.entity_graph import (
    DecisionWrite,
    EntityWrite,
    RelWrite,
)
from api.shared.types import Workflow
from verticals.electronics.domains import ELECTRONICS_DOMAINS
from verticals.electronics.process_profiles import ELECTRONICS_PROCESS_PROFILES


def _asset(
    actor_id: str,
    *,
    status: str,
    workflow_id: str,
) -> EntityWrite:
    return EntityWrite(
        kind="Asset",
        id=actor_id,
        attrs={
            "kind": _actor_kind(actor_id),
            "identifier": actor_id,
            "status": status,
            "attributes": json.dumps(
                {"workflow_id": workflow_id},
                sort_keys=True,
            ),
        },
        source_workflows=(workflow_id,),
    )


def _actor_kind(actor_id: str) -> str:
    prefixes = {
        "STORE-": "retail-store",
        "DC-": "distribution-centre",
        "SKU-": "electronics-sku",
        "STOCK-": "inventory-position",
        "ORDER-": "retail-order",
        "RETURN-": "retail-return",
        "DELIVERY-": "delivery",
        "PROMO-": "promotion",
        "SELLER-": "marketplace-seller",
        "OFFER-": "marketplace-offer",
    }
    return next(
        (kind for prefix, kind in prefixes.items() if actor_id.startswith(prefix)),
        "retail-actor",
    )


def _decision(
    workflow: Workflow,
    actor_ids: tuple[str, ...],
) -> DecisionWrite | None:
    entries = (workflow.payload or {}).get("decisions") or []
    profile = ELECTRONICS_PROCESS_PROFILES[workflow.type]
    if entries:
        entry = entries[-1]
        decision_id = entry.get("decision_id")
    else:
        decision = (workflow.payload or {}).get("decision") or {}
        reasoning = decision.get("reasoning")
        authority = (
            reasoning.get("authority")
            if isinstance(reasoning, dict)
            else None
        )
        if not isinstance(authority, dict) or not authority.get("decision"):
            return None
        entry = {
            "phase": (
                ELECTRONICS_DOMAINS[workflow.type].hitl_gates[0].gate_phase
                if ELECTRONICS_DOMAINS[workflow.type].hitl_gates
                else "Policy Decision"
            ),
            "persona_role": authority.get("persona"),
            "verdict": authority.get("decision"),
            "reason": reasoning.get("summary") or "Durable authority decision.",
            "decided_at": datetime.fromtimestamp(
                workflow.created_at,
                tz=timezone.utc,
            ).isoformat(),
        }
        decision_id = authority.get("decision_id")
    return DecisionWrite(
        workflow_id=workflow.id,
        phase=str(entry.get("phase") or "Approval"),
        persona_role=str(
            entry.get("persona_role")
            or profile.hitl_persona
            or profile.function
        ),
        verdict=str(entry.get("verdict") or "approve"),
        reason=str(entry.get("reason") or ""),
        decided_at=str(
            entry.get("decided_at") or "2026-07-22T14:00:00+00:00"
        ),
        source_event="world.responder.decided",
        attributes={
            "workflow_type": workflow.type,
            "command_type": profile.command_type,
            "decision_id": decision_id,
        },
        decided_on=actor_ids,
    )


def project(
    workflow: Workflow,
) -> list[EntityWrite | RelWrite | DecisionWrite]:
    payload = workflow.payload or {}
    observation = payload.get("retail_case")
    if not isinstance(observation, dict):
        observation = {}
    actor_ids = tuple(
        dict.fromkeys(
            str(value)
            for value in observation.get("actor_ids") or []
            if value
        )
    )
    operations: list[EntityWrite | RelWrite | DecisionWrite] = [
        EntityWrite(
            kind="Workflow",
            id=workflow.id,
            attrs={
                "workflow_type": workflow.type,
                "status": workflow.status,
            },
            source_workflows=(workflow.id,),
        ),
        EntityWrite(
            kind="Period",
            id="PERIOD-electronics-demo",
            attrs={
                "kind": "demo-window",
                "label": "Electronics Retail live demo",
            },
        ),
        RelWrite(
            workflow.id,
            "WORKFLOW_IN_PERIOD",
            "PERIOD-electronics-demo",
        ),
    ]
    for actor_id in actor_ids:
        operations.append(
            _asset(
                actor_id,
                status=workflow.status,
                workflow_id=workflow.id,
            )
        )

    if workflow.type == "inventory-rebalancing":
        candidate = observation.get("transfer_candidate")
        if not isinstance(candidate, dict):
            raise ValueError(
                "inventory-rebalancing projection requires observation."
                "transfer_candidate with source_location_id, "
                "destination_location_id and sku_id"
            )
        missing = [
            field
            for field in (
                "source_location_id",
                "destination_location_id",
                "sku_id",
            )
            if not candidate.get(field)
        ]
        if missing:
            raise ValueError(
                "inventory-rebalancing observation.transfer_candidate is "
                f"missing required field(s): {', '.join(missing)}"
            )
        source_location = str(candidate["source_location_id"])
        destination_location = str(candidate["destination_location_id"])
        sku_id = str(candidate["sku_id"])
        source_stock = (
            f"STOCK-{source_location}-{sku_id}"
        )
        destination_stock = (
            f"STOCK-{destination_location}-{sku_id}"
        )
        required = (
            source_location,
            destination_location,
            sku_id,
            source_stock,
            destination_stock,
        )
        existing = {
            operation.id
            for operation in operations
            if isinstance(operation, EntityWrite)
        }
        for actor_id in required:
            if actor_id not in existing:
                operations.append(
                    _asset(
                        actor_id,
                        status=workflow.status,
                        workflow_id=workflow.id,
                    )
                )
        operations.extend(
            [
                RelWrite(source_stock, "HOSTED_ON", source_location),
                RelWrite(
                    destination_stock,
                    "HOSTED_ON",
                    destination_location,
                ),
                RelWrite(
                    sku_id,
                    "ASSET_AT_SITE",
                    destination_location,
                ),
            ]
        )

    decision = _decision(workflow, actor_ids[:5])
    if decision is not None:
        operations.append(decision)
    return operations

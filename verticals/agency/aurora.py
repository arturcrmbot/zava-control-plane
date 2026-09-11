from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from typing import Any

from api.server.services.entity_graph import EntityWrite


BRAND_ID = "BRAND-aurora"

def bootstrap_budget_context(graph) -> None:
    """Provide the synthetic scenario input, never a pre-completed workflow."""
    if _brand(graph, BRAND_ID) is not None:
        return
    graph.upsert(EntityWrite(
        kind="Brand",
        id=BRAND_ID,
        attrs={
            "name": "Aurora",
            "annual_budget_gbp": 100_000.0,
            "budget_remaining_gbp": 100_000.0,
            "attributes": json.dumps({"synthetic": True, "source": "aurora-demo"}),
        },
        source_workflows=(),
    ))


class AuroraOperationConflict(ValueError):
    pass


def _digest(*parts: object, length: int = 16) -> str:
    raw = ":".join(str(part) for part in parts)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:length]


def _brand(graph, brand_id: str) -> dict[str, Any] | None:
    rows = graph.query(
        "MATCH (b:Brand) WHERE b.id = $bid "
        "RETURN b.id AS id, b.name AS name, "
        "b.annual_budget_gbp AS annual_budget_gbp",
        {"bid": brand_id},
    )
    return rows[0] if rows else None


def _spend(graph, brand_id: str) -> float:
    rows = graph.query(
        "MATCH (m:Money)-[:COSTED_TO_BRAND]->(b:Brand) "
        "WHERE b.id = $bid RETURN sum(m.amount) AS total",
        {"bid": brand_id},
    )
    value = rows[0].get("total") if rows else None
    return float(value) if value is not None else 0.0


def _first_id(graph, query: str, key: str) -> str | None:
    rows = graph.query(query)
    value = rows[0].get(key) if rows else None
    return str(value) if value else None


def observe_budget_signal(
    graph,
    *,
    workflow_id: str,
    brand_id: str = BRAND_ID,
    target_pct: float = 1.0,
) -> dict[str, Any]:
    if not 0.0 < float(target_pct) <= 2.0:
        raise ValueError("target_pct must be greater than 0 and no more than 2")
    brand = _brand(graph, brand_id)
    if brand is None:
        raise ValueError(f"brand {brand_id!r} not found")
    budget = float(brand.get("annual_budget_gbp") or 0.0)
    if budget <= 0:
        raise ValueError(f"brand {brand_id!r} has no annual_budget_gbp")

    signal_id = f"AUR-SIGNAL-{_digest(workflow_id, brand_id, target_pct)}"
    money_ids = [
        f"MONEY-{signal_id}-{index}"
        for index in range(1, 6)
    ]
    existing_total = 0.0
    existing_ids: set[str] = set()
    for money_id in money_ids:
        row = graph.query_one(
            "MATCH (m:Money) WHERE m.id = $id "
            "RETURN m.id AS id, m.amount AS amount",
            {"id": money_id},
        )
        if row is not None:
            existing_ids.add(money_id)
            existing_total += float(row.get("amount") or 0.0)

    current_spend = _spend(graph, brand_id)
    original_spend = max(0.0, current_spend - existing_total)
    target_amount = budget * float(target_pct)
    gap = max(0.0, target_amount - original_spend)
    per_row = round(gap / len(money_ids), 2) if gap else 0.0
    account_id = _first_id(
        graph,
        "MATCH (a:Account) RETURN a.id AS id LIMIT 1",
        "id",
    )
    period_id = _first_id(
        graph,
        "MATCH (p:Period) WHERE p.kind = 'quarter' "
        "RETURN p.id AS id ORDER BY p.`starts` DESC LIMIT 1",
        "id",
    )
    now = datetime.now(tz=timezone.utc)
    for index, money_id in enumerate(money_ids):
        if money_id in existing_ids or gap <= 0:
            continue
        amount = (
            per_row
            if index < len(money_ids) - 1
            else round(gap - per_row * (len(money_ids) - 1), 2)
        )
        graph.upsert(EntityWrite(
            kind="Money",
            id=money_id,
            attrs={
                "kind": "po",
                "amount": float(amount),
                "currency": "GBP",
                "attributes": json.dumps({
                    "synthetic_signal": signal_id,
                    "source": "aurora-budget-response",
                }),
            },
            source_workflows=(workflow_id,),
        ))
        graph.link(money_id, "COSTED_TO_BRAND", brand_id, posted_at=now)
        if account_id:
            graph.link(money_id, "BOOKED_AGAINST", account_id, posted_at=now)
        if period_id:
            graph.link(money_id, "BELONGS_TO", period_id)

    after_spend = _spend(graph, brand_id)
    return {
        "signal_id": signal_id,
        "synthetic": True,
        "brand_id": brand_id,
        "brand_name": str(brand.get("name") or brand_id),
        "annual_budget_gbp": budget,
        "before_spend_gbp": round(original_spend, 2),
        "after_spend_gbp": round(after_spend, 2),
        "before_pct": round(original_spend / budget, 4),
        "after_pct": round(after_spend / budget, 4),
        "money_ids": money_ids if gap > 0 else [],
        "gap_filled_gbp": round(gap, 2),
    }


def apply_approved_policy(
    graph,
    *,
    governance_kernel,
    workflow_id: str,
    brand_id: str,
    approval: dict[str, Any],
    proposed_action: dict[str, Any],
) -> dict[str, Any]:
    if approval.get("decision") != "approve":
        raise ValueError("policy application requires an approve decision")
    decision_id = str(approval.get("decision_id") or "").strip()
    if not decision_id:
        raise ValueError("approval decision_id is required")
    actor_role = str(approval.get("actor_role") or "").strip().lower()
    action = str(proposed_action.get("kind") or "")
    verdict = str(proposed_action.get("verdict") or "")
    attributes = dict(proposed_action.get("attributes") or {})
    category = str(attributes.get("scope") or "")
    targets = [str(value) for value in (proposed_action.get("decided_on") or [])]
    if action != "policy_set" or verdict != "freeze":
        raise ValueError("Aurora response requires a policy_set freeze action")
    if category != "po":
        raise PermissionError("Aurora freeze authority is scoped to category 'po'")
    if targets != [brand_id]:
        raise ValueError("proposed action must target only the Aurora brand")

    authority = governance_kernel.check_authority(
        role=actor_role,
        action=action,
        category=category,
        requester_role=actor_role,
    )
    if not authority.allowed:
        raise PermissionError(authority.reason)

    existing = graph.query_one(
        "MATCH (d:Decision) WHERE d.workflow_id = $workflow_id "
        "AND d.phase = 'policy_set' AND d.persona_role = $persona_role "
        "RETURN d.id AS id, d.verdict AS verdict, d.attributes AS attributes",
        {"workflow_id": workflow_id, "persona_role": actor_role},
    )
    if existing is not None:
        existing_attrs = json.loads(existing.get("attributes") or "{}")
        if (
            existing.get("verdict") != verdict
            or existing_attrs.get("approval_decision_id") != decision_id
        ):
            raise AuroraOperationConflict(
                "conflicting policy retry for existing Aurora decision"
            )
        return {
            "outcome": "applied",
            "duplicate": True,
            "decision_id": existing["id"],
            "approval_decision_id": decision_id,
            "governing_rule_id": existing_attrs.get("governing_rule_id"),
            "brand_id": brand_id,
            "verdict": verdict,
        }

    graph_decision_id = graph.record_decision(
        workflow_id=workflow_id,
        phase="policy_set",
        persona_role=actor_role,
        verdict=verdict,
        reason=str(
            proposed_action.get("reason")
            or "Approved Aurora purchase-order freeze"
        ),
        decided_at=datetime.now(tz=timezone.utc),
        source_event="aurora_budget_response_decision",
        attributes={
            **attributes,
            "action_id": proposed_action.get("id"),
            "approval_decision_id": decision_id,
            "approved_by": approval.get("resolved_by"),
            "governing_rule_id": authority.governing_rule_id,
            "target_brand_id": brand_id,
        },
        decided_on=(brand_id,),
    )
    return {
        "outcome": "applied",
        "duplicate": False,
        "decision_id": graph_decision_id,
        "approval_decision_id": decision_id,
        "governing_rule_id": authority.governing_rule_id,
        "brand_id": brand_id,
        "verdict": verdict,
    }

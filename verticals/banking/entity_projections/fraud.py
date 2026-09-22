"""APP fraud reimbursement entity projection.

Projects only observed evidence. Every record below requires grounded
evidence on the workflow payload; absent evidence yields fewer nodes rather
than invented ones.
"""
from __future__ import annotations

import json
from collections.abc import Generator
from datetime import datetime, timezone
from typing import Any

from api.server.services.entity_graph import DecisionWrite, EntityWrite, RelWrite
from verticals.banking.fraud_constants import (
    FRAUD_HITL_EVENT,
    FRAUD_HITL_PERSONA,
    FRAUD_WORKFLOW_TYPE,
)

WORKFLOW_TYPE = FRAUD_WORKFLOW_TYPE


def _json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, default=str)


def _payload(workflow: Any) -> dict[str, Any]:
    payload = getattr(workflow, "payload", None)
    return payload if isinstance(payload, dict) else {}


def _dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _observation(payload: dict[str, Any]) -> dict[str, Any]:
    hitl = _dict(payload.get("hitl_context"))
    observation = _dict(hitl.get("observation"))
    if observation:
        return observation
    evidence = _dict(payload.get("evidence"))
    return _dict(evidence.get("observation"))


def project(workflow: Any) -> Generator[EntityWrite | RelWrite | DecisionWrite, None, None]:
    workflow_id = getattr(workflow, "id", None)
    if not isinstance(workflow_id, str) or not workflow_id:
        return

    payload = _payload(workflow)
    hitl = _dict(payload.get("hitl_context"))
    observation = _observation(payload)
    if not observation:
        return

    claim = _dict(observation.get("claim"))
    customer = _dict(observation.get("customer"))
    account = _dict(observation.get("account"))
    beneficiary = _dict(observation.get("beneficiary"))
    receiving_psp = _dict(observation.get("receiving_psp"))
    corporate = _dict(observation.get("corporate_holder"))
    sources = (workflow_id,)

    if customer.get("id"):
        yield EntityWrite(
            kind="Person",
            id=str(customer["id"]),
            attrs={
                "name": str(customer.get("display_name") or customer["id"]),
                "role": "customer",
                "market": str(customer.get("segment") or "personal"),
                "attributes": _json(
                    {
                        "vulnerability_flag": customer.get("vulnerability_flag"),
                        "status": customer.get("status"),
                    }
                ),
            },
            source_workflows=sources,
        )

    if account.get("id"):
        yield EntityWrite(
            kind="Account",
            id=str(account["id"]),
            attrs={
                "name": str(account["id"]),
                "type": str(account.get("kind") or "current"),
                "currency": "GBP",
                "attributes": _json(
                    {
                        "sort_code": account.get("sort_code"),
                        "status": account.get("status"),
                    }
                ),
            },
            source_workflows=sources,
        )
        if customer.get("id"):
            yield RelWrite(
                src_id=str(customer["id"]),
                rel="HOLDS_ACCOUNT",
                dst_id=str(account["id"]),
            )

    if beneficiary.get("id"):
        yield EntityWrite(
            kind="Account",
            id=str(beneficiary["id"]),
            attrs={
                "name": str(beneficiary["id"]),
                "type": "beneficiary",
                "currency": "GBP",
                "attributes": _json(
                    {
                        "risk_band": beneficiary.get("risk_band"),
                        "holder_kind": beneficiary.get("holder_kind"),
                        "psp_id": beneficiary.get("psp_id"),
                        "status": beneficiary.get("status"),
                    }
                ),
            },
            source_workflows=sources,
        )
        if account.get("id"):
            yield RelWrite(
                src_id=str(account["id"]),
                rel="TRANSACTS",
                dst_id=str(beneficiary["id"]),
                attrs={"amount_gbp": float(claim.get("amount_gbp") or 0.0)},
            )

    if receiving_psp.get("id"):
        yield EntityWrite(
            kind="Organisation",
            id=str(receiving_psp["id"]),
            attrs={
                "name": str(receiving_psp.get("display_name") or receiving_psp["id"]),
                "kind": "payment-service-provider",
                "attributes": _json({"status": receiving_psp.get("status")}),
            },
            source_workflows=sources,
        )
        if beneficiary.get("id"):
            yield RelWrite(
                src_id=str(beneficiary["id"]),
                rel="BELONGS_TO",
                dst_id=str(receiving_psp["id"]),
            )

    # The corporate holder is the seam where a retail fraud claim and the
    # wholesale book resolve to one client.
    if corporate.get("id"):
        yield EntityWrite(
            kind="Organisation",
            id=str(corporate["id"]),
            attrs={
                "name": str(corporate.get("display_name") or corporate["id"]),
                "kind": "corporate-client",
                "jurisdiction": str(corporate.get("jurisdiction") or ""),
                "risk_band": str(corporate.get("risk_band") or ""),
                "attributes": _json({"sector": corporate.get("sector")}),
            },
            source_workflows=sources,
        )
        if beneficiary.get("id"):
            yield RelWrite(
                src_id=str(beneficiary["id"]),
                rel="OWNS",
                dst_id=str(corporate["id"]),
            )

    selected = _dict(hitl.get("selected_option"))
    money_id = f"{workflow_id}-reimbursement"
    if selected.get("value_gbp") is not None:
        yield EntityWrite(
            kind="Money",
            id=money_id,
            attrs={
                "amount": float(selected.get("value_gbp") or 0.0),
                "currency": "GBP",
                "kind": "reimbursement",
                "attributes": _json({"option_id": selected.get("option_id")}),
            },
            source_workflows=sources,
        )
        if claim.get("id"):
            yield RelWrite(src_id=money_id, rel="OWED_BY", dst_id=str(claim["id"]))

    approval = _dict(payload.get("approval"))
    if approval.get("decision"):
        decided_on: list[str] = [money_id]
        if customer.get("id"):
            decided_on.append(str(customer["id"]))
        if beneficiary.get("id"):
            decided_on.append(str(beneficiary["id"]))
        yield DecisionWrite(
            workflow_id=workflow_id,
            phase="Decide Reimbursement",
            persona_role=FRAUD_HITL_PERSONA,
            verdict=str(approval.get("decision")),
            reason=str(approval.get("rationale") or approval.get("reason") or ""),
            decided_at=datetime.now(timezone.utc).isoformat(),
            source_event=FRAUD_HITL_EVENT,
            attributes={
                "selected_option_id": approval.get("selected_option_id"),
                "decision_id": approval.get("decision_id"),
                "governing_rule_id": _dict(hitl.get("authority")).get(
                    "governing_rule_id"
                ),
            },
            decided_on=tuple(decided_on),
        )

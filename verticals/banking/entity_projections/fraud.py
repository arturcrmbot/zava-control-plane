"""APP fraud reimbursement entity projection.

Reads the payload shape the workflow store actually persists, which differs
by lifecycle stage:

* suspended at the gate: ``hitl_context`` carries the full decision context;
* completed: ``observation`` at the top level, the orchestration output under
  ``evidence`` (with ``approval`` and ``hitl_context``), the command under
  ``decision`` and the world evaluation under ``outcome``;
* refused by the authority matrix: ``observation`` only.

Only observed evidence is projected. Absent evidence yields fewer records,
never invented ones.
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
_HITL_PHASE = "Decide Reimbursement"


def _json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, default=str)


def _dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _contexts(payload: dict[str, Any]) -> list[dict[str, Any]]:
    """Every decision context the payload holds, most authoritative first."""
    evidence = _dict(payload.get("evidence"))
    return [
        context
        for context in (
            _dict(evidence.get("hitl_context")),
            _dict(payload.get("hitl_context")),
        )
        if context
    ]


def _observation(payload: dict[str, Any]) -> dict[str, Any]:
    observation = _dict(payload.get("observation"))
    if observation:
        return observation
    for context in _contexts(payload):
        observation = _dict(context.get("observation"))
        if observation:
            return observation
    evidence = _dict(payload.get("evidence"))
    return _dict(_dict(evidence.get("workflow_evidence")).get("observation"))


def _selected_option(payload: dict[str, Any]) -> dict[str, Any]:
    for context in _contexts(payload):
        option = _dict(context.get("selected_option"))
        if option:
            return option
    command = _dict(_dict(payload.get("decision")).get("command"))
    command_payload = _dict(command.get("payload"))
    if command_payload.get("option_id"):
        return {
            "option_id": command_payload.get("option_id"),
            "value_gbp": command_payload.get("value_gbp"),
        }
    return {}


def _governing_rule(payload: dict[str, Any]) -> str | None:
    for context in _contexts(payload):
        rule = _dict(context.get("authority")).get("governing_rule_id")
        if rule:
            return str(rule)
    return None


def _decisions(payload: dict[str, Any]) -> list[dict[str, Any]]:
    """Governed decisions this workflow actually recorded.

    A persona-responder decision is persisted under ``decisions``. A decision
    a person made through the operator surface arrives as the approval the
    orchestration validated, under ``evidence.approval``.
    """
    recorded = [entry for entry in _list(payload.get("decisions")) if isinstance(entry, dict)]
    if recorded:
        return [
            {
                "phase": entry.get("phase") or _HITL_PHASE,
                "persona_role": entry.get("persona_role") or FRAUD_HITL_PERSONA,
                "verdict": entry.get("verdict"),
                "reason": entry.get("reason") or "",
                "decided_at": entry.get("decided_at"),
                "source_event": entry.get("source_event") or FRAUD_HITL_EVENT,
                "decided_via": "persona",
            }
            for entry in recorded
            if entry.get("verdict")
        ]
    approval = _dict(_dict(payload.get("evidence")).get("approval"))
    if approval.get("decision"):
        return [
            {
                "phase": _HITL_PHASE,
                "persona_role": approval.get("persona") or FRAUD_HITL_PERSONA,
                "verdict": approval.get("decision"),
                "reason": approval.get("rationale")
                or approval.get("reason")
                or "approved at the reimbursement gate",
                "decided_at": approval.get("decided_at"),
                "source_event": FRAUD_HITL_EVENT,
                "decided_via": "operator",
            }
        ]
    return []


def project(workflow: Any) -> Generator[EntityWrite | RelWrite | DecisionWrite, None, None]:
    workflow_id = getattr(workflow, "id", None)
    if not isinstance(workflow_id, str) or not workflow_id:
        return

    payload = _dict(getattr(workflow, "payload", None))
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
                    {"sort_code": account.get("sort_code"), "status": account.get("status")}
                ),
            },
            source_workflows=sources,
        )
        if customer.get("id"):
            yield RelWrite(src_id=str(customer["id"]), rel="HOLDS_ACCOUNT", dst_id=str(account["id"]))

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
            yield RelWrite(src_id=str(beneficiary["id"]), rel="BELONGS_TO", dst_id=str(receiving_psp["id"]))

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
            yield RelWrite(src_id=str(beneficiary["id"]), rel="OWNS", dst_id=str(corporate["id"]))

    selected = _selected_option(payload)
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

    decided_on = tuple(
        entity_id
        for entity_id in (
            money_id if selected.get("value_gbp") is not None else None,
            customer.get("id"),
            beneficiary.get("id"),
        )
        if entity_id
    )
    governing_rule = _governing_rule(payload)
    for decision in _decisions(payload):
        yield DecisionWrite(
            workflow_id=workflow_id,
            phase=str(decision["phase"]),
            persona_role=str(decision["persona_role"]),
            verdict=str(decision["verdict"]),
            reason=str(decision["reason"]),
            decided_at=str(
                decision.get("decided_at") or datetime.now(timezone.utc).isoformat()
            ),
            source_event=str(decision["source_event"]),
            attributes={
                "selected_option_id": selected.get("option_id"),
                "governing_rule_id": governing_rule,
                "decided_via": decision["decided_via"],
            },
            decided_on=decided_on,
        )

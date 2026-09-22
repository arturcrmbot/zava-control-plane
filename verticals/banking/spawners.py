"""Pack-owned spawners for the supporting processes.

The ramp loop imports these by dotted path from each Domain's ``spawn_fn``.
They are what makes the bank look staffed: every interval, a new synthetic
case arrives and an orchestration starts without anyone pressing anything.

Nothing global is patched -- these live in the pack and only the pack's
domains name them.
"""
from __future__ import annotations

import random

from api.server.services.durable_client import schedule_new_orchestration
from api.server.services.synthetic_data import _now_with_jitter
from api.server.state import app_state
from api.shared.types import Workflow
from verticals.banking.support_constants import (
    MERCHANT_ORCHESTRATOR,
    MERCHANT_WORKFLOW_ID_PREFIX,
    MERCHANT_WORKFLOW_TYPE,
    MULE_ORCHESTRATOR,
    MULE_WORKFLOW_ID_PREFIX,
    MULE_WORKFLOW_TYPE,
)

_RISK_BANDS = ("low", "medium", "medium", "high")
_SECTORS = (
    "logistics", "wholesale", "construction", "hospitality",
    "professional-services", "technology",
)

_mule_seq = 0
_merchant_seq = 0
_rng = random.Random(1_729)


def _build_workflow(
    workflow_id: str,
    workflow_type: str,
    first_phase: str,
    case: dict,
) -> Workflow:
    created_at, sla = _now_with_jitter()
    return Workflow(
        id=workflow_id,
        type=workflow_type,
        current_phase=first_phase,
        created_at=created_at,
        sla_due_at=sla,
        jurisdiction="SYN-UK-Zava",
        agency="Zava Bank",
        payload={"case": case},
    )


async def _spawn(
    *,
    workflow_id: str,
    workflow_type: str,
    orchestrator: str,
    first_phase: str,
    case: dict,
) -> str:
    workflow = _build_workflow(workflow_id, workflow_type, first_phase, case)
    app_state.store.upsert_workflow(workflow)
    payload = {
        "workflow_id": workflow_id,
        "type": workflow_type,
        "case": case,
    }
    try:
        result = await schedule_new_orchestration(payload, function_name=orchestrator)
        workflow.orchestration_instance_id = result.get("id")
        app_state.store.upsert_workflow(workflow)
    except Exception as exc:  # noqa: BLE001 - surfaced, never silently dropped
        print(f"[banking] failed to schedule {workflow_id}: {exc}")
    return workflow_id


async def spawn_mule_investigation_workflow(scenario: str | None = None) -> str:
    """Open a synthetic mule-account investigation."""
    global _mule_seq
    _mule_seq += 1
    workflow_id = f"{MULE_WORKFLOW_ID_PREFIX}-{_mule_seq:04d}"
    case = {
        "id": f"SYN-MULE-CASE-{_mule_seq:04d}",
        "subject_id": f"SYN-BENE-{_rng.randint(1, 240):03d}",
        "subject_kind": "beneficiary",
        "risk_band": scenario or _rng.choice(_RISK_BANDS),
        "linked_claim_count": _rng.randint(1, 6),
        "balance_gbp": float(_rng.randint(1_200, 140_000)),
        "version": 1,
    }
    return await _spawn(
        workflow_id=workflow_id,
        workflow_type=MULE_WORKFLOW_TYPE,
        orchestrator=MULE_ORCHESTRATOR,
        first_phase="Assemble Beneficiary Evidence",
        case=case,
    )


async def spawn_merchant_onboarding_workflow(scenario: str | None = None) -> str:
    """Open a synthetic merchant onboarding risk assessment."""
    global _merchant_seq
    _merchant_seq += 1
    workflow_id = f"{MERCHANT_WORKFLOW_ID_PREFIX}-{_merchant_seq:04d}"
    case = {
        "id": f"SYN-MER-CASE-{_merchant_seq:04d}",
        "subject_id": f"SYN-MERCHANT-{_merchant_seq:04d}",
        "subject_kind": "merchant",
        "risk_band": scenario or _rng.choice(_RISK_BANDS),
        "sector": _rng.choice(_SECTORS),
        "projected_monthly_volume_gbp": float(_rng.randint(8_000, 900_000)),
        "version": 1,
    }
    return await _spawn(
        workflow_id=workflow_id,
        workflow_type=MERCHANT_WORKFLOW_TYPE,
        orchestrator=MERCHANT_ORCHESTRATOR,
        first_phase="Collect Merchant Application",
        case=case,
    )

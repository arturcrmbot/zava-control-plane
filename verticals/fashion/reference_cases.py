from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

from verticals.fashion.process_profiles import FashionProcessProfile


DEFAULT_ACTIONS = {
    "inventory-rebalancing": "inventory.transfer",
    "demand-spike-response": "reallocate",
    "promotion-readiness": "ready-channel",
    "markdown-governance": "recommend-markdown",
    "supplier-delay-recovery": "split",
    "fulfilment-exception-resolution": "reroute",
    "marketplace-seller-exception": "suppress-offer",
    "returns-disposition": "restock",
}


@dataclass(slots=True)
class FashionProcessCase:
    id: str
    workflow_type: str
    subject_ids: tuple[str, ...]
    status: str
    facts: dict[str, Any]
    allowed_actions: tuple[str, ...]
    recommended_action: str
    outcome: dict[str, Any] | None = None


def process_case_view(case: FashionProcessCase) -> dict[str, Any]:
    data = asdict(case)
    data["subject_ids"] = list(case.subject_ids)
    data["allowed_actions"] = list(case.allowed_actions)
    return data


def build_reference_case(
    scenario: Any,
    profile: FashionProcessProfile,
    case_id: str,
) -> FashionProcessCase:
    subject_ids, facts = scenario.case_evidence(profile.workflow_type)
    recommended_action = scenario.recommended_action(
        profile.workflow_type, tuple(subject_ids)
    )
    return FashionProcessCase(
        id=case_id,
        workflow_type=profile.workflow_type,
        subject_ids=tuple(subject_ids),
        status="open",
        facts=facts,
        allowed_actions=profile.allowed_actions,
        recommended_action=recommended_action,
    )


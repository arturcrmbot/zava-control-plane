from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

from verticals.telco.process_profiles import (
    STANDARD_PROCESS_PROFILES,
    TelcoProcessProfile,
)


@dataclass(slots=True)
class TelcoProcessCase:
    id: str
    workflow_type: str
    subject_ids: tuple[str, ...]
    status: str
    facts: dict[str, object]
    allowed_actions: tuple[str, ...]
    outcome: dict[str, object] | None = None


def process_case_view(case: TelcoProcessCase) -> dict[str, Any]:
    data = asdict(case)
    data["subject_ids"] = list(case.subject_ids)
    data["allowed_actions"] = list(case.allowed_actions)
    return data


def _case(
    profile: TelcoProcessProfile,
    case_id: str,
    subject_ids: list[str],
    facts: dict[str, object],
) -> TelcoProcessCase:
    return TelcoProcessCase(
        id=case_id,
        workflow_type=profile.workflow_type,
        subject_ids=tuple(subject_ids),
        status="open",
        facts={
            **facts,
            "source_process": profile.source_id,
            "process_focus": profile.display_name,
            "risk_score": float(facts.get("risk_score") or 0.75),
        },
        allowed_actions=(profile.command_type,),
    )


def build_network_case(
    profile: TelcoProcessProfile,
    scenario: Any,
    case_id: str,
) -> TelcoProcessCase:
    site = max(
        scenario.sites.values(),
        key=lambda item: (item.utilization, item.id),
    )
    assets = [
        asset
        for asset in scenario.assets.values()
        if asset.site_id == site.id
    ][:2]
    return _case(
        profile,
        case_id,
        [site.id, *(asset.id for asset in assets)],
        {
            "site": scenario._site_view(site),
            "assets": [scenario._asset_view(asset) for asset in assets],
            "risk_score": max(
                [asset.failure_probability for asset in assets] or [0.5]
            ),
        },
    )


def build_operations_case(
    profile: TelcoProcessProfile,
    scenario: Any,
    case_id: str,
) -> TelcoProcessCase:
    technician = next(iter(scenario.technicians.values()))
    stock = next(iter(scenario.spare_stocks.values()))
    return _case(
        profile,
        case_id,
        [technician.id, stock.id],
        {
            "technician": scenario._technician_view(technician),
            "spare_stock": asdict(stock),
            "risk_score": 0.65,
        },
    )


def build_customer_case(
    profile: TelcoProcessProfile,
    scenario: Any,
    case_id: str,
) -> TelcoProcessCase:
    account = next(
        (
            item
            for item in scenario.accounts.values()
            if item.vulnerable
        ),
        next(iter(scenario.accounts.values())),
    )
    subscription = next(
        item
        for item in scenario.subscriptions.values()
        if item.account_id == account.id
    )
    return _case(
        profile,
        case_id,
        [account.id, subscription.id],
        {
            "account": scenario._account_view(account),
            "subscription": asdict(subscription),
            "customer_interaction": {
                "id": f"INT-{account.id}",
                "channel": "digital",
                "intent": profile.workflow_type,
            },
            "risk_score": 0.8 if account.vulnerable else 0.6,
        },
    )


def build_order_case(
    profile: TelcoProcessProfile,
    scenario: Any,
    case_id: str,
) -> TelcoProcessCase:
    order = next(iter(scenario.orders.values()))
    account = scenario.accounts[order.account_id]
    site = scenario.sites[order.requested_site_id]
    return _case(
        profile,
        case_id,
        [order.id, account.id, site.id],
        {
            "service_order": asdict(order),
            "account": scenario._account_view(account),
            "site": scenario._site_view(site),
            "risk_score": 0.7 if order.status == "infeasible" else 0.4,
        },
    )


def build_revenue_case(
    profile: TelcoProcessProfile,
    scenario: Any,
    case_id: str,
) -> TelcoProcessCase:
    account = next(iter(scenario.accounts.values()))
    return _case(
        profile,
        case_id,
        [account.id],
        {
            "account": scenario._account_view(account),
            "invoice": {
                "id": f"INV-{account.id}",
                "amount_gbp": 125.0,
                "status": "exception",
            },
            "usage_record": {
                "service_units": 450,
                "rated_units": 420,
            },
            "payment": {"status": "due", "days_overdue": 14},
            "risk_score": 0.75,
        },
    )


def build_identity_case(
    profile: TelcoProcessProfile,
    scenario: Any,
    case_id: str,
) -> TelcoProcessCase:
    account = next(iter(scenario.accounts.values()))
    subscription = next(
        item
        for item in scenario.subscriptions.values()
        if item.account_id == account.id
    )
    return _case(
        profile,
        case_id,
        [account.id, subscription.id],
        {
            "account": scenario._account_view(account),
            "identity_case": {
                "id": f"IDENT-{account.id}",
                "evidence_status": "review",
                "risk_flags": ["synthetic-reference-flag"],
            },
            "sim": {
                "id": f"SIM-{subscription.id}",
                "status": "pending-verification",
            },
            "risk_score": 0.8,
        },
    )


def build_plan_case(
    profile: TelcoProcessProfile,
    scenario: Any,
    case_id: str,
) -> TelcoProcessCase:
    site = max(
        scenario.sites.values(),
        key=lambda item: (item.traffic_mbps, item.id),
    )
    account = next(iter(scenario.accounts.values()))
    return _case(
        profile,
        case_id,
        [site.id, account.id],
        {
            "site": scenario._site_view(site),
            "account": scenario._account_view(account),
            "planning_horizon_days": 90,
            "risk_score": 0.7,
        },
    )


NETWORK_CASES = {
    "network-slice-assurance",
    "energy-optimization",
    "backhaul-optimization",
    "core-network-anomaly-management",
    "spectrum-interference-management",
    "network-security-response",
}
PLAN_CASES = {
    "ran-capacity-planning",
    "network-configuration-validation",
    "rollout-site-planning",
    "network-change-release",
    "experience-benchmarking",
    "customer-experience-twin",
}
FIELD_CASES = {
    "spares-inventory-optimization",
    "site-asset-health-monitoring",
}
CUSTOMER_CASES = {
    "proactive-service-assurance",
    "contact-centre-agent-assist",
    "autonomous-self-service",
    "next-best-action",
    "complaint-nps-closed-loop",
    "device-lifecycle-upgrade",
    "roaming-experience-steering",
}
ORDER_CASES = {
    "service-provisioning-activation",
    "number-sim-porting",
}
REVENUE_CASES = {
    "billing-dispute-resolution",
    "revenue-assurance",
    "collections-dunning",
}
IDENTITY_CASES = {
    "fraud-prevention",
    "customer-onboarding-kyc",
}

CASE_BUILDERS_BY_WORKFLOW = {
    **{name: build_network_case for name in NETWORK_CASES},
    **{name: build_plan_case for name in PLAN_CASES},
    **{name: build_operations_case for name in FIELD_CASES},
    **{name: build_customer_case for name in CUSTOMER_CASES},
    **{name: build_order_case for name in ORDER_CASES},
    **{name: build_revenue_case for name in REVENUE_CASES},
    **{name: build_identity_case for name in IDENTITY_CASES},
}

if set(CASE_BUILDERS_BY_WORKFLOW) != set(
    profile.workflow_type
    for profile in STANDARD_PROCESS_PROFILES.values()
):
    raise ValueError("reference case builders do not cover all standard profiles")

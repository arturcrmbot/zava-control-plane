from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

from verticals.telco.process_profiles import TelcoProcessProfile


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


def build_commercial_case(
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
            "subscription": asdict(subscription),
            "value": 75.0 if account.vulnerable else 25.0,
            "risk_score": 0.8 if account.vulnerable else 0.6,
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


CASE_BUILDERS = {
    "network": build_network_case,
    "operations": build_operations_case,
    "commercial": build_commercial_case,
    "plan": build_plan_case,
}

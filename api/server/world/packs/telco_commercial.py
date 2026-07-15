"""Deterministic commercial actors for the Telco world."""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(slots=True)
class CustomerAccount:
    id: str
    subscriber_id: str
    segment: str
    vulnerable: bool = False
    approval_required: bool = False
    total_credits: float = 0.0
    notification_ids: list[str] = field(default_factory=list)
    credit_ids: list[str] = field(default_factory=list)


@dataclass(slots=True)
class ServiceSubscription:
    id: str
    account_id: str
    subscriber_id: str
    site_id: str
    product: str
    status: str = "active"


@dataclass(slots=True)
class ServiceOrder:
    id: str
    account_id: str
    product: str
    requested_site_id: str
    status: str
    reason: str | None = None


@dataclass(slots=True)
class Notification:
    id: str
    account_id: str
    channel: str
    message: str
    trace_id: str


@dataclass(slots=True)
class CreditAdjustment:
    id: str
    account_id: str
    amount: float
    trace_id: str
    authority_approved: bool

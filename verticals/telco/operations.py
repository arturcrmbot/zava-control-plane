"""Deterministic operational actors for the Telco world.

Mirrors ``commercial.py``: plain slotted dataclasses only, no behaviour. These
back the outage, maintenance, field-dispatch, care-ticket and retention
workflows layered on top of the network-incident scenario in later tasks.
``NetworkScenario`` (see ``world.py``) owns creation, dynamics and views.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class NetworkAsset:
    id: str
    site_id: str
    kind: str
    health: float
    temperature_c: float
    load: float
    failure_probability: float = 0.0
    status: str = "healthy"


@dataclass(slots=True)
class WeatherEvent:
    id: str
    region: str
    severity: float
    power_risk: float
    cooling_risk: float
    starts_at: float
    ends_at: float


@dataclass(slots=True)
class WorkOrder:
    id: str
    site_id: str
    asset_id: str
    kind: str
    priority: str
    required_skill: str
    required_spare: str
    due_at: float
    status: str = "open"
    technician_id: str | None = None


@dataclass(slots=True)
class Technician:
    id: str
    region: str
    skills: tuple[str, ...]
    status: str = "available"
    assigned_work_order_id: str | None = None


@dataclass(slots=True)
class SpareStock:
    id: str
    region: str
    part_kind: str
    quantity: int
    reorder_point: int


@dataclass(slots=True)
class CareTicket:
    id: str
    account_id: str
    subscription_id: str
    incident_trace_id: str
    category: str
    severity: str
    status: str = "open"
    root_cause: str | None = None


@dataclass(slots=True)
class ExperienceEpisode:
    id: str
    account_id: str
    source_trace_id: str
    kind: str
    impact_score: float
    occurred_at: float


@dataclass(slots=True)
class RetentionOffer:
    id: str
    account_id: str
    reason: str
    value_gbp: float
    offer_kind: str
    status: str = "proposed"

"""Pack-local world entities for the Fashion supporting workflows.

Each supporting reference case reads one of these versioned records and applies
a workflow-specific typed mutation, so a completed workflow leaves observable,
deterministic state behind rather than a generic simulated pass.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class Order:
    id: str
    sku_id: str
    location_id: str
    quantity: int
    status: str
    allocation_location_id: str | None = None
    version: int = 1


@dataclass(slots=True)
class Reservation:
    id: str
    location_id: str
    sku_id: str
    reserved_units: int
    status: str
    version: int = 1


@dataclass(slots=True)
class Promotion:
    id: str
    sku_id: str
    stock_ready: bool
    content_ready: bool
    channels_ready: tuple[str, ...]
    status: str
    version: int = 1


@dataclass(slots=True)
class Delivery:
    id: str
    supplier_id: str
    style_id: str
    delay_days: int
    recovery_plan: str | None
    status: str
    version: int = 1


@dataclass(slots=True)
class Return:
    id: str
    sku_id: str
    condition: str
    disposition: str | None
    recovery_value_gbp: float
    status: str
    version: int = 1


@dataclass(slots=True)
class SellerOffer:
    id: str
    seller_id: str
    sku_id: str
    sla_breach_hours: int
    suppressed: bool
    escalated: bool
    status: str
    version: int = 1


@dataclass(slots=True)
class MarkdownRecommendation:
    id: str
    style_id: str
    location_id: str
    recommendation: str | None
    status: str
    version: int = 1


@dataclass(slots=True)
class DemandSignal:
    """Deterministic weather/campaign demand signal state.

    ``recent_uplift_units`` records the magnitude the campaign added to the
    recent (days 8-14) window of the seeded history so its contribution can be
    derived, and ``active`` toggles the signal for causal what-if evaluation.
    """

    id: str
    sku_ids: tuple[str, ...]
    region: str
    channel: str | None
    kind: str
    active: bool
    recent_uplift_units: int

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any


@dataclass(slots=True)
class Location:
    id: str
    name: str
    kind: str
    country: str
    region: str


@dataclass(slots=True)
class Brand:
    id: str
    name: str
    relationship: str


@dataclass(slots=True)
class Style:
    id: str
    brand_id: str
    name: str
    lifecycle: str


@dataclass(slots=True)
class SKU:
    id: str
    style_id: str
    colour: str
    size: str
    retail_price_gbp: float


@dataclass(slots=True)
class Customer:
    id: str
    home_region: str
    location_id: str
    status: str
    last_event_id: str | None = None


@dataclass(slots=True)
class Staff:
    id: str
    name: str
    role: str
    location_id: str
    status: str
    serving_customer_id: str | None = None
    last_event_id: str | None = None


@dataclass(slots=True)
class InventoryPosition:
    id: str
    location_id: str
    sku_id: str
    ownership: str
    on_hand: int
    reserved: int
    safety_stock: int
    version: int
    retail_price_gbp: float
    status: str = "available"
    last_event_id: str | None = None

    @property
    def available(self) -> int:
        return max(0, self.on_hand - self.reserved)


@dataclass(slots=True)
class Order:
    id: str
    customer_id: str
    sku_id: str
    quantity: int
    location_id: str
    channel: str
    status: str
    created_at: float
    last_event_id: str | None = None


@dataclass(slots=True)
class Delivery:
    id: str
    location_id: str
    supplier_id: str
    status: str
    expected_at: float
    last_event_id: str | None = None


@dataclass(slots=True)
class Return:
    id: str
    order_id: str
    customer_id: str
    sku_id: str
    location_id: str
    status: str
    disposition: str | None = None
    last_event_id: str | None = None


@dataclass(slots=True)
class Promotion:
    id: str
    name: str
    status: str
    sku_ids: tuple[str, ...]


@dataclass(slots=True)
class SellerOffer:
    id: str
    seller_id: str
    sku_id: str
    status: str


@dataclass(slots=True)
class ProcessCase:
    id: str
    workflow_type: str
    subject_ids: tuple[str, ...]
    status: str
    facts: dict[str, object]
    allowed_actions: tuple[str, ...]
    outcome: dict[str, object] | None = None


def view(actor: Any) -> dict[str, Any]:
    data = asdict(actor)
    for key, value in tuple(data.items()):
        if isinstance(value, tuple):
            data[key] = list(value)
    if isinstance(actor, InventoryPosition):
        data["available"] = actor.available
    return data


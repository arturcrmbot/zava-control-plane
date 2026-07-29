from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class ElectronicsReferenceCase:
    id: str
    workflow_type: str
    subject_ids: tuple[str, ...]
    facts: dict[str, object]
    allowed_actions: tuple[str, ...]


def _case(
    case_id: str,
    workflow_type: str,
    subjects: tuple[str, ...],
    action: str,
    **facts: object,
) -> ElectronicsReferenceCase:
    return ElectronicsReferenceCase(
        id=case_id,
        workflow_type=workflow_type,
        subject_ids=subjects,
        facts=facts,
        allowed_actions=(action,),
    )


ELECTRONICS_REFERENCE_CASES = {
    "inventory-rebalancing": _case(
        "CASE-REBAL-001",
        "inventory-rebalancing",
        ("SKU-APEX-X1-GRAPHITE-16", "DC-UK-MID-01", "STORE-UK-LON-01"),
        "inventory.transfer",
        quantity=24,
        ownership="owned",
        retail_value_gbp=35_976.0,
    ),
    "demand-spike-response": _case(
        "CASE-DEMAND-001",
        "demand-spike-response",
        ("SKU-VOLT-X1-MIDNIGHT-14", "STORE-UK-MAN-01"),
        "allocation.adjust",
        velocity_ratio=2.4,
    ),
    "promotion-readiness": _case(
        "CASE-PROMO-001",
        "promotion-readiness",
        ("PROMO-LAUNCH-01", "SKU-NIMBUS-X1-CHARCOAL-14"),
        "promotion.prepare",
        window_hours=24,
    ),
    "markdown-governance": _case(
        "CASE-MARKDOWN-001",
        "markdown-governance",
        ("SKU-NORTH-X1-SLATE-16",),
        "markdown.recommend",
        weeks_of_supply=18.0,
    ),
    "supplier-delay-recovery": _case(
        "CASE-SUPPLY-001",
        "supplier-delay-recovery",
        ("SUPPLIER-07", "DELIVERY-IN-0042"),
        "supplier.recover",
        delay_hours=48,
    ),
    "fulfilment-exception-resolution": _case(
        "CASE-FULFIL-001",
        "fulfilment-exception-resolution",
        ("ORDER-0042", "CUST-0042"),
        "fulfilment.resolve",
        promised_service="next-day",
    ),
    "marketplace-seller-exception": _case(
        "CASE-SELLER-001",
        "marketplace-seller-exception",
        ("SELLER-03", "OFFER-MKT-0003"),
        "seller.offer.suppress",
        stock_accuracy=0.62,
    ),
    "returns-disposition": _case(
        "CASE-RETURN-001",
        "returns-disposition",
        ("RETURN-0042", "ORDER-0042", "SKU-CREST-X1-ONYX-15"),
        "return.disposition",
        condition="repairable",
    ),
}


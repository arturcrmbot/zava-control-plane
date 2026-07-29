from __future__ import annotations

from typing import Any


HERO_SKU = "SKU-APEX-X1-GRAPHITE-16"
SOURCE_LOCATION = "DC-UK-MID-01"
DESTINATION_LOCATION = "STORE-UK-LON-01"
DESTINATION_AVAILABLE_THRESHOLD = 8
SOURCE_AVAILABLE_THRESHOLD = 60
DEMAND_SALES_THRESHOLD = 4


def inventory_measurements(scenario: Any) -> dict[str, float | int]:
    source = scenario.inventory[(SOURCE_LOCATION, HERO_SKU)]
    destination = scenario.inventory[(DESTINATION_LOCATION, HERO_SKU)]
    return {
        "source_available": source.available,
        "destination_available": destination.available,
        "source_safety_stock": source.safety_stock,
        "destination_safety_stock": destination.safety_stock,
        "demand_sales": scenario.hero_sales,
        "weeks_of_supply": round(destination.available / max(scenario.hero_sales, 1), 2),
        "transfer_cost_gbp": 180.0,
        "expected_recovered_margin_gbp": 864.0,
        "fairness_score": 0.94,
    }


def inventory_imbalance_crossed(scenario: Any) -> bool:
    measurements = inventory_measurements(scenario)
    return bool(
        measurements["destination_available"]
        <= DESTINATION_AVAILABLE_THRESHOLD
        and measurements["source_available"] >= SOURCE_AVAILABLE_THRESHOLD
        and measurements["demand_sales"] >= DEMAND_SALES_THRESHOLD
    )


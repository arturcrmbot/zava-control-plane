from __future__ import annotations

KNOWN_CAPABILITIES = frozenset(
    {"blueprint", "compose", "knowledge", "memory", "world"}
)
KNOWN_LENSES = frozenset(
    {
        "agency-operations",
        "telco-network",
        "customer-impact",
        "field-operations",
        "process-library",
        "order",
        "control",
    }
)

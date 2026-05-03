"""Graph-shape adapter for the fleet-vendor-kyc-kyc-diligence validator.

In-graph validators return `{"ok": bool, ...}` so TrackedExecutor can emit
`validator.blocked` cleanly. Mirrors validate_classification_schema_node.py.
"""
from __future__ import annotations


async def execute(input: dict) -> dict:
    payload = input.get("kyc_diligence") or {}

    registry_id = payload.get("registry_id")
    if not isinstance(registry_id, str) or not registry_id:
        return {
            "ok": False,
            "blocked_reason": f"registry_id must be a non-empty string; got {registry_id!r}",
            "kyc_diligence": payload,
        }

    countries_screened = payload.get("countries_screened")
    if not isinstance(countries_screened, list) or len(countries_screened) == 0:
        return {
            "ok": False,
            "blocked_reason": (
                "countries_screened must be a non-empty list (at least the "
                "country of incorporation)"
            ),
            "kyc_diligence": payload,
        }

    entity_sanctions_hits = payload.get("entity_sanctions_hits")
    if not isinstance(entity_sanctions_hits, list):
        return {
            "ok": False,
            "blocked_reason": "entity_sanctions_hits must be a list (empty if clean)",
            "kyc_diligence": payload,
        }

    filings_24m_count = payload.get("filings_24m_count")
    if not isinstance(filings_24m_count, int) or filings_24m_count < 0:
        return {
            "ok": False,
            "blocked_reason": (
                f"filings_24m_count must be a non-negative int; got {filings_24m_count!r}"
            ),
            "kyc_diligence": payload,
        }

    return {
        "ok": True,
        "kyc_diligence": payload,
        "registry_id": registry_id,
        "entity_sanctions_hits": entity_sanctions_hits,
    }

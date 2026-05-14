"""
Contract renewal activity functions — registered as Azure Durable
Functions activity triggers (see GRADUATION.md for the function_app.py
diff). Each runs synchronously and wraps an async MAF Workflow run inside
asyncio.run.
"""
from __future__ import annotations
import asyncio

from api.functions.workflows.activities import _run_workflow
from api.functions.graphs import (
    build_fleet_contract_renewal_contract_lookup_workflow,
    build_fleet_contract_renewal_market_benchmarker_workflow,
    build_fleet_contract_renewal_renewal_terms_drafter_workflow,
)


def fleet_contract_renewal_contract_lookup_activity(payload: dict) -> dict:
    """Phase 1 — read the contract record (parties, value, term, category, region) from the contract repository."""
    return asyncio.run(_run_workflow(
        build_fleet_contract_renewal_contract_lookup_workflow,
        payload,
        "Contract Lookup",
    ))


def fleet_contract_renewal_market_benchmarker_activity(payload: dict) -> dict:
    """Phase 2 — agent benchmarks the contract against comparables, market quotes and amendment history; validator guards schema."""
    return asyncio.run(_run_workflow(
        build_fleet_contract_renewal_market_benchmarker_workflow,
        payload,
        "Market Benchmarker",
    ))


def fleet_contract_renewal_renewal_terms_drafter_activity(payload: dict) -> dict:
    """Phase 3 — agent drafts proposed renewal terms with cited clauses and per-line delta; validator guards schema."""
    return asyncio.run(_run_workflow(
        build_fleet_contract_renewal_renewal_terms_drafter_workflow,
        payload,
        "Renewal Terms Drafter",
    ))

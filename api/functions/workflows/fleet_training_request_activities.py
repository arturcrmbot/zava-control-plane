"""
Training request activity functions — registered as Azure Durable Functions
activity triggers (see GRADUATION.md for the function_app.py diff). Each
runs synchronously and wraps an async MAF Workflow run inside asyncio.run.

Only the two deterministic phases (request_intake, book) need per-phase
MAF graph activities here. The agentic phase (eligibility_and_catalogue)
ships as a segment-by-default — its activity triggers live in
function_app.py and call `run_segment_b` directly.
"""
from __future__ import annotations
import asyncio

from api.functions.workflows.activities import _run_workflow
from api.functions.graphs import (
    build_fleet_training_request_request_intake_workflow,
    build_fleet_training_request_book_workflow,
)


def fleet_training_request_request_intake_activity(payload: dict) -> dict:
    """Phase 1 — capture the training request (employee + topic + cost + date)."""
    return asyncio.run(_run_workflow(
        build_fleet_training_request_request_intake_workflow,
        payload,
        "Request Intake",
    ))


def fleet_training_request_book_activity(payload: dict) -> dict:
    """Phase 4 — record the booking (booking_id, vendor, course, start_date)."""
    return asyncio.run(_run_workflow(
        build_fleet_training_request_book_workflow,
        payload,
        "Book",
    ))

"""Phase 4 (Book) graph for Training request.

  deterministic_book -> terminal

Per brief: record the booking on the workflow payload — booking_id,
vendor, course_id, course_start_date — derived from the catalogue match
stamped in Phase 2. Uses the learning_catalogue.reserve_seat stub to
mint a deterministic booking_id.
"""
from __future__ import annotations
from agent_framework import Workflow, WorkflowBuilder

from api.functions.graphs._tracked_executor import TrackedExecutor, TerminalExecutor
from api.server.mcp_tools.learning_catalogue import reserve_seat


async def _book_execute(input: dict) -> dict:
    """Deterministic booking. Reads the catalogue match from the
    eligibility_and_catalogue phase output and reserves a seat. Returns
    the booking record stamped on the workflow payload."""
    intake = input.get("request_intake") or {}
    eac = input.get("eligibility_and_catalogue") or {}
    employee_id = intake.get("employee_id")
    course_id = eac.get("course_id")
    vendor = eac.get("vendor")
    course_start_date = eac.get("course_start_date")

    if not employee_id or not course_id or not course_start_date:
        return {
            "ok": False,
            "blocked_reason": "missing employee_id / course_id / course_start_date",
        }
    booking = reserve_seat(
        course_id=course_id,
        employee_id=employee_id,
        course_start_date=course_start_date,
    )
    return {
        "ok": True,
        "booking_id": booking.get("booking_id"),
        "vendor": vendor,
        "course_id": course_id,
        "course_start_date": course_start_date,
        "seat_no": booking.get("seat_no"),
    }


def build_fleet_training_request_book_workflow() -> Workflow:
    n1 = TrackedExecutor(
        id="book",
        name="deterministic_book",
        executor_type="deterministic",
        fn=_book_execute,
    )
    term = TerminalExecutor(id="terminal")
    return (
        WorkflowBuilder(start_executor=n1)
        .add_edge(n1, term)
        .build()
    )

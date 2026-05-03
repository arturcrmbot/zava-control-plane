"""calendar_service MCP tool — find availability, list rooms, book events.

Stub. Returns deterministic synthetic data keyed on the input(s). No real
upstream call. Replace the bodies of `find_availability`, `get_room_options`,
`book_event` with real calendar (Microsoft Graph / Google Calendar)
calls when wiring to a production tenant.
"""
from __future__ import annotations
import hashlib
import json

from copilot.tools import ToolResult, define_tool
from opentelemetry import trace
from pydantic import BaseModel, Field

from ._otel import traced_tool


# Per-market room pools. Each market has a stable set of synthetic rooms.
_ROOMS_BY_MARKET: dict[str, list[tuple[str, int]]] = {
    "UK": [("LON-RM-301", 4), ("LON-RM-412", 8), ("LON-RM-510", 12)],
    "US": [("NYC-RM-204", 4), ("NYC-RM-318", 6), ("NYC-RM-501", 10)],
    "DE": [("BER-RM-110", 4), ("BER-RM-220", 6), ("BER-RM-330", 8)],
    "FR": [("PAR-RM-101", 4), ("PAR-RM-205", 6), ("PAR-RM-309", 10)],
    "JP": [("TYO-RM-104", 4), ("TYO-RM-208", 6), ("TYO-RM-312", 8)],
}


# --------------------------------------------------------------------------
# find_availability
# --------------------------------------------------------------------------


@traced_tool("calendar_service.find_availability")
def find_availability(
    attendees: list[str],
    duration_minutes: int,
    window_start: str,
    window_days: int,
) -> dict:
    """Find a time slot of `duration_minutes` across all attendees within
    [window_start, window_start + window_days] — stub."""
    span = trace.get_current_span()
    span.set_attribute("wpp.calendar_service.attendee_count", len(attendees))
    span.set_attribute("wpp.calendar_service.duration_minutes", int(duration_minutes))
    span.set_attribute("wpp.calendar_service.window_start", str(window_start))
    span.set_attribute("wpp.calendar_service.window_days", int(window_days))
    return _synth_find_availability(attendees, duration_minutes, window_start, window_days)


def _synth_find_availability(
    attendees: list[str],
    duration_minutes: int,
    window_start: str,
    window_days: int,
) -> dict:
    """Deterministic synthesis. Same inputs -> byte-identical slot."""
    key = "|".join([
        ",".join(sorted(attendees or [])),
        str(duration_minutes),
        str(window_start),
        str(window_days),
    ])
    seed = int(hashlib.sha256(key.encode()).hexdigest()[:8], 16)
    # Pick a day offset within the window (1..window_days) and an hour
    # of day (9..16 — keep within working hours).
    day_offset = 1 + (seed % max(window_days, 1))
    hour_of_day = 9 + ((seed >> 4) % 8)
    # Synthesise an ISO-8601 string by concatenation; we don't actually
    # parse window_start (it's just a label here) so the slot strings
    # are deterministic anchors the agent can quote verbatim.
    base = str(window_start)
    start_iso = f"{base}T{hour_of_day:02d}:00:00+00:00"
    end_minutes = (hour_of_day * 60) + int(duration_minutes)
    end_hour = end_minutes // 60
    end_min = end_minutes % 60
    end_iso = f"{base}T{end_hour:02d}:{end_min:02d}:00+00:00"
    return {
        "attendees": list(attendees or []),
        "duration_minutes": int(duration_minutes),
        "slot": {
            "start": start_iso,
            "end": end_iso,
            "day_offset": day_offset,
        },
    }


class _FindAvailabilityParams(BaseModel):
    attendees: list[str] = Field(description="Employee identifiers attending the meeting")
    duration_minutes: int = Field(description="Meeting length in minutes (e.g. 90)")
    window_start: str = Field(description="ISO date the search window opens (YYYY-MM-DD)")
    window_days: int = Field(description="Window length in calendar days (e.g. 14)")


@define_tool(
    name="calendar_service_find_availability",
    description=(
        "Find a meeting slot of duration_minutes across all attendees within "
        "a window starting at window_start of length window_days. Returns "
        "the first matching slot as start + end ISO timestamps. "
        "Stub: returns deterministic synthetic data."
    ),
)
def calendar_service_find_availability_tool(params: _FindAvailabilityParams) -> ToolResult:
    try:
        result = find_availability(
            params.attendees,
            params.duration_minutes,
            params.window_start,
            params.window_days,
        )
        return ToolResult(text_result_for_llm=json.dumps(result, ensure_ascii=False))
    except Exception as ex:
        return ToolResult(text_result_for_llm="", result_type="failure", error=str(ex))


# --------------------------------------------------------------------------
# get_room_options
# --------------------------------------------------------------------------


@traced_tool("calendar_service.get_room_options")
def get_room_options(market: str, capacity: int) -> dict:
    """List room candidates in `market` with at least `capacity` seats — stub."""
    span = trace.get_current_span()
    span.set_attribute("wpp.calendar_service.market", str(market))
    span.set_attribute("wpp.calendar_service.capacity", int(capacity))
    return _synth_get_room_options(market, capacity)


def _synth_get_room_options(market: str, capacity: int) -> dict:
    """Deterministic. Same (market, capacity) -> same room list."""
    pool = _ROOMS_BY_MARKET.get(market, _ROOMS_BY_MARKET["UK"])
    rooms = [
        {"room_id": rid, "capacity": cap}
        for (rid, cap) in pool
        if cap >= int(capacity)
    ]
    return {
        "market": market,
        "capacity_min": int(capacity),
        "rooms": rooms,
    }


class _GetRoomOptionsParams(BaseModel):
    market: str = Field(description="Office market ISO-2 (e.g. UK, US, DE)")
    capacity: int = Field(description="Minimum room capacity (number of seats)")


@define_tool(
    name="calendar_service_get_room_options",
    description=(
        "List meeting-room options in a given market that meet a minimum "
        "capacity. Use after find_availability to pick a venue. "
        "Stub: returns deterministic synthetic data."
    ),
)
def calendar_service_get_room_options_tool(params: _GetRoomOptionsParams) -> ToolResult:
    try:
        result = get_room_options(params.market, params.capacity)
        return ToolResult(text_result_for_llm=json.dumps(result, ensure_ascii=False))
    except Exception as ex:
        return ToolResult(text_result_for_llm="", result_type="failure", error=str(ex))


# --------------------------------------------------------------------------
# book_event
# --------------------------------------------------------------------------


@traced_tool("calendar_service.book_event")
def book_event(slot: dict, room_id: str, attendees: list[str], subject: str) -> dict:
    """Book a calendar event at `slot` in `room_id` with `attendees` — stub."""
    span = trace.get_current_span()
    span.set_attribute("wpp.calendar_service.room_id", str(room_id))
    span.set_attribute("wpp.calendar_service.attendee_count", len(attendees or []))
    span.set_attribute("wpp.calendar_service.subject", str(subject))
    return _synth_book_event(slot, room_id, attendees, subject)


def _synth_book_event(
    slot: dict, room_id: str, attendees: list[str], subject: str,
) -> dict:
    """Deterministic. Same (slot, room, attendees, subject) -> same event_id."""
    key = "|".join([
        str((slot or {}).get("start") or ""),
        str((slot or {}).get("end") or ""),
        str(room_id),
        ",".join(sorted(attendees or [])),
        str(subject),
    ])
    seed = int(hashlib.sha256(key.encode()).hexdigest()[:8], 16)
    event_id = f"EVT-{seed % 1000000:06d}"
    return {
        "event_id": event_id,
        "confirmation": True,
        "slot": slot or {},
        "room_id": room_id,
        "attendees": list(attendees or []),
        "subject": subject,
    }


class _BookEventParams(BaseModel):
    slot: dict = Field(description="Slot dict with start + end ISO timestamps")
    room_id: str = Field(description="Room identifier from get_room_options")
    attendees: list[str] = Field(description="Employee identifiers to invite")
    subject: str = Field(description="Event subject line")


@define_tool(
    name="calendar_service_book_event",
    description=(
        "Book a calendar event at the given slot in the given room with the "
        "given attendees. Returns event_id + confirmation flag. Use after "
        "find_availability + get_room_options. "
        "Stub: returns deterministic synthetic data."
    ),
)
def calendar_service_book_event_tool(params: _BookEventParams) -> ToolResult:
    try:
        result = book_event(params.slot, params.room_id, params.attendees, params.subject)
        return ToolResult(text_result_for_llm=json.dumps(result, ensure_ascii=False))
    except Exception as ex:
        return ToolResult(text_result_for_llm="", result_type="failure", error=str(ex))

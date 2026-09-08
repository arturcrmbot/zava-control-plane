"""Airline Hero 3 – Preemptive Schedule Resilience constants.

Focused constants for the preemptive-schedule-resilience workflow.
Do not import from process_profiles to avoid coupling with Hero 1 constants.
"""
from __future__ import annotations

SCHED_WORKFLOW_TYPE = "preemptive-schedule-resilience"
SCHED_SENSOR_ID = "sensor:schedule_resilience"
SCHED_SCENARIO_ID = "synthetic-schedule-restriction"
SCHED_STORY_ID = "SYN-STORY-SCHED-001"
SCHED_WORKFLOW_ID = "AIRSCHED-0001"
SCHED_DECISION_ID = "SYN-SCHED-DECISION-001"
SCHED_COMMAND_TYPE = "airline.commit_schedule_adjustment"
SCHED_SUCCESS_EVENT = "airline.schedule_adjustment.applied"
SCHED_SOURCE_EVENT_TYPE = "airline.schedule_risk.detected"
SCHED_HITL_PERSONA = "network_operations_director"
SCHED_ISSUER = "network-planning"

# Stage-1 spend cap — no AuthorityRow lookup yet; real authority registration next stage.
SCHED_MAX_VALUE_GBP = 300_000.0

# Deterministic synthetic entity IDs
SCHED_RISK_SIGNAL_ID = "SYN-RISK-SCHED-001"
SCHED_FCAST_SLOT_ID = "SYN-FCAST-SLOT-001"
SCHED_FCAST_GROUND_ID = "SYN-FCAST-GROUND-001"

# Affected window: 120–240 synthetic minutes (OUT-003 = slot 170, OUT-004 = slot 180)
SCHED_AFFECTED_SECTOR_IDS = ("SYN-SECTOR-OUT-003", "SYN-SECTOR-OUT-004")
SCHED_AFFECTED_ROTATION_IDS = ("SYN-ROTATION-03", "SYN-ROTATION-04")
SCHED_AFFECTED_SLOT_IDS = ("SYN-SLOT-07", "SYN-SLOT-08")
SCHED_AFFECTED_CREW_IDS = ("SYN-CREW-DUTY-05", "SYN-CREW-DUTY-04")
SCHED_AFFECTED_AIRCRAFT_IDS = ("SYN-TAIL-003", "SYN-TAIL-004")

# Pre-day cancellation is permitted for exactly one sector (OUT-004 only)
SCHED_CANCEL_SECTOR_ID = "SYN-SECTOR-OUT-004"
SCHED_CANCEL_ROTATION_ID = "SYN-ROTATION-04"
SCHED_CANCEL_CREW_ID = "SYN-CREW-DUTY-04"
SCHED_FREED_DUTY_MINUTES = 90  # duty freed when OUT-004 is pre-cancelled

# Reserve resources (existing world entities, no new aircraft)
SCHED_RESERVE_AIRCRAFT_ID = "SYN-TAIL-005"
SCHED_RESERVE_CREW_ID = "SYN-DUTY-006"

SCHED_WINDOW_START_MINUTES = 120
SCHED_WINDOW_END_MINUTES = 240
SCHED_BUFFER_MINUTES = 15  # retime buffer for buffer_retime option

# Profile identity constants (used for future manifest/process-profile registration)
SCHED_DISPLAY_NAME = "Preemptive Schedule Resilience"
SCHED_WORKFLOW_ID_PREFIX = "AIRSCHED"
SCHED_OBJECTIVE_TYPE = "manage_schedule_risk"
SCHED_FAILURE_EVENT = "command.rejected"

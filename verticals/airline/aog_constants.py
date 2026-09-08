"""Airline Hero 2 – AOG Engineering Recovery constants.

Focused constants for the aog-engineering-recovery workflow.
Do not import process_profiles to avoid coupling with Hero 1 constants.
"""
from __future__ import annotations

AOG_WORKFLOW_TYPE = "aog-engineering-recovery"
AOG_SENSOR_ID = "sensor:aog_engineering"
AOG_SCENARIO_ID = "synthetic-aog-defect"
AOG_STORY_ID = "SYN-STORY-AOG-001"
AOG_WORKFLOW_ID = "AOGA-0001"
AOG_DECISION_ID = "SYN-AOG-DECISION-001"
AOG_COMMAND_TYPE = "airline.commit_aog_recovery"
AOG_SUCCESS_EVENT = "airline.aog_recovery.applied"
AOG_SOURCE_EVENT_TYPE = "airline.aog.detected"
AOG_HITL_PERSONA = "engineering_duty_manager"
AOG_ISSUER = "engineering-maintenance"

# Stage-1 spend cap – no AuthorityRow lookup yet; next stage adds real matrix.
AOG_MAX_VALUE_GBP = 200_000.0

# Affected entities (deterministic synthetic IDs)
AOG_AFFECTED_TAIL_ID = "SYN-TAIL-003"
AOG_ROTATION_ID = "SYN-ROTATION-03"
AOG_THREATENED_SECTOR_ID = "SYN-SECTOR-OUT-003"
AOG_SUBSTITUTE_TAIL_ID = "SYN-TAIL-005"
AOG_TECH_STATUS_ID = "SYN-TECH-003"
AOG_TASK_ID = "SYN-TASK-001"
AOG_PROVIDER_ID = "SYN-PROV-001"
AOG_SPARE_LOCAL_ID = "SYN-SPARE-LOCAL-001"
AOG_SPARE_REPO_ID = "SYN-SPARE-REPO-001"

# Profile identity constants (used by process_profiles, domains, functions)
AOG_DISPLAY_NAME = "AOG Engineering and Spares Recovery"
AOG_WORKFLOW_ID_PREFIX = "AOGA"
AOG_ORCHESTRATOR = "AirlineAogEngineeringRecoveryOrchestrator"
AOG_OBJECTIVE_TYPE = "recover_aog_engineering"
AOG_FAILURE_EVENT = "command.rejected"
AOG_HITL_EVENT = "engineering_duty_manager_decision"

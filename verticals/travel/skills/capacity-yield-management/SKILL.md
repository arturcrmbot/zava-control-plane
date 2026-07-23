---
name: capacity-yield-management
description: Moves contracted room headroom between hotel allotments to relieve capacity pressure without ever breaching a supplier's contracted total.
allowed-tools:
  - travel_operations_check_allotment_headroom
  - travel_operations_move_allotment_rooms
---

# Capacity Yield Management

Moves contracted room headroom between hotel allotments to relieve capacity pressure without ever breaching a supplier's contracted total.

- **Sensor:** `sensor:capacity_pressure`
- **Objective:** `protect_package_capacity`
- **Command:** `adjust_package_allotment`
- **Evaluation:** `capacity_within_bounds`
- **Authority:** `revenue_manager`
- **Orchestrator:** `CapacityYieldManagementOrchestrator`

## Phases

1. `detect_pressure` (deterministic)
1. `plan_adjustment` (agent)
1. `execute_adjustment` (deterministic)

## Tools

- `travel_operations_check_allotment_headroom`
- `travel_operations_move_allotment_rooms`

---
name: hotel-supplier-recovery
description: Restores accommodation for a shortfall-hit hotel allotment by moving contracted rooms from a donor allotment with headroom, resolving the reported supplier shortfall.
allowed-tools:
  - travel_operations_check_allotment_headroom
  - travel_operations_move_allotment_rooms
---

# Hotel Supplier Recovery

Restores accommodation for a shortfall-hit hotel allotment by moving contracted rooms from a donor allotment with headroom, resolving the reported supplier shortfall.

- **Sensor:** `sensor:hotel_allotment_shortfall`
- **Objective:** `restore_hotel_accommodation`
- **Command:** `move_hotel_allotment`
- **Evaluation:** `accommodation_restored`
- **Authority:** `accommodation_manager`
- **Orchestrator:** `HotelSupplierRecoveryOrchestrator`

## Phases

1. `detect_shortfall` (deterministic)
1. `assess_recovery` (agent)
1. `plan_move` (agent)
1. `execute_move` (deterministic)

## Tools

- `travel_operations_check_allotment_headroom`
- `travel_operations_move_allotment_rooms`

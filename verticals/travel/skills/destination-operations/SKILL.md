---
name: destination-operations
description: Dispatches a replacement resort transfer when an arrival is at risk, rebinding any travellers on the at-risk transfer to the replacement.
allowed-tools:
  - travel_operations_check_transfer_risk
  - travel_operations_dispatch_replacement_transfer
---

# Destination Operations

Dispatches a replacement resort transfer when an arrival is at risk, rebinding any travellers on the at-risk transfer to the replacement.

- **Sensor:** `sensor:transfer_arrival_risk`
- **Objective:** `restore_destination_journey`
- **Command:** `dispatch_replacement_transfer`
- **Evaluation:** `transfer_sla_restored`
- **Authority:** `destination_operations_manager`
- **Orchestrator:** `DestinationOperationsOrchestrator`

## Phases

1. `detect_risk` (deterministic)
1. `plan_replacement` (agent)
1. `dispatch` (deterministic)

## Tools

- `travel_operations_check_transfer_risk`
- `travel_operations_dispatch_replacement_transfer`

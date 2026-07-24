---
name: flight-disruption-recovery
description: Recovers travellers stranded by a cancelled flight: moves the affected booking's flight and transfer to a validated alternative, escalating material or high-cost cases to Head of Operations.
allowed-tools:
  - travel_operations_check_flight_disruption
  - travel_operations_reaccommodate_booking
---

# Flight Disruption Recovery

Recovers travellers stranded by a cancelled flight: moves the affected booking's flight and transfer to a validated alternative, escalating material or high-cost cases to Head of Operations.

- **Sensor:** `sensor:flight_cancellation_impact`
- **Objective:** `recover_cancelled_flight`
- **Command:** `reaccommodate_travellers`
- **Evaluation:** `travellers_reaccommodated`
- **Authority:** `operations_controller`
- **Orchestrator:** `FlightDisruptionRecoveryOrchestrator`

## Phases

1. `detect_cancellation` (deterministic)
1. `assess_impact` (agent)
1. `escalate` (hitl)
1. `reaccommodate` (deterministic)

## Tools

- `travel_operations_check_flight_disruption`
- `travel_operations_reaccommodate_booking`

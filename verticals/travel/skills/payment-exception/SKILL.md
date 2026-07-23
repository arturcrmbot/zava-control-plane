---
name: payment-exception
description: Resolves a failed balance payment by retrying it to complete the booking, or releasing the booking's inventory when retry is not viable.
allowed-tools:
  - travel_operations_check_booking_status
  - travel_operations_release_booking_capacity
---

# Payment Exception

Resolves a failed balance payment by retrying it to complete the booking, or releasing the booking's inventory when retry is not viable.

- **Sensor:** `sensor:balance_payment_exception`
- **Objective:** `preserve_payment_booking`
- **Command:** `resolve_payment_exception`
- **Evaluation:** `payment_or_inventory_resolved`
- **Authority:** `payments_specialist`
- **Orchestrator:** `PaymentExceptionOrchestrator`

## Phases

1. `detect_exception` (deterministic)
1. `assess_resolution` (agent)
1. `resolve` (deterministic)

## Tools

- `travel_operations_check_booking_status`
- `travel_operations_release_booking_capacity`

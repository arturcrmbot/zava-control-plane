---
name: cancellation-refund
description: Settles an accepted customer cancellation: releases the booking's flight, hotel and transfer capacity and issues the bounded refund.
allowed-tools:
  - travel_operations_check_booking_status
  - travel_operations_release_booking_capacity
---

# Cancellation Refund

Settles an accepted customer cancellation: releases the booking's flight, hotel and transfer capacity and issues the bounded refund.

- **Sensor:** `sensor:customer_cancellation_accepted`
- **Objective:** `settle_cancelled_booking`
- **Command:** `cancel_and_refund_booking`
- **Evaluation:** `refund_settled`
- **Authority:** `finance_operations_lead`
- **Orchestrator:** `CancellationRefundOrchestrator`

## Phases

1. `detect_cancellation` (deterministic)
1. `assess_refund` (agent)
1. `settle` (deterministic)

## Tools

- `travel_operations_check_booking_status`
- `travel_operations_release_booking_capacity`

---
name: proactive-customer-care
description: Proactively notifies and, where warranted, extends a small bounded goodwill gesture to a customer whose itinerary materially changed.
allowed-tools:
  - travel_operations_check_booking_status
  - travel_operations_issue_care_action
---

# Proactive Customer Care

Proactively notifies and, where warranted, extends a small bounded goodwill gesture to a customer whose itinerary materially changed.

- **Sensor:** `sensor:material_itinerary_change`
- **Objective:** `protect_disrupted_customer`
- **Command:** `issue_customer_care_action`
- **Evaluation:** `customer_notified_and_supported`
- **Authority:** `customer_care_lead`
- **Orchestrator:** `ProactiveCustomerCareOrchestrator`

## Phases

1. `detect_change` (deterministic)
1. `assess_care` (agent)
1. `issue_action` (deterministic)

## Tools

- `travel_operations_check_booking_status`
- `travel_operations_issue_care_action`

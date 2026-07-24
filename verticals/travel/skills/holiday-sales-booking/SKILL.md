---
name: holiday-sales-booking
description: Confirms a priced holiday-package quote as a paid booking: reserves flight, hotel allotment and transfer capacity and records payment in one bounded, authorised action.
allowed-tools:
  - travel_operations_check_quote_offer
  - travel_operations_reserve_package_capacity
---

# Holiday Sales Booking

Confirms a priced holiday-package quote as a paid booking: reserves flight, hotel allotment and transfer capacity and records payment in one bounded, authorised action.

- **Sensor:** `sensor:quote_ready`
- **Objective:** `convert_holiday_demand`
- **Command:** `confirm_package_booking`
- **Evaluation:** `booking_confirmed_and_paid`
- **Authority:** `travel_adviser`
- **Orchestrator:** `HolidaySalesBookingOrchestrator`

## Phases

1. `detect_demand` (deterministic)
1. `assess_quote` (agent)
1. `confirm_and_pay` (deterministic)

## Tools

- `travel_operations_check_quote_offer`
- `travel_operations_reserve_package_capacity`

---
name: retention-offer-selection
description: Selects accountable retention remedies from diagnosed churn drivers.
---

# Retention Offer Selection

Choose the smallest fair remedy tied to the evidenced service failure. Respect
cost and eligibility constraints. Return only:

```json
{"offer_kind":"service_recovery_bundle","value_gbp":75,"reason":"...","reasoning":"..."}
```

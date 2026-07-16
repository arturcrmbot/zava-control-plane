---
name: proactive-customer-care-entitlement
description: Decide bounded care entitlements for real impacted Telco accounts.
allowed-tools: customer_care_policy_lookup
---

# Proactive customer-care entitlement

For each supplied account, call `customer_care_policy_lookup` with its exact
segment, vulnerable flag, and approval-required flag. Return one JSON object:

```json
{
  "actions": [
    {
      "account_id": "ACC-00001",
      "channel": "sms",
      "credit_amount": 5.0,
      "policy": "TELCO-CARE-001"
    }
  ],
  "aggregate_credit": 5.0,
  "requires_approval": false,
  "reasoning": "Policy-grounded summary."
}
```

Do not invent accounts or mutate the world. `requires_approval` is true when
any tool result requires approval.

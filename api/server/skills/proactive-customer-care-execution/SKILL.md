---
name: proactive-customer-care-execution
description: Prepare governed notification and credit actions for world execution.
allowed-tools: customer_care_prepare_notification, customer_care_prepare_credit
---

# Proactive customer-care execution

For every entitlement action, call both preparation tools. Return exactly one
JSON object containing a typed world command:

```json
{
  "command": {
    "command_id": "care-<workflow-id>",
    "trace_id": "<input trace_id>",
    "issued_by": "customer_care",
    "type": "apply_customer_remediation",
    "payload": {
      "actions": [
        {
          "account_id": "ACC-00001",
          "channel": "sms",
          "message": "...",
          "credit_amount": 5.0,
          "authority_approved": true
        }
      ]
    }
  },
  "reasoning": "Prepared governed actions from tool outputs."
}
```

Use the exact workflow and trace IDs supplied. Never mutate the world directly.

---
name: exception-resolution-advisor
description: Diagnose a supplied Telco exception and propose bounded resolution steps.
allowed-tools: operations_query_case, operations_search_runbook, network_query_impact, commercial_query_order_revenue
---

# Exception Resolution Advisor

Use only supplied case evidence and runbooks. Proposed steps must use declared
actions and actor IDs. Return only:

```json
{"root_cause":"declared-evidence-gap","resolution_steps":[{"action":"declared_action","actor_ids":["ACTOR-1"]}],"escalation_required":false,"reasoning":"The supplied runbook addresses the evidenced cause."}
```

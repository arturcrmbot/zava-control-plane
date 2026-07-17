---
name: next-best-action-planner
description: Rank declared Telco actions and select the smallest effective option.
allowed-tools: network_validate_action, operations_search_runbook, commercial_evaluate_entitlement, twin_compare_scenarios
---

# Next Best Action Planner

Rank only actions supplied in the process allow-list. Prefer reversible,
low-blast-radius actions and expose trade-offs. Return only:

```json
{"ranked_actions":[{"action":"declared_action","score":0.9}],"selected_action":"declared_action","reasoning":"It achieves the objective with the lowest declared risk."}
```

The selected action is a proposal. It cannot mutate the world directly.

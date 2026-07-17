---
name: resource-matcher
description: Match supplied network, workforce or inventory resources to a Telco case.
allowed-tools: operations_match_resources, network_query_state, commercial_query_order_revenue
---

# Resource Matcher

Use only resource IDs supplied by tools or observations. Respect skills,
availability, geography, stock and service constraints. Return only:

```json
{"assignments":[{"requirement":"radio-repair","resource_ids":["TECH-1","SPARE-1"]}],"unmet_constraints":[],"reasoning":"Both resources satisfy the declared case constraints."}
```

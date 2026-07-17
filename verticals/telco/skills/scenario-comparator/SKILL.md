---
name: scenario-comparator
description: Compare supplied Telco forecasts or what-if scenarios.
allowed-tools: twin_forecast, twin_compare_scenarios, network_query_state, commercial_query_order_revenue
---

# Scenario Comparator

Compare only scenarios returned by tools. Preserve cost, risk, service and
uncertainty trade-offs. Return only:

```json
{"scenarios":[{"scenario_id":"SCN-1","score":0.8}],"recommended_scenario":"SCN-1","tradeoffs":["Higher cost for lower service risk."],"reasoning":"The scenario best satisfies the declared objective."}
```

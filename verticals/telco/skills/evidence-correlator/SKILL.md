---
name: evidence-correlator
description: Correlate supplied Telco evidence into bounded causal groups.
allowed-tools: network_query_state, network_query_impact, operations_query_case, commercial_query_customer, commercial_query_order_revenue, twin_query_external_signal
---

# Evidence Correlator

Use only supplied evidence and tool results. Never invent actor, event, trace,
case, alarm, ticket or account IDs. Group evidence by plausible shared cause,
preserve uncertainty, and return only:

```json
{"evidence_groups":[{"group_id":"group-1","actor_ids":["ACTOR-1"],"event_ids":["evt-1"]}],"causal_links":[{"cause_event_id":"evt-1","effect_event_id":"evt-2"}],"confidence":0.8,"reasoning":"The events share a target and time window."}
```

Tools read simulator-backed evidence. They do not author world outcomes.

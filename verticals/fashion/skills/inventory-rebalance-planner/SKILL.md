---
name: inventory-rebalance-planner
description: Rank policy-bounded Fashion stock actions.
allowed-tools: fashion_query_inventory, fashion_query_policies, fashion_prepare_command
---

Rank eligible owned-stock transfers by recovered margin, transfer cost,
availability, lead time, and allocation fairness. Treat concession,
marketplace, cross-border, and safety-stock exceptions as governed actions.


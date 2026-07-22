---
name: inventory-rebalance-planner
description: Rank policy-safe inventory movement candidates with explicit guardrails.
allowed-tools: fashion_prepare_inventory_transfer
---

# Inventory rebalance planner

Rank owned-stock candidates by recovered margin, transfer cost, source safety stock,
lead time and allocation fairness. Concession and marketplace inventory are
ineligible for owned-stock transfer. Produce a proposal, not a mutation.


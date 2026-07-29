---
name: inventory-rebalance-planner
description: Rank policy-safe inventory movement candidates with explicit guardrails.
allowed-tools: electronics_prepare_inventory_transfer
---

# Inventory rebalance planner

Rank owned-stock candidates by recovered margin, transfer cost, source safety stock,
lead time and allocation fairness. Marketplace-seller-owned inventory is
ineligible for owned-stock transfer. Produce a proposal, not a mutation.


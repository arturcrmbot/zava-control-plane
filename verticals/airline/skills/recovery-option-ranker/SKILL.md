---
name: recovery-option-ranker
description: Rank deterministically admitted synthetic hub recovery options.
allowed-tools: airline_rank_feasible_recovery_options
---

# Recovery option ranker

Use only `airline_rank_feasible_recovery_options`. Return a ranked list
containing only admitted option IDs, with trade-offs, uncertainty, and an
explicit no-action comparison.

The ranker cannot introduce options, cannot declare infeasible options feasible,
cannot mutate state, and cannot claim live data. Treat the tool's
`source_mode` as `simulated`; deterministic validators, not this agent, own
feasibility.

---
name: author-ambient-trigger
description: |
  v4 sub-skill #5 (optional). Adds the `ambient:` block — declares
  an AmbientAgent that watches the bus / graph / clock and spawns
  workflows of the listed types. Skipped when the operator answers
  "no" to "does this domain need an ambient hook?".
audience: design-time-only
forbidden-runtime: true
inputs:
  - brief.function (so codegen knows which file to append to)
outputs:
  - brief.ambient (optional)
  - <sandbox>/api/server/services/ambient_agents/<function>.py (append-or-create)
hands_off_to: existing v3 generators
---

# author-ambient-trigger

Most domains need no ambient hook (the workflow is operator-driven
end-to-end). When one is needed, declare it as a single block:

```yaml
ambient:
  name: <PascalCase>                     # e.g. VendorRiskWatcher
  function: <one of the 10 keys>         # which file to land in
  reasoning_skill: <kebab>               # optional GHCP skill, null = deterministic
  spawnable_workflow_types: [<wt>, ...]  # workflows this watcher may spawn
  triggers:                              # ≥ 1 of: bus | cypher | cadence
    - kind: bus
      event_type: <FleetEvent type>
      filter:     <Cypher-like predicate>
    - kind: cypher
      pattern:        "(node:Type {prop:value})"
      sweep_seconds:  3600
    - kind: cadence
      cron: "0 0 * * *"
```

## Procedure

1. Ask the operator: "does this domain need an ambient hook?".
2. If no → write nothing, return cleanly. Pipeline continues.
3. If yes → propose the `ambient:` block and write it to the brief.
4. Run `validator.py:validate(brief)`. STOP on `SchemaError`.
5. Render with `codegen.render_ambient(brief)` → `(file_path, append_block)`.
   File path is `api/server/services/ambient_agents/<function>.py`.
6. The codegen wraps the constructor in a sentinel block
   `# compose-domain:ambient:<workflow_type>` so `graduate.sh`
   appends idempotently.
7. The constructor is guarded by `if hasattr(_module, "AmbientAgent")`
   so the file is import-clean before Phase 3 lands the
   `AmbientAgent` primitive.

## Constraints

- `ambient.function` must equal `brief.function` (same registry
  ownership). Validator enforces.
- Every entry in `spawnable_workflow_types` must be present in the
  live `api.shared.domains.DOMAINS` registry OR be the brief's own
  `domain.workflow_type` (forward-declaration of self-spawning).
- Triggers form a discriminated union: each entry sets exactly one
  of `bus | cypher | cadence` and supplies the kind-specific keys.

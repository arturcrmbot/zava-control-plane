---
name: author-entity-projection
description: |
  v4 sub-skill #2. Adds the `entities:` block to the brief and emits
  a per-domain projection function at
  `api/server/services/entity_projections/<workflow_type_snake>.py`.
  Validates entity kinds + relations against the Phase 1
  `_NODE_TABLES` / `_REL_TABLES` schema in
  `api/server/services/entity_graph.py`.
audience: design-time-only
forbidden-runtime: true
inputs:
  - brief.domain (from author-domain-skeleton)
  - brief.phases
  - the live orchestrator file at
    `api/functions/workflows/<prefix>_<workflow_type_snake>.py`
    (so ref_field paths can be AST-walked against the emitted payload)
outputs:
  - brief.entities
  - <sandbox>/api/server/services/entity_projections/<wt_snake>.py
hands_off_to: author-decision-mapping
---

# author-entity-projection

This sub-skill is responsible for one thing: declaring **which graph
entities and relationships this workflow projects**, then emitting a
single Python projection module that Phase 1's
`api.server.services.entity_projections.PROJECTIONS` registry binds.

## Procedure

1. **Read the orchestrator** at
   `api/functions/workflows/<prefix>_<workflow_type_snake>.py`. Walk
   its AST to enumerate every dotted path the orchestrator stamps on
   the `payload` it emits. Use that as the universe of permissible
   `ref_field` and `attribute` paths.

2. **Propose the `entities:` block.** Each entity declares:
   - `kind` — must be one of the seven Phase 1 node tables
     (`Person`, `Organisation`, `Asset`, `Money`, `Decision`, `Place`,
     `Period`). `Workflow` is reflector-managed; do not project it.
   - `ref_field` — dotted path inside `payload` (e.g.
     `payload.vendor.id`) holding the entity id.
   - `source` (optional) — sub-kind label landing on the node's
     `kind` attr (e.g. `vendor`, `agency`, `joiner`, `campaign`).
   - `attributes` (optional) — map of Kuzu column → dotted payload
     ref.
   - `relations` (optional) — list of `{kind, target_ref}` entries
     where `kind` is one of `_REL_TABLES` and `target_ref` is another
     entity's `ref_field`.

3. **Validate.** Run `validator.py:validate(brief, orchestrator_path)`.
   On `SchemaError` (unknown kind / unresolved ref / bad rel), STOP
   and print the structured failure.

4. **Render the projection.** Call
   `codegen.render_projection(brief)`. Write `(filename, body)` into
   the sandbox at
   `tools/scratch/compose-domain/<run-id>/api/server/services/entity_projections/<filename>`.

5. **Hand off** to `author-decision-mapping`.

## Output shape (one Python module per domain)

The codegen emits a module that mirrors the twelve hand-written Phase 1
projection modules:

```python
"""Projection: <workflow-type> (compose-domain v4 codegen)."""
from __future__ import annotations

import json

from api.server.services.entity_projections import (
    DecisionWrite, EntityWrite, RelWrite, build_decision, slug,
)
from api.shared.types import Workflow

WORKFLOW_TYPE = "<workflow-type>"


def project(workflow: Workflow) -> list[EntityWrite | RelWrite | DecisionWrite]:
    p = workflow.payload or {}
    sw = (workflow.id,)
    ops: list[EntityWrite | RelWrite | DecisionWrite] = []

    # --- Entity 0 ---
    <kind>_id = f"<PREFIX>-<source>-{slug(str(<ref_field>))}"
    ops.append(EntityWrite(
        kind="<Kind>", id=<kind>_id,
        attrs={"kind": "<source>", ...},
        source_workflows=sw,
    ))
    # ...
    return ops
```

`build_decision(...)` is appended downstream by
`author-decision-mapping` — this codegen produces only `EntityWrite`
+ `RelWrite`.

## Constraints

- The function MUST be named `project` (Phase 1 PAT-005). The module
  MUST expose `WORKFLOW_TYPE = "<workflow-type>"` so the registry can
  bind it.
- Imports MUST be limited to the allow-list above; the validator
  enforces this on the rendered output.
- ID prefix convention (matches Phase 1):
  `Person → PERSON-`, `Organisation → ORG-`, `Asset → ASSET-`,
  `Money → MONEY-`, `Decision → DEC-`, `Place → PLACE-`,
  `Period → PERIOD-`.

## Failure handling

Validation failure aborts the pipeline. Re-author the brief.

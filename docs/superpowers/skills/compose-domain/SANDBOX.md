# compose-domain v4 — sandbox layout

Every wholesale `compose-domain` invocation lands under
`tools/scratch/compose-domain/<run-id>/`. The folder mirrors the live
`api/` tree so `graduate.sh` can `cp -r` into place. v4 adds two new
sibling subtrees for the artefacts the v4 codegens emit, plus a
`brief/` subfolder snapshotting each enrichment pass.

## Layout

```
tools/scratch/compose-domain/<RUN_ID>/
├── REPORT.md                      # self-check verdicts (CHECKLIST.md run)
├── GRADUATION.md                  # human-readable graduate.sh reference
├── graduate.sh                    # mechanical apply script (chmod +x)
│
├── brief/                         # NEW v4: per-pass brief snapshots
│   ├── v0-skeleton.yaml           # author-domain-skeleton output
│   ├── v1-entity-projection.yaml  # + entities block
│   ├── v2-decision-mapping.yaml   # + decisions block
│   ├── v3-function-membership.yaml# + function field
│   ├── v4-ambient-trigger.yaml    # + ambient block (optional)
│   └── v5-sealed.yaml             # final brief, ready for graduation
│
├── api/                           # mirrors live tree
│   ├── functions/
│   │   ├── workflows/<prefix>_<workflow_type_snake>.py
│   │   ├── workflows/<prefix>_<workflow_type_snake>_activities.py
│   │   └── graphs/<prefix>_<workflow_type_snake>_<phase>.py
│   ├── server/
│   │   ├── skills/<workflow_type>-<phase>/SKILL.md
│   │   ├── personae/<role>/SKILL.md
│   │   ├── mcp_tools/<tool>.py
│   │   └── services/
│   │       ├── entity_projections/<workflow_type_snake>.py    # NEW v4
│   │       ├── precedent_queries/<workflow_type>_<phase>.cypher # NEW v4
│   │       └── ambient_agents/<function>.py                   # NEW v4 (optional)
│   └── shared/
│       └── functions.py.patch       # NEW v4 (FUNCTIONS["<fn>"].owns_domains append)
```

`RUN_ID = <YYYYMMDD-HHMMSS>-<domain.workflow_type>`. Re-projection-only
runs use `<RUN_ID>-reproj/` and only write the four NEW v4 subtrees
(`brief/`, `entity_projections/`, `precedent_queries/`,
`ambient_agents/` + the FUNCTIONS patch). The orchestrator/graphs/
personae/MCP layers are untouched.

## Phase 7 backfill convention

Phase 7 will iterate the twelve canonical synthetic-journey domains:

```bash
for d in fleet-ap-invoice fleet-contract-renewal fleet-contract-review \
         fleet-employee-onboarding fleet-it-access-request fleet-perf-review \
         fleet-privacy-dpia fleet-purchase-order fleet-travel-preapproval \
         fleet-treasury-fx fleet-vendor-kyc creative-campaign; do
  python -m docs.superpowers.skills.compose_domain \
      --brief docs/superpowers/specs/${d}-brief.yaml \
      --re-projection-only
done
```

Each iteration writes into a fresh `<RUN_ID>-reproj/` and the operator
applies the patches by running `graduate.sh` from each sandbox. The
orchestrators under `api/functions/workflows/` MUST stay byte-equal
pre/post.

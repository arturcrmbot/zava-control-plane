# Per-`(workflow_type, phase)` precedent Cypher templates.
#
# Phase 4 IP3 (TASK-017). Each file is a read-only Cypher query of the
# shape `<workflow_type>_<phase>.cypher` consumed by the
# `query_precedents` MCP tool. Files are populated per-domain by
# compose-domain v4's HITL-phase codegen at graduation; this directory
# is intentionally empty until then.
#
# Read-only constraint: any file containing `CREATE`, `MERGE`, `DELETE`,
# `SET`, `REMOVE`, or `DROP` is rejected at load time by the tool.
#
# Phase 4 IP9 (TASK-042) — historical note: prior to Phase 1 the
# substrate seeded persona reasoning from `data/synthetic/precedents.json`
# (a static JSON catalogue). That file is left in place for blueprint
# replay scripts but is NOT imported by any production code path. The
# canonical precedent source from Phase 4 onwards is the entity graph's
# `Decision` nodes traversed via the templates in this directory.

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

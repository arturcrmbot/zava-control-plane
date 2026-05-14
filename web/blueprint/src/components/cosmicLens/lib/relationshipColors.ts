/**
 * Per-relationship colour palette. Mirrors the Kuzu rel-table catalogue
 * declared in api/server/services/entity_graph.py (_REL_TABLES). Grouped by
 * intent so callers and reviewers can scan the rationale quickly.
 *
 * Picking colour keeps the cosmic palette coherent:
 *   • Authority / hierarchy  → cool blues
 *   • Money / value flow     → green / gold
 *   • Decision verdicts      → violet (matches Decision node colour)
 *   • Marketing / brand      → warm orange / teal
 *   • Touch / passive        → soft white (low-presence, fades into noise)
 */
export const REL_COLORS: Record<string, string> = {
  // Authority / hierarchy
  EMPLOYED_BY: "#22d3ee",
  MANAGES: "#60a5fa",
  LOCATED_IN: "#94a3b8",
  BELONGS_TO: "#7dd3fc",

  // Ownership / value
  OWNS: "#fbbf24",
  TRANSACTS: "#22c55e",

  // Decision authority — matches the violet of the Decision node colour
  DECIDED_ON: "#a78bfa",
  DECIDED_PERSON: "#a78bfa",
  DECIDED_MONEY: "#a78bfa",
  DECIDED_ASSET: "#a78bfa",
  DECIDED_ORG: "#a78bfa",
  DECIDED_PERIOD: "#a78bfa",
  DECIDED_PLACE: "#a78bfa",
  PRECEDENT_OF: "#f472b6",

  // Workflow process
  TOUCHED: "#cbd5e1",
  SUB_WORKFLOW_OF: "#818cf8",

  // Agency / brand graph
  BRAND_OF: "#fb923c",
  CAMPAIGN_FOR: "#fb923c",
  EXECUTED_BY: "#14b8a6",
  SUPPLIED_BY: "#22c55e",
};

export function colorForRelationship(rel: string | undefined): string {
  if (!rel) return "#475569";
  return REL_COLORS[rel] ?? "#475569";
}

/**
 * Function key → cadence keys (TASK-038).
 *
 * The cadence YAMLs in `data/governance/cadences/` declare three
 * cadences (morning-sweep, period-close, quarterly-okr). The mapping
 * of cadence → owning function is implicit:
 *
 *   - period-close + quarterly-okr fire ambient agents that live on
 *     the Finance floor (see `FUNCTIONS["finance"].ambient_agents`).
 *   - morning-sweep fires the morning-sweep ambient agent on the HR
 *     floor (see `FUNCTIONS["hr"].ambient_agents`).
 *
 * Source-of-truth: api/shared/functions.py FUNCTIONS[*].ambient_agents.
 * Hard-coded here so the frontend doesn't need a second round-trip to
 * derive it; documented in commit body.
 */

export type CadenceKey = "morning-sweep" | "period-close" | "quarterly-okr";

export const CADENCES_BY_FUNCTION: Record<string, CadenceKey[]> = {
  finance: ["period-close", "quarterly-okr"],
  hr: ["morning-sweep"],
  // CEO floor is the implicit owner of period-close + quarterly-okr at
  // the org level (board-prep + fy-close domains both touch them).
  ceo: ["period-close", "quarterly-okr"],
};

export function cadencesFor(fn: string): CadenceKey[] {
  return CADENCES_BY_FUNCTION[fn] ?? [];
}

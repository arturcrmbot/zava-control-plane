/**
 * Tower-wide registry: world positions of desks indexed by (function, role).
 *
 * Mutable singleton — Floor components register their desk positions on
 * mount; WorkflowMotes and DecisionPool look up positions when they need
 * to animate motes/tags between the lobby and a specific desk.
 *
 * Not a React state value (would cause render thrash); ref-style global
 * registry consulted from useFrame loops.
 */
type Vec3 = [number, number, number];

const desks: Map<string, Vec3> = new Map();
const fallbackByFunction: Map<string, Vec3> = new Map();

/** Stable key for desk lookup. */
function key(fn: string, role: string): string {
  return `${fn}::${role}`;
}

/** Stable djb2 hash for distributing workflows across desks. */
function djb2(s: string): number {
  let h = 5381;
  for (let i = 0; i < s.length; i++) h = ((h << 5) + h + s.charCodeAt(i)) | 0;
  return h >>> 0;
}

const desksByFunction: Map<string, Vec3[]> = new Map();

export function registerDeskPositions(fn: string, role: string, position: Vec3): void {
  desks.set(key(fn, role), position);
  if (!fallbackByFunction.has(fn)) {
    fallbackByFunction.set(fn, position);
  }
  // Build per-function ordered desk list (used to distribute workflow
  // motes across desks deterministically by workflow_id hash).
  const list = desksByFunction.get(fn) ?? [];
  if (!list.some((p) => p[0] === position[0] && p[1] === position[1] && p[2] === position[2])) {
    list.push(position);
    desksByFunction.set(fn, list);
  }
}

/** Pick a deterministic desk position for a workflow_id within a function.
 *  Used when we don't know which persona owns the gate — spreads motes
 *  across the floor's desks so they don't pile on one spot. */
export function deskPositionForWorkflow(fn: string, workflowId: string): Vec3 | null {
  const list = desksByFunction.get(fn);
  if (!list || list.length === 0) return fallbackByFunction.get(fn) ?? null;
  const idx = djb2(workflowId) % list.length;
  return list[idx];
}

export function deskPosition(fn: string, role: string | null | undefined): Vec3 | null {
  if (role) {
    const k = key(fn, role);
    if (desks.has(k)) return desks.get(k)!;
  }
  if (fallbackByFunction.has(fn)) return fallbackByFunction.get(fn)!;
  return null;
}

export function lobbyEntryPosition(): Vec3 {
  // Right side of the lobby — workflows enter here.
  return [2.0, 0.4, 1.4];
}

export function lobbyDecisionPoolPosition(): Vec3 {
  // Center-front of the lobby — receipts pile here.
  return [0, 0.0, 1.6];
}

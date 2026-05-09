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

export function registerDeskPositions(fn: string, role: string, position: Vec3): void {
  desks.set(key(fn, role), position);
  // First registered desk per function becomes the function's fallback
  // (used when a workflow's persona role doesn't match any known desk).
  if (!fallbackByFunction.has(fn)) {
    fallbackByFunction.set(fn, position);
  }
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

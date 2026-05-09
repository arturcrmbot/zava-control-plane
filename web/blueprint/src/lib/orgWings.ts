/**
 * The Org Building (IP6, TASK-031) — wing groupings.
 *
 * A "wing" is a group of related-function floors framed together at
 * zoom-level-2. Mirrors the ``FUNCTIONS`` registry: every function key
 * declared in `floorLayout.FLOOR_ORDER_TOP_DOWN` belongs to exactly one
 * wing.
 *
 * Pure data — safe to import from tests and from non-R3F modules.
 */

export type WingKey = "Money" | "People" | "Operations" | "Front-office" | "C-suite";

export const WINGS: Record<WingKey, string[]> = {
  Money: ["finance", "revenue"],
  People: ["hr"],
  Operations: ["ops", "tech", "data"],
  "Front-office": ["marketing", "legal", "customer-success"],
  "C-suite": ["ceo"],
};

/** Reverse lookup: floor (function key) → wing name. Built once. */
export const FLOOR_TO_WING: Record<string, WingKey> = (() => {
  const out: Record<string, WingKey> = {};
  for (const wing of Object.keys(WINGS) as WingKey[]) {
    for (const fn of WINGS[wing]) {
      out[fn] = wing;
    }
  }
  return out;
})();

/** All wing keys, in canonical render order (top-down: C-suite first). */
export const WING_ORDER: WingKey[] = [
  "C-suite",
  "Money",
  "People",
  "Operations",
  "Front-office",
];

/** Resolve the wing for a floor. Returns null when the floor key is
 *  unknown — keeps callers from blowing up on stale inputs. */
export function wingForFloor(fn: string): WingKey | null {
  return FLOOR_TO_WING[fn] ?? null;
}

/**
 * The Org Building (IP4) — shared layout primitives.
 *
 * Mirrors the constants in components/orgBuilding/Building.tsx so the
 * animation overlay can address per-floor / per-window / per-lobby-icon
 * positions without re-walking the scene graph each frame.
 *
 * Pure data, no R3F / three imports — safe to import from tests.
 */

export const FLOOR_HEIGHT = 1.0;
export const FLOOR_WIDTH = 3.2;
export const FLOOR_DEPTH = 2.0;
export const PENTHOUSE_WIDTH = 2.2;
export const LOBBY_WIDTH = 4.2;
export const WINDOWS_PER_FLOOR = 6;

// Top-down floor order — must match Building.tsx FLOOR_ORDER_TOP_DOWN.
export const FLOOR_ORDER_TOP_DOWN: string[] = [
  "ceo",
  "finance",
  "revenue",
  "hr",
  "ops",
  "legal",
  "marketing",
  "tech",
  "data",
  "customer-success",
];

// Lobby kind palette (must match Building.tsx KIND_PALETTE order).
export const KIND_ORDER: string[] = [
  "Person",
  "Organisation",
  "Asset",
  "Money",
  "Decision",
  "Place",
  "Period",
];

export type Vec3 = [number, number, number];

/** Y position of a function floor. Lobby anchored at y=0; floor stack
 *  starts at y=FLOOR_HEIGHT and increments by FLOOR_HEIGHT per floor.
 *  Returns null when the function name is unknown. */
export function floorY(fnName: string): number | null {
  const reversed = [...FLOOR_ORDER_TOP_DOWN].reverse();
  const i = reversed.indexOf(fnName);
  if (i < 0) return null;
  return FLOOR_HEIGHT * (i + 1);
}

/** Front-facade window position for a given workflow_id within a floor.
 *  Hashed deterministically into one of WINDOWS_PER_FLOOR slots so the
 *  same workflow always lights the same window. Falls back to the
 *  centre slot when workflow_id is null/empty. */
export function windowPosition(
  fnName: string,
  workflowId: string | null | undefined,
  isPenthouse = false,
): Vec3 | null {
  const y = floorY(fnName);
  if (y == null) return null;
  const width = isPenthouse ? PENTHOUSE_WIDTH : FLOOR_WIDTH;
  const span = width * 0.72;
  const slot = workflowId ? hashSlot(workflowId, WINDOWS_PER_FLOOR) : Math.floor(WINDOWS_PER_FLOOR / 2);
  const t = slot / Math.max(1, WINDOWS_PER_FLOOR - 1);
  const x = -span / 2 + t * span;
  const yOffset = FLOOR_HEIGHT * 0.05;
  const z = FLOOR_DEPTH / 2 + 0.025;
  return [x, y + yOffset, z];
}

/** Centre of a floor's front facade — handy for floor-level pulses
 *  (cadence flash, ambient wave) when no specific workflow is involved. */
export function floorFrontCentre(fnName: string): Vec3 | null {
  const y = floorY(fnName);
  if (y == null) return null;
  return [0, y, FLOOR_DEPTH / 2 + 0.05];
}

/** Lobby kind-icon world position (matches the Lobby() group in
 *  Building.tsx). Returns null when the kind is unknown. */
export function lobbyKindPosition(kind: string): Vec3 | null {
  const i = KIND_ORDER.indexOf(kind);
  if (i < 0) return null;
  const span = LOBBY_WIDTH * 0.86;
  const t = i / (KIND_ORDER.length - 1);
  const x = -span / 2 + t * span;
  const y = -FLOOR_HEIGHT * 0.06;
  const z = (FLOOR_DEPTH / 2) * 1.08 + 0.06;
  return [x, y, z];
}

/** Sensor-icon position on a floor's facade for a given ambient agent.
 *  Stacked along the right edge of the floor (one icon per ambient
 *  agent declared on that floor). */
export function ambientSensorPosition(
  fnName: string,
  agentIndex: number,
  totalAgents: number,
): Vec3 | null {
  const y = floorY(fnName);
  if (y == null) return null;
  const width = fnName === "ceo" ? PENTHOUSE_WIDTH : FLOOR_WIDTH;
  const xRight = width / 2 - 0.18;
  const ySpan = FLOOR_HEIGHT * 0.55;
  const yT = totalAgents <= 1 ? 0.5 : agentIndex / (totalAgents - 1);
  const yLocal = -ySpan / 2 + yT * ySpan;
  const z = FLOOR_DEPTH / 2 + 0.04;
  return [xRight, y + yLocal * 0.6, z];
}

/** Tiny djb2-style hash → integer in [0, modulo). */
function hashSlot(s: string, modulo: number): number {
  let h = 5381;
  for (let i = 0; i < s.length; i += 1) {
    h = ((h << 5) + h + s.charCodeAt(i)) | 0;
  }
  return Math.abs(h) % modulo;
}

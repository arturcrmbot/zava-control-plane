/**
 * The Org Building (IP4, TASK-018) — animation queue reducer.
 *
 * The SSE stream from `useObservatory` fires raw events; the building
 * needs short-lived visual entries it can drive in a useFrame() loop.
 * This reducer owns that translation.
 *
 * Each entry advances `t` from 0..1 and is evicted when t >= 1. The
 * reducer caps entry counts per kind so a burst of 1k events doesn't
 * blow the GPU pool.
 */
import type { Vec3 } from "./floorLayout";

export type AnimKind =
  | "spark" // bright point at a window (decision/spawn)
  | "beam" // straight line A→B (cross-function entity reuse, persistent)
  | "pulse" // soft brightness ramp (workflow.completed window pulse, ambient sensor flash, cadence)
  | "filament" // thin curved line A→B that fades (workflow.sub_spawned)
  | "mote"; // small drifting point (entity.upserted floor → lobby vault)

export interface AnimEntry {
  id: string;
  kind: AnimKind;
  /** Source position. */
  from: Vec3;
  /** Destination position (omitted for pulses anchored at `from`). */
  to?: Vec3;
  /** Tint, hex string. */
  color: string;
  /** Animation progress 0..1. */
  t: number;
  /** Lifetime in seconds; the per-frame loop advances t by dt/lifetime. */
  lifetime: number;
  /** Free-form payload, e.g. {kind: "Person"} for motes or
   *  {gate: "finance_signoff"} for sparks. Used by handlers that need
   *  more context than position alone. */
  payload?: Record<string, unknown>;
}

export interface AnimState {
  entries: AnimEntry[];
}

export type AnimAction =
  | { type: "enqueue"; entry: AnimEntry }
  | { type: "tick"; dt: number }
  | { type: "clearKind"; kind: AnimKind }
  | { type: "reset" };

// Per-kind caps. Oldest entries of the same kind are evicted on overflow.
export const KIND_CAPS: Record<AnimKind, number> = {
  spark: 64,
  beam: 32,
  pulse: 64,
  filament: 32,
  mote: 200,
};

export const initialAnimState: AnimState = { entries: [] };

export function animReducer(state: AnimState, action: AnimAction): AnimState {
  switch (action.type) {
    case "enqueue": {
      const cap = KIND_CAPS[action.entry.kind];
      const sameKind = state.entries.filter((e) => e.kind === action.entry.kind);
      const others = state.entries.filter((e) => e.kind !== action.entry.kind);
      const trimmed =
        sameKind.length >= cap
          ? sameKind.slice(sameKind.length - cap + 1)
          : sameKind;
      return { entries: [...others, ...trimmed, action.entry] };
    }
    case "tick": {
      const next: AnimEntry[] = [];
      for (const e of state.entries) {
        const advance = action.dt / Math.max(0.0001, e.lifetime);
        const t = e.t + advance;
        if (t >= 1) continue;
        next.push({ ...e, t });
      }
      // Reference equality short-circuit: if nothing changed, return prior state.
      if (next.length === state.entries.length && next.every((e, i) => e.t === state.entries[i].t)) {
        return state;
      }
      return { entries: next };
    }
    case "clearKind":
      return { entries: state.entries.filter((e) => e.kind !== action.kind) };
    case "reset":
      return initialAnimState;
    default:
      return state;
  }
}

/** Cheap unique id for queue entries. */
let idCounter = 0;
export function nextAnimId(prefix = "a"): string {
  idCounter = (idCounter + 1) | 0;
  return `${prefix}-${idCounter}-${Date.now()}`;
}

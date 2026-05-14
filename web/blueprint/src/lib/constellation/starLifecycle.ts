/**
 * Star = a single in-flight or recently-completed workflow.
 *
 * Lifecycle:
 *   - born:      fade in alpha 0→1 + scale 0.4→1 over BIRTH_MS
 *   - alive:     soft idle twinkle, gentle drift inside the cluster
 *   - awaiting:  parked on a HITL gate. Magenta tint, slow size-pulse.
 *                Sticky — stays until durable.resumed (or any subsequent
 *                step event) flips it back to alive. Does NOT decay.
 *   - exception: workflow.exception.detected / policy.violation tripped.
 *                Orange tint, faster pulse. Also sticky.
 *   - completed: bright flash to amber-white, then fade out over DIE_MS
 *   - blocked:   red flash, then fade out over DIE_MS
 *
 * After fully fading (only completed/blocked do), the star is removed from
 * the cluster.
 */
import type { Mote } from "../constellation/types";

export const BIRTH_MS = 1500;
export const DIE_MS = 4500;
/** A star with no events for this long is considered "drifting" — gradually
 *  dimmed but not removed (workflows can park at HITL gates for minutes). */
export const IDLE_DIM_MS = 8000;
/** Hard ceiling: regardless of state, after this long with no events, remove. */
export const HARD_TTL_MS = 90000;

export interface StarVisual {
  /** 0..1 alpha for this frame. */
  alpha: number;
  /** 0..1 scale for this frame. */
  scale: number;
  /** RGB tint for this frame, 0..1 each. */
  r: number;
  g: number;
  b: number;
  /** True if star should be culled this frame. */
  dead: boolean;
}

// Tints for the sticky non-fatal states. Picked to be visually distinct
// from the per-domain palette without clashing with the validator-red.
const AWAITING_R = 0.85;
const AWAITING_G = 0.40;
const AWAITING_B = 0.92; // magenta-violet
const EXCEPTION_R = 0.95;
const EXCEPTION_G = 0.55;
const EXCEPTION_B = 0.18; // orange

export function computeStarVisual(
  m: Mote,
  baseColor: { r: number; g: number; b: number },
  nowMs: number,
  bornAtMs: number,
  diedAtMs: number | null,
): StarVisual {
  const sinceBorn = nowMs - bornAtMs;
  const sinceLastSeen = nowMs - m.lastSeenMs;

  // Birth fade-in.
  let birth = 1;
  if (sinceBorn < BIRTH_MS) {
    birth = sinceBorn / BIRTH_MS;
  }

  // Death fade-out (only when explicitly completed/blocked or idle past TTL).
  if (diedAtMs !== null) {
    const sinceDied = nowMs - diedAtMs;
    if (sinceDied >= DIE_MS) {
      return { alpha: 0, scale: 0, r: 0, g: 0, b: 0, dead: true };
    }
    const k = 1 - sinceDied / DIE_MS;
    // Bright flash at moment of death, then ease toward zero.
    const flashBoost = m.state === "blocked" ? 1.8 : 1.6;
    const fade = k * k; // ease-out cubic-ish
    const alpha = Math.min(1, birth) * fade;
    const scale = (0.4 + 0.6 * birth) * (0.6 + 0.6 * fade);
    if (m.state === "blocked") {
      return {
        alpha,
        scale,
        r: 0.95 * flashBoost * fade + baseColor.r * 0.2,
        g: 0.30 * flashBoost * fade + baseColor.g * 0.2,
        b: 0.25 * flashBoost * fade + baseColor.b * 0.2,
        dead: false,
      };
    }
    return {
      alpha,
      scale,
      r: 0.96 * flashBoost * fade + baseColor.r * 0.3,
      g: 0.78 * flashBoost * fade + baseColor.g * 0.3,
      b: 0.30 * flashBoost * fade + baseColor.b * 0.3,
      dead: false,
    };
  }

  // Sticky non-fatal states — no diedAt, no decay, just a tinted pulse.
  if (m.state === "awaiting") {
    // Slow ~0.5Hz size+brightness pulse. Escalated gates pulse ~2x faster
    // and run a touch hotter so the operator's eye snaps to them.
    const speed = m.escalated ? 0.0050 : 0.0028;
    const tw = 0.6 + 0.4 * Math.sin(nowMs * speed + m.seed * 0.21);
    const sat = m.escalated ? 1.15 : 1.0;
    const alpha = Math.min(1, birth) * (0.85 + 0.15 * tw);
    const scale = (0.4 + 0.6 * birth) * (1.05 + 0.45 * tw);
    return {
      alpha,
      scale,
      r: AWAITING_R * sat * tw + baseColor.r * 0.10,
      g: AWAITING_G * sat * tw + baseColor.g * 0.10,
      b: AWAITING_B * sat * tw + baseColor.b * 0.10,
      dead: false,
    };
  }
  if (m.state === "exception") {
    const tw = 0.55 + 0.45 * Math.sin(nowMs * 0.0065 + m.seed * 0.41);
    const alpha = Math.min(1, birth) * (0.9 + 0.1 * tw);
    const scale = (0.4 + 0.6 * birth) * (1.1 + 0.5 * tw);
    return {
      alpha,
      scale,
      r: EXCEPTION_R * tw + baseColor.r * 0.10,
      g: EXCEPTION_G * tw + baseColor.g * 0.10,
      b: EXCEPTION_B * tw + baseColor.b * 0.10,
      dead: false,
    };
  }

  // Alive: soft twinkle + idle dimming. SLA breach overlays a slow
  // amber→red beat on top of the domain tint without leaving "alive".
  const tw = 0.75 + 0.35 * Math.sin(nowMs * 0.0018 + m.seed * 0.31);
  const idleDim =
    sinceLastSeen > IDLE_DIM_MS
      ? Math.max(0.35, 1 - (sinceLastSeen - IDLE_DIM_MS) / 30000)
      : 1;
  const alpha = Math.min(1, birth) * idleDim;
  const scale = (0.4 + 0.6 * birth) * (0.85 + 0.3 * m.progress);
  const bright = tw * (0.6 + 0.5 * m.progress);
  if (m.slaBreach) {
    // Pulse toward red-amber while keeping a hint of the domain tint.
    const beat = 0.5 + 0.5 * Math.sin(nowMs * 0.006 + m.seed * 0.13);
    return {
      alpha,
      scale: scale * (1 + 0.2 * beat),
      r: baseColor.r * bright * 0.5 + 0.95 * beat,
      g: baseColor.g * bright * 0.5 + 0.30 * beat,
      b: baseColor.b * bright * 0.5 + 0.20 * beat,
      dead: sinceLastSeen > HARD_TTL_MS,
    };
  }
  return {
    alpha,
    scale,
    r: baseColor.r * bright,
    g: baseColor.g * bright,
    b: baseColor.b * bright,
    dead: sinceLastSeen > HARD_TTL_MS,
  };
}

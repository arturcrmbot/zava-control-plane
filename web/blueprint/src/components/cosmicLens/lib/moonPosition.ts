/**
 * Cosmic Lens v2 — Moon orbit position helper.
 *
 * Resolves the world-space point a workflow's "moon" would occupy if it
 * were rendered. The visible moon meshes were dropped (rocket IS the
 * workflow), but Rockets / HoveredWorkflowPath still use this point as
 * the workflow's home anchor (fly-home target, hover-path origin).
 */

import { planetPosition } from "../FunctionPlanets";
import type { FunctionMeta } from "./types";
import { MoonRegistry } from "./registries";

const MOON_ORBIT_RADIUS_BASE = 1.6;
/** Moons sit at base..base+band so the orbit reads as a 3D shell. */
const MOON_ORBIT_RADIUS_BAND = 0.65;

/**
 * Resolve a workflow's anchor point near its parent planet using the
 * registry's stable hash offset. Used by Rockets (fly-home target) and
 * HoveredWorkflowPath (path origin).
 */
export function moonPosition(
  workflowId: string,
  fn: string | undefined,
  functions: FunctionMeta[],
  time: number,
  registry: MoonRegistry,
): [number, number, number] {
  const planet = planetPosition(fn, functions, time);
  const offset = registry.offsetFor(workflowId);
  const sharedRotation = time * 0.35;
  const moonAngle = sharedRotation + offset * Math.PI * 2;
  const radius = MOON_ORBIT_RADIUS_BASE + offset * MOON_ORBIT_RADIUS_BAND;
  return [
    planet[0] + Math.cos(moonAngle) * radius,
    planet[1] + Math.sin(moonAngle * 0.5 + offset * Math.PI * 2) * 0.4,
    planet[2] + Math.sin(moonAngle) * radius,
  ];
}

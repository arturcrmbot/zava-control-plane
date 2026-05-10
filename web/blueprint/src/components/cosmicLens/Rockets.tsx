import { useEffect, useMemo, useRef } from "react";
import * as THREE from "three";
import { useFrame } from "@react-three/fiber";
import type {
  CityMeta,
  CosmicFlash,
  CosmicMode,
  FunctionMeta,
  WorkflowMoonData,
} from "./lib/types";
import { MoonRegistry, RocketRegistry, TrailRegistry } from "./lib/registries";
import { moonPosition } from "./WorkflowMoons";
import { cityPosition } from "./Cities";
import { isReadEvent, isWriteEvent, labelForCapability, labelForEntity } from "./lib/labels";
import { buildWorkflowTypeToFunction, resolveFunction, workflowTypeFromId } from "./lib/workflowFunction";
import { colorForFunction } from "./lib/colors";

interface RocketsProps {
  flashesRef: React.MutableRefObject<{ buffer: CosmicFlash[]; version: number }>;
  inFlight: WorkflowMoonData[];
  cities: CityMeta[];
  functions: FunctionMeta[];
  mode: CosmicMode;
  /** External trail registry so Trails component can render the same data. */
  trailRegistry: TrailRegistry;
  /** External rocket registry so DirectionalBeams can read parked rockets. */
  rocketRegistry: RocketRegistry;
}

const MAX_ROCKETS = 200;
const ROCKET_BODY = 0.09;
const FLIGHT_MS = 1800; // outbound + return travel time
const MIN_PARK_MS = 800;
const DEFAULT_PARK_MS = 2500;

const matrix = new THREE.Matrix4();
const position = new THREE.Vector3();
const scale = new THREE.Vector3(1, 1, 1);
const quaternion = new THREE.Quaternion();
const tmpColor = new THREE.Color();
const yAxis = new THREE.Vector3(0, 1, 0);

/**
 * Rockets — workflow's currently-active step in motion.
 *
 * Phase A: dispatch on tool.invoked / persona.thinking events; pick a
 * deterministic city based on hash of event payload so motion is visible
 * even if cities aren't yet labeled correctly. Phase B does proper city
 * targeting via tool_name lookup.
 */
export function Rockets({ flashesRef, inFlight, cities, functions, mode, trailRegistry, rocketRegistry }: RocketsProps) {
  const meshRef = useRef<THREE.InstancedMesh>(null);
  const moonRegistry = useMemo(() => new MoonRegistry(), []);
  const lastVersionRef = useRef(0);
  const counterRef = useRef(0);

  // Build quick lookup: workflow_id → function key (for moon position resolution)
  const wfFn = useMemo(() => {
    const wfTypeMap = buildWorkflowTypeToFunction(functions);
    const m = new Map<string, string>();
    inFlight.forEach((wf) => {
      const wfType = wf.workflow_type || workflowTypeFromId(wf.id) || "";
      m.set(wf.id, resolveFunction({ ...wf, workflow_type: wfType } as WorkflowMoonData, wfTypeMap));
    });
    return m;
  }, [inFlight, functions]);

  // Rebuild city list lookup by id for quick resolution
  const cityById = useMemo(() => {
    const m = new Map<string, CityMeta>();
    cities.forEach((c) => m.set(c.id, c));
    return m;
  }, [cities]);

  // Pre-compute deterministic city positions (matches Cities.tsx logic exactly)
  const cityPositions = useMemo(() => {
    const m = new Map<string, [number, number, number]>();
    cities.forEach((city) => {
      m.set(city.id, cityPosition(city.id));
    });
    return m;
  }, [cities]);

  // Drain new flashes and dispatch rockets
  useEffect(() => {
    const interval = setInterval(() => {
      const ref = flashesRef.current;
      if (ref.version === lastVersionRef.current) return;
      lastVersionRef.current = ref.version;
      const buffer = ref.buffer;
      const now = Date.now();
      // Only process the most recent batch (last 50 events) to avoid
      // dispatching a backlog of rockets when SSE just connected.
      const tail = buffer.slice(Math.max(0, buffer.length - 50));
      for (const flash of tail) {
        if (rocketRegistry.size() >= MAX_ROCKETS) break;
        // Only dispatch in capabilities mode for Phase A
        if (mode === "capabilities") {
          if (
            flash.type !== "tool.invoked" &&
            flash.type !== "persona.thinking" &&
            flash.type !== "ambient.decided"
          ) {
            continue;
          }
        } else {
          if (
            flash.type !== "entity.read" &&
            flash.type !== "entity.upserted" &&
            flash.type !== "entity.linked"
          ) {
            continue;
          }
        }
        const workflowId = flash.workflow_id ?? flash.caller_workflow_id;
        if (!workflowId) continue;
        // Already dispatched a rocket for this exact event recently? Skip dedup.
        const existingId = rocketKey(flash, counterRef.current);
        if (rocketRegistry.has(existingId)) continue;
        const cityId = pickCityForFlash(flash, cities, mode);
        if (!cityId) continue;
        counterRef.current += 1;
        const id = `r-${counterRef.current}`;
        rocketRegistry.set(id, {
          id,
          workflow_id: workflowId,
          city_id: cityId,
          label: mode === "capabilities" ? labelForCapability(flash) : labelForEntity(flash),
          origin_workflow_id: workflowId,
          phase: "outbound",
          dispatched_at: now,
          is_read: isReadEvent(flash.type),
          is_write: isWriteEvent(flash.type),
        });
      }
    }, 100);
    return () => clearInterval(interval);
  }, [flashesRef, rocketRegistry, cities, mode]);

  // Listen for completion events to mark rockets as returning
  useEffect(() => {
    const interval = setInterval(() => {
      const buf = flashesRef.current.buffer;
      const tail = buf.slice(Math.max(0, buf.length - 30));
      for (const flash of tail) {
        const isCompletion =
          flash.type === "tool.completed" ||
          flash.type === "persona.decided" ||
          flash.type === "decision.recorded";
        if (!isCompletion) continue;
        const wfId = flash.workflow_id ?? flash.caller_workflow_id;
        if (!wfId) continue;
        const r = rocketRegistry.latestForWorkflow(wfId);
        if (!r) continue;
        if (r.phase === "parked" || r.phase === "outbound") {
          r.phase = "returning";
          r.completed_at = Date.now();
        }
      }
    }, 200);
    return () => clearInterval(interval);
  }, [flashesRef, rocketRegistry]);

  useFrame((state) => {
    if (!meshRef.current) return;
    const mesh = meshRef.current;
    const t = state.clock.getElapsedTime();
    const now = Date.now();
    let i = 0;

    rocketRegistry.values().forEach((r) => {
      if (i >= MAX_ROCKETS) return;
      const fn = wfFn.get(r.workflow_id);
      const moonPos = moonPosition(r.workflow_id, fn, functions, t, moonRegistry);
      const cityPos = cityPositions.get(r.city_id) ?? [0, 0.42, 0];

      let px: number, py: number, pz: number;
      const sinceDispatch = now - r.dispatched_at;

      if (r.phase === "outbound") {
        const progress = Math.min(1, sinceDispatch / FLIGHT_MS);
        // Arc up between moon and city
        const arcY = Math.sin(progress * Math.PI) * 1.5;
        px = moonPos[0] + (cityPos[0] - moonPos[0]) * progress;
        pz = moonPos[2] + (cityPos[2] - moonPos[2]) * progress;
        py = moonPos[1] + (cityPos[1] - moonPos[1]) * progress + arcY;
        if (progress >= 1) {
          r.phase = "parked";
          r.parked_at = now;
        }
      } else if (r.phase === "parked") {
        // Hover slightly above the city with a gentle bob
        const bob = Math.sin(t * 3 + r.dispatched_at * 0.001) * 0.05;
        px = cityPos[0];
        py = cityPos[1] + 0.45 + bob;
        pz = cityPos[2];
        // Auto-complete after DEFAULT_PARK_MS even without backend completion
        // event (so demo always animates rockets back).
        const parkAge = now - (r.parked_at ?? now);
        if (parkAge > Math.max(MIN_PARK_MS, DEFAULT_PARK_MS) && !r.completed_at) {
          r.phase = "returning";
          r.completed_at = now;
        }
      } else if (r.phase === "returning") {
        const sinceComplete = now - (r.completed_at ?? now);
        const progress = Math.min(1, sinceComplete / FLIGHT_MS);
        const arcY = Math.sin(progress * Math.PI) * 1.0;
        px = cityPos[0] + (moonPos[0] - cityPos[0]) * progress;
        pz = cityPos[2] + (moonPos[2] - cityPos[2]) * progress;
        py = cityPos[1] + (moonPos[1] - cityPos[1]) * progress + arcY;
        if (progress >= 1) {
          r.phase = "done";
          r.returned_at = now;
          // Emit a trail sample on completion (only once per rocket).
          // Color: function family of the origin moon, with read/write
          // override taking precedence so entity ops are still visible.
          let trailColor = colorForFunction(fn);
          if (r.is_write) trailColor = "#fb923c";
          else if (r.is_read) trailColor = "#67e8f9";
          else if (r.is_exception) trailColor = "#ef4444";
          trailRegistry.push({
            from: moonPos,
            to: cityPos,
            emitted_at: now,
            color: trailColor,
          });
        }
      } else {
        // done — park off-screen
        px = 0;
        py = -100;
        pz = 0;
      }

      // Orient the rocket along its direction of travel (approx)
      let orientation = quaternion;
      // When parked, point cone "into" city (Phase D entity beam will refine)
      if (r.phase === "parked") {
        // nose down at the city
        orientation = new THREE.Quaternion().setFromAxisAngle(new THREE.Vector3(1, 0, 0), Math.PI);
      } else {
        orientation = quaternion;
      }
      position.set(px, py, pz);
      matrix.compose(position, orientation, scale);
      mesh.setMatrixAt(i, matrix);
      // Color by mode + read/write
      let colorHex = "#22d3ee";
      if (r.is_write) colorHex = "#fb923c";
      else if (r.is_read) colorHex = "#67e8f9";
      else if (r.is_exception) colorHex = "#ef4444";
      tmpColor.set(colorHex);
      mesh.setColorAt(i, tmpColor);
      i++;
    });
    // Park unused
    for (let j = i; j < MAX_ROCKETS; j++) {
      position.set(0, -100, 0);
      matrix.compose(position, quaternion, scale);
      mesh.setMatrixAt(j, matrix);
    }
    mesh.instanceMatrix.needsUpdate = true;
    if (mesh.instanceColor) mesh.instanceColor.needsUpdate = true;
    mesh.count = MAX_ROCKETS;

    // Periodic prune
    if (Math.floor(t) % 10 === 0) {
      rocketRegistry.pruneCompleted(now, 4000);
    }
  });

  return (
    <instancedMesh ref={meshRef} args={[undefined, undefined, MAX_ROCKETS]} castShadow>
      <coneGeometry args={[ROCKET_BODY, ROCKET_BODY * 2.5, 6]} />
      <meshBasicMaterial vertexColors />
    </instancedMesh>
  );
}

/** Build a deterministic key for dedup (Phase A doesn't need it strictly). */
function rocketKey(flash: CosmicFlash, counter: number): string {
  return `${flash.type}-${flash.workflow_id}-${counter}`;
}

/** Pick a city to target. Phase A: hash event to a city id when no precise match. */
function pickCityForFlash(
  flash: CosmicFlash,
  cities: CityMeta[],
  mode: CosmicMode,
): string | null {
  if (!cities.length) return null;
  // Capabilities mode: try to match by tool/persona name
  if (mode === "capabilities") {
    if (flash.type === "persona.thinking" && flash.persona) {
      // Look for a persona-kind city with this id/label
      const found = cities.find(
        (c) => c.kind === "persona" && (c.id === flash.persona || c.label === flash.persona),
      );
      if (found) return found.id;
    }
    if (flash.type === "tool.invoked" && flash.tool_name) {
      const tn = flash.tool_name;
      const found = cities.find(
        (c) =>
          c.id === tn ||
          c.label === tn ||
          c.id.endsWith(tn) ||
          tn.startsWith(c.id),
      );
      if (found) return found.id;
    }
    // Fall back to hash
  } else {
    // Entities mode: target the entity-type city
    if (flash.entity_kind) {
      const found = cities.find(
        (c) => c.kind === "entity_type" && (c.id === flash.entity_kind || c.label === flash.entity_kind),
      );
      if (found) return found.id;
    }
  }
  // Hash fallback so motion is always visible even before backend wires names properly
  let hash = 5381;
  const seed = `${flash.type}-${flash.workflow_id ?? ""}-${flash.persona ?? flash.tool_name ?? flash.entity_kind ?? ""}`;
  for (let i = 0; i < seed.length; i++) {
    hash = ((hash << 5) + hash + seed.charCodeAt(i)) | 0;
  }
  const idx = Math.abs(hash) % cities.length;
  return cities[idx].id;
}

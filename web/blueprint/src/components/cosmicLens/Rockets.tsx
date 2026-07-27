import { useEffect, useMemo, useRef, useState } from "react";
import * as THREE from "three";
import { useFrame } from "@react-three/fiber";
import { Html } from "@react-three/drei";
import type {
  CityMeta,
  CosmicFlash,
  CosmicMode,
  FunctionMeta,
  Rocket,
  WorkflowMoonData,
} from "./lib/types";
import { MoonRegistry, RocketRegistry, TrailRegistry } from "./lib/registries";
import type { ExhaustRegistry } from "./RocketExhaust";
import { moonPosition } from "./lib/moonPosition";
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
  /** Particle plume buffer — rockets push exhaust particles into this every
   *  frame while travelling. Replaces the lineSegment trail. */
  exhaustRegistry: ExhaustRegistry;
  /** External rocket registry so DirectionalBeams + HoveredWorkflowPath can read it. */
  rocketRegistry: RocketRegistry;
  /** When set, brighten/upscale the rocket owned by this workflow. */
  highlightWorkflowId?: string | null;
  /** Click on a rocket — entities mode prefers last_entity_id over workflow_id. */
  onRocketClick?: (rocket: Rocket) => void;
  /** Hover on a rocket — used to drive the orbital path overlay + sibling highlight. */
  onRocketHover?: (workflowId: string | null) => void;
}

const ROCKET_BODY = 0.13;
const TRAVEL_MS = 1200;
const RETURN_MS = 1000;
const BURST_MS = 600;
const TRAIL_EMIT_TRAVEL_EVERY_FRAMES = 1;
const TRAIL_EMIT_IDLE_EVERY_FRAMES = 6;
const WOUNDED_RED = "#ef4444";
/** Hard cap on rockets rendered in a single frame. Set very high
 *  (effectively off) so all in-flight workflows are visible by default at
 *  the current ~25-50 concurrency. The cap mechanism is kept for future
 *  scale; the "+N more" overflow indicator only surfaces if the cap is
 *  ever actually exceeded. */
const MAX_VISIBLE_ROCKETS = 9999;

// Cubic ease-in-out
function ease(p: number): number {
  return p < 0.5 ? 4 * p * p * p : 1 - Math.pow(-2 * p + 2, 3) / 2;
}

// Lerp two colour strings into a THREE.Color (returned by ref).
const _lerpA = new THREE.Color();
const _lerpB = new THREE.Color();
function lerpColor(out: THREE.Color, fromHex: string, toHex: string, t: number): THREE.Color {
  _lerpA.set(fromHex);
  _lerpB.set(toHex);
  out.copy(_lerpA).lerp(_lerpB, t);
  return out;
}

interface BurstHandle {
  ringRef: React.MutableRefObject<THREE.Mesh | null>;
}

/**
 * Rockets — one per in-flight workflow.
 *
 * Spawn on workflow.started; one entry in rocketRegistry keyed by workflow_id.
 * Travel smoothly between cities on tool/persona/executor events. Bob in place
 * while idle. Fly back to the workflow's moon and burst on completion.
 *
 * At expected scale (10–30 simultaneous rockets) we draw one mesh per rocket
 * instead of an InstancedMesh — gives free per-rocket colour without the
 * vertexColors-on-InstancedMesh shader-compile hazard documented in STATE.md.
 */
export function Rockets({ flashesRef, inFlight, cities, functions, mode, trailRegistry, exhaustRegistry, rocketRegistry, highlightWorkflowId, onRocketClick, onRocketHover }: RocketsProps) {
  const moonRegistry = useMemo(() => new MoonRegistry(), []);
  const lastVersionRef = useRef(0);
  const frameRef = useRef(0);
  const diagRef = useRef<{ ticks: number; lastDrawnCount: number }>({ ticks: 0, lastDrawnCount: 0 });

  // Expose diagnostics handle on the registry so CosmicLens can publish it
  // through window.__cosmic.rocketDiag().
  useEffect(() => {
    (rocketRegistry as unknown as { __diag?: typeof diagRef.current }).__diag = diagRef.current;
  }, [rocketRegistry]);

  // workflow_id -> function key
  const wfFn = useMemo(() => {
    const wfTypeMap = buildWorkflowTypeToFunction(functions);
    const m = new Map<string, string>();
    inFlight.forEach((wf) => {
      const wfType = wf.workflow_type || workflowTypeFromId(wf.id) || "";
      m.set(wf.id, resolveFunction({ ...wf, workflow_type: wfType } as WorkflowMoonData, wfTypeMap));
    });
    return m;
  }, [inFlight, functions]);

  const cityPositions = useMemo(() => {
    const m = new Map<string, [number, number, number]>();
    cities.forEach((city) => {
      m.set(city.id, cityPosition(city.id));
    });
    return m;
  }, [cities]);

  // Set of currently in-flight workflow ids (for spawn-on-discovery + despawn-on-disappear).
  const inFlightIds = useMemo(() => new Set(inFlight.map((w) => w.id)), [inFlight]);
  const woundedIds = useMemo(() => {
    const s = new Set<string>();
    for (const w of inFlight) if (w.active_exception_id) s.add(w.id);
    return s;
  }, [inFlight]);

  // Spawn a rocket for any in-flight workflow that doesn't have one yet.
  // Mark wounded flag from the polled in-flight snapshot.
  useEffect(() => {
    const now = Date.now();
    for (const wf of inFlight) {
      const fn = wfFn.get(wf.id);
      const r = rocketRegistry.upsertForWorkflow(wf.id, () => {
        const moonPos = moonPosition(wf.id, fn, functions, performance.now() / 1000, moonRegistry);
        return {
          id: wf.id,
          workflow_id: wf.id,
          origin_workflow_id: wf.id,
          phase: "idle",
          color: colorForFunction(fn),
          current_city_id: null,
          target_city_id: null,
          current_pos: moonPos,
          travel_from: null,
          travel_to: null,
          phase_started_at: now,
          spawned_at: now,
          is_wounded: !!wf.active_exception_id,
        };
      });
      r.is_wounded = woundedIds.has(wf.id);
    }
  }, [inFlight, rocketRegistry, wfFn, functions, moonRegistry, woundedIds]);

  // Drain new flashes — drive travel + completion.
  useEffect(() => {
    const interval = setInterval(() => {
      const ref = flashesRef.current;
      if (ref.version === lastVersionRef.current) return;
      const buffer = ref.buffer;
      const since = lastVersionRef.current;
      lastVersionRef.current = ref.version;
      // We don't know exactly which buffer entries were appended since the
      // last drain (the ref doesn't track it), so process the most recent
      // batch heuristically: at most (version-since) tail entries.
      const newCount = Math.max(1, Math.min(buffer.length, ref.version - since));
      const tail = buffer.slice(buffer.length - newCount);
      const now = Date.now();
      for (const flash of tail) {
        const workflowId = flash.workflow_id ?? flash.caller_workflow_id;
        if (!workflowId) continue;
        let r = rocketRegistry.forWorkflow(workflowId);
        if (!r) {
          const wfTypeMap = buildWorkflowTypeToFunction(functions);
          const workflowType = workflowTypeFromId(workflowId) || "";
          const fn = resolveFunction(
            {
              id: workflowId,
              workflow_type: workflowType,
              function: "",
              status: "in_progress",
            },
            wfTypeMap,
          );
          const moonPos = moonPosition(
            workflowId,
            fn,
            functions,
            performance.now() / 1000,
            moonRegistry,
          );
          r = rocketRegistry.upsertForWorkflow(workflowId, () => ({
            id: workflowId,
            workflow_id: workflowId,
            origin_workflow_id: workflowId,
            phase: "idle",
            color: colorForFunction(fn),
            current_city_id: null,
            target_city_id: null,
            current_pos: moonPos,
            travel_from: null,
            travel_to: null,
            phase_started_at: now,
            spawned_at: now,
            is_wounded: false,
          }));
          wfFn.set(workflowId, fn);
        }

        // Completion: fly home and burst.
        const isCompletion =
          flash.type === "workflow.completed" ||
          flash.type === "durable.workflow.completed" ||
          flash.type === "workflow.failed";
        if (isCompletion && r.phase !== "returning" && r.phase !== "burst" && r.phase !== "done") {
          const fn = wfFn.get(r.workflow_id);
          const moonPos = moonPosition(r.workflow_id, fn, functions, performance.now() / 1000, moonRegistry);
          r.travel_from = [...r.current_pos];
          r.travel_to = moonPos;
          r.target_city_id = null;
          r.phase = "returning";
          r.phase_started_at = now;
          continue;
        }

        // Travel: tool / executor.invoked / persona.thinking / ambient.decided
        const isExecutorStart =
          flash.type === "durable.executor.invoked" &&
          (flash as unknown as { stage?: string }).stage === "start";
        const isCapabilityEvent =
          flash.type === "persona.thinking" ||
          flash.type === "ambient.decided" ||
          isExecutorStart;
        // `tool.invoked` is intentionally not listened for — the substrate emits
        // `durable.executor.invoked` for every tool/skill/validator/agent
        // invocation; checking both was a duplicate.
        const isEntityEvent =
          flash.type === "entity.read" ||
          flash.type === "entity.upserted" ||
          flash.type === "entity.linked";
        const isTravelEvent =
          mode === "capabilities" ? isCapabilityEvent : isEntityEvent;
        if (!isTravelEvent) continue;

        const cityId = pickCityForFlash(flash, cities, mode);
        if (!cityId) continue;
        const cityPos = cityPositions.get(cityId);
        if (!cityPos) continue;

        // Skip pure-repeat travels to the same city while still travelling
        // there (avoids stutter when multiple events fire on one tool).
        if (r.phase === "travelling" && r.target_city_id === cityId) continue;

        r.travel_from = [...r.current_pos];
        r.travel_to = [...cityPos];
        r.target_city_id = cityId;
        r.phase = "travelling";
        r.phase_started_at = now;
        r.last_event_type = flash.type;
        r.last_label = mode === "capabilities" ? labelForCapability(flash) : labelForEntity(flash);
        // Capture entity_id off entity events so a click-to-EntityView in
        // entities mode can target the most recently-touched entity.
        const eid = (flash as unknown as { entity_id?: string }).entity_id;
        if (eid) {
          (r as unknown as { last_entity_id?: string }).last_entity_id = eid;
        }
        r.is_read = isReadEvent(flash.type);
        r.is_write = isWriteEvent(flash.type);
      }
    }, 100);
    return () => clearInterval(interval);
  }, [flashesRef, rocketRegistry, cities, mode, cityPositions, wfFn, functions, moonRegistry]);

  // Per-frame: integrate phase, write each rocket's mesh transform/color via refs.
  const meshRefs = useRef(new Map<string, THREE.Mesh>());
  const haloRefs = useRef(new Map<string, THREE.Mesh>());
  const burstRefs = useRef(new Map<string, BurstHandle>());
  const tmpColor = useMemo(() => new THREE.Color(), []);
  const tmpVec = useMemo(() => new THREE.Vector3(), []);
  const upY = useMemo(() => new THREE.Vector3(0, 1, 0), []);
  const downY = useMemo(() => new THREE.Vector3(0, -1, 0), []);

  useFrame((state) => {
    frameRef.current++;
    const t = state.clock.getElapsedTime();
    const now = Date.now();
    let drawn = 0;

    // Despawn any rockets whose workflow is no longer in flight AND who are
    // already idle/done (don't yank rockets mid-travel — let them complete
    // naturally via workflow.completed flash).
    for (const r of rocketRegistry.values()) {
      if (!inFlightIds.has(r.workflow_id) && (r.phase === "idle" || r.phase === "done")) {
        // Treat as completion: fly home + burst.
        if (r.phase === "idle") {
          const fn = wfFn.get(r.workflow_id);
          const moonPos = moonPosition(r.workflow_id, fn, functions, t, moonRegistry);
          r.travel_from = [...r.current_pos];
          r.travel_to = moonPos;
          r.target_city_id = null;
          r.phase = "returning";
          r.phase_started_at = now;
        }
      }
    }

    for (const r of rocketRegistry.values()) {
      const mesh = meshRefs.current.get(r.id);
      if (!mesh) continue;
      const halo = haloRefs.current.get(r.id);
      const fn = wfFn.get(r.workflow_id);
      const moonPos = moonPosition(r.workflow_id, fn, functions, t, moonRegistry);
      const phaseAge = now - r.phase_started_at;

      let px = r.current_pos[0];
      let py = r.current_pos[1];
      let pz = r.current_pos[2];
      let dirSet = false;

      // Remember previous render position so we can derive instantaneous
      // heading from frame-to-frame delta. Pointing the nose along the
      // straight start→end chord looks wrong at the apex of an arced flight
      // because the rocket's actual motion is sideways while the chord
      // points downward toward the destination.
      const prevRender = (r as unknown as { _last_render_pos?: [number, number, number] })._last_render_pos;

      if (r.phase === "travelling" && r.travel_from && r.travel_to) {
        const p = Math.min(1, phaseAge / TRAVEL_MS);
        const e = ease(p);
        const arc = Math.sin(p * Math.PI) * 1.5;
        px = r.travel_from[0] + (r.travel_to[0] - r.travel_from[0]) * e;
        pz = r.travel_from[2] + (r.travel_to[2] - r.travel_from[2]) * e;
        py = r.travel_from[1] + (r.travel_to[1] - r.travel_from[1]) * e + arc;
        // Heading from actual frame-to-frame velocity (handles arc tangent).
        if (prevRender) {
          tmpVec.set(px - prevRender[0], py - prevRender[1], pz - prevRender[2]);
          if (tmpVec.lengthSq() > 1e-8) {
            tmpVec.normalize();
            mesh.quaternion.setFromUnitVectors(upY, tmpVec);
          }
        } else {
          tmpVec.set(r.travel_to[0] - r.travel_from[0], r.travel_to[1] - r.travel_from[1], r.travel_to[2] - r.travel_from[2]).normalize();
          mesh.quaternion.setFromUnitVectors(upY, tmpVec);
        }
        dirSet = true;
        if (p >= 1) {
          r.phase = "idle";
          r.phase_started_at = now;
          r.current_city_id = r.target_city_id;
          if (r.target_city_id) rocketRegistry.recordVisit(r.workflow_id, r.target_city_id, now);
          r.travel_from = null;
          r.travel_to = null;
        }
        // Particle exhaust plume — emit 2 particles per frame while
        // travelling. Each spawns at the engine nozzle (just behind the
        // rocket centre) with velocity counter to the direction of travel
        // plus a small random scatter so the plume isn't a perfect line.
        if (r.travel_to) {
          const exhaustColor = r.is_wounded ? WOUNDED_RED : r.color;
          const nozzleOffset = 0.16;
          const nx = px - tmpVec.x * nozzleOffset;
          const ny = py - tmpVec.y * nozzleOffset;
          const nz = pz - tmpVec.z * nozzleOffset;
          const baseSpeed = 1.4;
          for (let k = 0; k < 2; k++) {
            const jitter = 0.55;
            const vx = -tmpVec.x * baseSpeed + (Math.random() - 0.5) * jitter;
            const vy = -tmpVec.y * baseSpeed + (Math.random() - 0.5) * jitter;
            const vz = -tmpVec.z * baseSpeed + (Math.random() - 0.5) * jitter;
            exhaustRegistry.emit(
              [nx, ny, nz],
              [vx, vy, vz],
              exhaustColor,
              0.85 + Math.random() * 0.35,
              0.16 + Math.random() * 0.06,
            );
          }
        }
      } else if (r.phase === "idle") {
        // Idle = parked. Slowly orbit the parent city so the rocket reads as
        // ALIVE (a little ship circling its planet) instead of standing
        // upright like a pylon. Nose follows the orbit tangent so the body
        // is horizontal and the direction-of-flight is unambiguous.
        const base = r.current_city_id && cityPositions.has(r.current_city_id)
          ? cityPositions.get(r.current_city_id)!
          : moonPos;
        // Stable hash from rocket id → uniformly distributed phase offset
        // and per-rocket orbital radius. spawned_at-based offsets clustered
        // because many rockets at a busy city spawn within seconds of each
        // other, producing near-identical positions and a 'chain of beads'
        // look. Hash gives even distribution around the full circle.
        let h = 0;
        for (let k = 0; k < r.id.length; k++) h = (h * 31 + r.id.charCodeAt(k)) | 0;
        const phaseOffset = ((h >>> 0) % 1000) / 1000 * Math.PI * 2;
        const radiusJitter = (((h >>> 8) >>> 0) % 1000) / 1000;
        const orbitSpeed = 0.45;
        const orbitR = 0.6 + radiusJitter * 0.55;
        const angle = t * orbitSpeed + phaseOffset;
        const cos = Math.cos(angle);
        const sin = Math.sin(angle);
        const bob = Math.sin(t * 2.5 + (h & 0xffff) * 0.0007) * 0.04;
        px = base[0] + cos * orbitR;
        py = base[1] + 0.42 + bob;
        pz = base[2] + sin * orbitR;
        // Tangent to circular orbit at angle a is (-sin a, 0, cos a). Point
        // the rocket's +Y nose along the tangent — body lies flat on the
        // disc plane and nose leads the motion.
        tmpVec.set(-sin, 0, cos);
        mesh.quaternion.setFromUnitVectors(upY, tmpVec);
        dirSet = true;
        // No exhaust trail at idle — rockets coast with engines off.
      } else if (r.phase === "returning" && r.travel_from && r.travel_to) {
        const p = Math.min(1, phaseAge / RETURN_MS);
        const e = ease(p);
        const arc = Math.sin(p * Math.PI) * 1.0;
        px = r.travel_from[0] + (r.travel_to[0] - r.travel_from[0]) * e;
        pz = r.travel_from[2] + (r.travel_to[2] - r.travel_from[2]) * e;
        py = r.travel_from[1] + (r.travel_to[1] - r.travel_from[1]) * e + arc;
        if (prevRender) {
          tmpVec.set(px - prevRender[0], py - prevRender[1], pz - prevRender[2]);
          if (tmpVec.lengthSq() > 1e-8) {
            tmpVec.normalize();
            mesh.quaternion.setFromUnitVectors(upY, tmpVec);
          }
        } else {
          tmpVec.set(r.travel_to[0] - r.travel_from[0], r.travel_to[1] - r.travel_from[1], r.travel_to[2] - r.travel_from[2]).normalize();
          mesh.quaternion.setFromUnitVectors(upY, tmpVec);
        }
        dirSet = true;
        // Particle exhaust during return flight (same pattern as travel).
        if (r.travel_to) {
          const exhaustColor = r.is_wounded ? WOUNDED_RED : r.color;
          const nozzleOffset = 0.16;
          const nx = px - tmpVec.x * nozzleOffset;
          const ny = py - tmpVec.y * nozzleOffset;
          const nz = pz - tmpVec.z * nozzleOffset;
          const baseSpeed = 1.2;
          for (let k = 0; k < 2; k++) {
            const jitter = 0.5;
            const vx = -tmpVec.x * baseSpeed + (Math.random() - 0.5) * jitter;
            const vy = -tmpVec.y * baseSpeed + (Math.random() - 0.5) * jitter;
            const vz = -tmpVec.z * baseSpeed + (Math.random() - 0.5) * jitter;
            exhaustRegistry.emit(
              [nx, ny, nz],
              [vx, vy, vz],
              exhaustColor,
              0.8 + Math.random() * 0.35,
              0.14 + Math.random() * 0.05,
            );
          }
        }
        if (p >= 1) {
          r.phase = "burst";
          r.phase_started_at = now;
          r.current_pos = [r.travel_to[0], r.travel_to[1], r.travel_to[2]];
          r.travel_from = null;
          r.travel_to = null;
        }
      } else if (r.phase === "burst") {
        // Stay at moon, scale up the burst ring + fade.
        const moonNow = moonPos;
        px = moonNow[0];
        py = moonNow[1];
        pz = moonNow[2];
        const burstP = Math.min(1, phaseAge / BURST_MS);
        const burstHandle = burstRefs.current.get(r.id);
        if (burstHandle?.ringRef.current) {
          const s = 0.4 + burstP * 1.6;
          burstHandle.ringRef.current.scale.set(s, s, s);
          burstHandle.ringRef.current.position.set(px, py, pz);
          const mat = burstHandle.ringRef.current.material as THREE.MeshBasicMaterial;
          mat.opacity = 0.7 * (1 - burstP);
          mat.color.set(r.is_wounded ? WOUNDED_RED : r.color);
          mat.transparent = true;
          mat.depthWrite = false;
        }
        if (burstP >= 1) {
          r.phase = "done";
        }
      } else {
        // done — park off-screen until pruneCompleted clears it this frame.
        px = 0;
        py = -100;
        pz = 0;
      }

      r.current_pos = [px, py, pz];
      (r as unknown as { _last_render_pos?: [number, number, number] })._last_render_pos = [px, py, pz];
      mesh.position.set(px, py, pz);
      if (!dirSet) {
        mesh.quaternion.identity();
      }

      // Body color: lerp toward red if wounded; brighten if highlighted.
      const baseHex = r.color;
      if (r.is_wounded) {
        lerpColor(tmpColor, baseHex, WOUNDED_RED, 0.6);
      } else {
        tmpColor.set(baseHex);
      }
      const isHighlighted = !!highlightWorkflowId && r.workflow_id === highlightWorkflowId;
      const bodyMat = mesh.material as THREE.MeshBasicMaterial;
      bodyMat.color.copy(tmpColor);
      const s = isHighlighted ? 2.4 : 1.0;
      mesh.scale.set(s, s, s);

      if (halo) {
        halo.position.set(px, py, pz);
        const haloPulse = 1 + 0.15 * Math.sin(t * 4 + r.spawned_at * 0.0007);
        const sH = isHighlighted ? 3.0 : haloPulse;
        halo.scale.set(sH, sH, sH);
        const haloMat = halo.material as THREE.MeshBasicMaterial;
        haloMat.color.copy(tmpColor);
      }

      if (r.phase !== "done") drawn++;
    }

    // Cheap, every-frame prune of done rockets (tight: no time gating).
    rocketRegistry.pruneCompleted();

    diagRef.current.ticks++;
    diagRef.current.lastDrawnCount = drawn;
    if (diagRef.current.ticks % 120 === 0 && drawn > 0) {
      const sample = rocketRegistry.values().slice(0, 3).map((r) => ({
        id: r.id,
        wf: r.workflow_id,
        phase: r.phase,
        city: r.current_city_id,
        color: r.color,
      }));
      console.debug("[rocket-diag]", { active: drawn, sample });
    }
  });

  // Render one mesh per active rocket. React reconciliation uses key=workflow_id
  // so adding/removing workflows is a clean mount/unmount. We cap at
  // MAX_VISIBLE_ROCKETS sprites per frame and surface the remainder as a
  // single overflow chip so the scene stays responsive under burst load.
  const allLive = rocketRegistry.values();
  // Prefer travelling rockets, then most recently active — keeps the
  // visible set biased toward "where work is actually moving" instead of
  // arbitrarily dropping the tail of the registry.
  const sortedLive = [...allLive].sort((a, b) => {
    const aTravel = a.phase === "travelling" ? 1 : 0;
    const bTravel = b.phase === "travelling" ? 1 : 0;
    if (aTravel !== bTravel) return bTravel - aTravel;
    return b.phase_started_at - a.phase_started_at;
  });
  const live = sortedLive.slice(0, MAX_VISIBLE_ROCKETS);
  const overflow = Math.max(0, sortedLive.length - live.length);

  return (
    <>
      {live.map((r) => (
        <RocketMesh
          key={r.id}
          rocket={r}
          radius={ROCKET_BODY}
          meshRefs={meshRefs}
          haloRefs={haloRefs}
          burstRefs={burstRefs}
          onRocketClick={onRocketClick}
          onRocketHover={onRocketHover}
          mode={mode}
        />
      ))}
      {overflow > 0 && (
        <Html position={[0, 1.2, 0]} center style={{ pointerEvents: "none" }}>
          <div
            style={{
              background: "rgba(2,6,23,0.92)",
              color: "#fbbf24",
              border: "1px solid rgba(251,191,36,0.6)",
              borderRadius: 999,
              padding: "2px 10px",
              fontSize: 11,
              fontWeight: 600,
              fontFamily: "ui-sans-serif, system-ui",
              whiteSpace: "nowrap",
              boxShadow: "0 0 12px rgba(251,191,36,0.35)",
            }}
          >
            +{overflow} more in flight
          </div>
        </Html>
      )}
    </>
  );
}

interface RocketMeshProps {
  rocket: Rocket;
  radius: number;
  meshRefs: React.MutableRefObject<Map<string, THREE.Mesh>>;
  haloRefs: React.MutableRefObject<Map<string, THREE.Mesh>>;
  burstRefs: React.MutableRefObject<Map<string, BurstHandle>>;
  onRocketClick?: (rocket: Rocket) => void;
  onRocketHover?: (workflowId: string | null) => void;
  mode: CosmicMode;
}

function RocketMesh({ rocket, radius, meshRefs, haloRefs, burstRefs, onRocketClick, onRocketHover, mode }: RocketMeshProps) {
  const meshRef = useRef<THREE.Mesh>(null);
  const haloRef = useRef<THREE.Mesh>(null);
  const ringRef = useRef<THREE.Mesh>(null);
  const [hover, setHover] = useState(false);

  useEffect(() => {
    if (meshRef.current) meshRefs.current.set(rocket.id, meshRef.current);
    if (haloRef.current) haloRefs.current.set(rocket.id, haloRef.current);
    burstRefs.current.set(rocket.id, { ringRef });
    const id = rocket.id;
    return () => {
      meshRefs.current.delete(id);
      haloRefs.current.delete(id);
      burstRefs.current.delete(id);
    };
  }, [rocket.id, meshRefs, haloRefs, burstRefs]);

  const entityId = (rocket as unknown as { last_entity_id?: string }).last_entity_id;

  return (
    <>
      <mesh
        ref={meshRef}
        frustumCulled={false}
        onClick={(e) => {
          e.stopPropagation();
          onRocketClick?.(rocket);
        }}
        onPointerOver={(e) => {
          e.stopPropagation();
          document.body.style.cursor = "pointer";
          setHover(true);
          onRocketHover?.(rocket.workflow_id);
        }}
        onPointerOut={() => {
          document.body.style.cursor = "default";
          setHover(false);
          onRocketHover?.(null);
        }}
      >
        {/* Rocket body — elongated cylinder along +Y. The parent useFrame
            rotates the whole mesh so +Y aligns with the travel direction. */}
        <cylinderGeometry args={[radius * 0.45, radius * 0.45, radius * 3.6, 14]} />
        <meshBasicMaterial color={rocket.color} />

        {/* Nose cone in WHITE so the direction-of-travel reads at a glance,
            even on a tiny rocket. Smooth (16 segments). */}
        <mesh position={[0, radius * 2.5, 0]}>
          <coneGeometry args={[radius * 0.45, radius * 1.4, 16]} />
          <meshBasicMaterial color="#f8fafc" />
        </mesh>

        {/* Three fins at the base — thin elongated boxes around the lower body. */}
        {[0, 1, 2].map((i) => {
          const a = (i * 2 * Math.PI) / 3;
          return (
            <mesh
              key={i}
              position={[Math.cos(a) * radius * 0.55, -radius * 1.5, Math.sin(a) * radius * 0.55]}
              rotation={[0, -a, 0]}
            >
              <boxGeometry args={[radius * 0.08, radius * 0.9, radius * 0.7]} />
              <meshBasicMaterial color={rocket.color} />
            </mesh>
          );
        })}

        {/* Tiny exhaust glow further BEHIND the rocket so its bloom halo
            reads as a trailing puff, not a blob fused to the body. */}
        <mesh position={[0, -radius * 3.6, 0]}>
          <sphereGeometry args={[radius * 0.22, 10, 10]} />
          <meshBasicMaterial
            color="#fed7aa"
            transparent
            opacity={0.55}
            blending={THREE.AdditiveBlending}
            depthWrite={false}
          />
        </mesh>
      </mesh>
      <mesh ref={haloRef} frustumCulled={false}>
        <sphereGeometry args={[radius * 1.5, 12, 12]} />
        <meshBasicMaterial
          color={rocket.color}
          transparent
          opacity={0.4}
          depthWrite={false}
          blending={THREE.AdditiveBlending}
        />
      </mesh>
      {/* Burst ring — only visible while phase === "burst", controlled by useFrame. */}
      <mesh ref={ringRef} frustumCulled={false} visible={true}>
        <ringGeometry args={[radius * 1.2, radius * 1.6, 24]} />
        <meshBasicMaterial color={rocket.color} transparent opacity={0} depthWrite={false} blending={THREE.AdditiveBlending} />
      </mesh>
      {hover && (
        <Html position={[0, radius * 2.5, 0]} center style={{ pointerEvents: "none" }}>
          <div style={{
            background: "rgba(2,6,23,0.92)", color: "#e2e8f0",
            border: "1px solid rgba(99,102,241,0.4)", borderRadius: 4,
            padding: "3px 8px", fontSize: 10, fontFamily: "ui-sans-serif, system-ui",
            whiteSpace: "nowrap",
          }}>
            <div style={{ color: "#22d3ee", fontWeight: 600 }}>{rocket.workflow_id}</div>
            {rocket.last_label && <div style={{ color: "#94a3b8" }}>{rocket.last_label}</div>}
            {mode === "entities" && entityId && (
              <div style={{ color: "#a78bfa", marginTop: 2 }}>{entityId}</div>
            )}
          </div>
        </Html>
      )}
    </>
  );
}

/** Pick a city to target. Match by tool/skill/persona name when possible,
 *  otherwise fall back to a deterministic hash so motion is always visible. */
function pickCityForFlash(
  flash: CosmicFlash,
  cities: CityMeta[],
  mode: CosmicMode,
): string | null {
  if (!cities.length) return null;
  if (mode === "capabilities") {
    if (flash.type === "persona.thinking" && flash.persona) {
      const found = cities.find(
        (c) => c.kind === "persona" && (c.id === flash.persona || c.label === flash.persona),
      );
      if (found) return found.id;
    }
    const f = flash as unknown as { skill?: string; tool?: string; tool_name?: string };
    const cap = f.skill || f.tool || f.tool_name;
    if (cap) {
      const found = cities.find(
        (c) =>
          c.id === cap ||
          c.label === cap ||
          c.id.endsWith(cap) ||
          cap.startsWith(c.id),
      );
      if (found) return found.id;
    }
  } else {
    if (flash.entity_kind) {
      const found = cities.find(
        (c) => c.kind === "entity_type" && (c.id === flash.entity_kind || c.label === flash.entity_kind),
      );
      if (found) return found.id;
    }
  }
  let hash = 5381;
  const seed = `${flash.type}-${flash.workflow_id ?? ""}-${flash.persona ?? flash.tool_name ?? flash.entity_kind ?? ""}`;
  for (let i = 0; i < seed.length; i++) {
    hash = ((hash << 5) + hash + seed.charCodeAt(i)) | 0;
  }
  const idx = Math.abs(hash) % cities.length;
  return cities[idx].id;
}

import { useEffect, useMemo, useRef, useState } from "react";
import * as THREE from "three";
import { useFrame } from "@react-three/fiber";
import type { CosmicFlash, FunctionMeta, WorkflowMoonData } from "./lib/types";
import { planetPosition } from "./FunctionPlanets";
import { colorForFunction } from "./lib/colors";
import {
  buildWorkflowTypeToFunction,
  resolveFunction,
  workflowTypeFromId,
} from "./lib/workflowFunction";

interface PlanetCompletionsProps {
  flashesRef: React.MutableRefObject<{ buffer: CosmicFlash[]; version: number }>;
  inFlight: WorkflowMoonData[];
  functions: FunctionMeta[];
}

/** completion: a workflow finished. heartbeat: the function's world is
 *  working (routine activity). alarm: the world raised a signal a
 *  workflow must answer (a sensor tripped). */
export type PulseKind = "completion" | "heartbeat" | "alarm";

interface Pulse {
  id: number;
  fn: string;
  kind: PulseKind;
  startedAt: number; // ms
  color: string;
}

const PULSE_STYLE: Record<PulseKind, { durationMs: number; growth: number; opacity: number }> = {
  completion: { durationMs: 1600, growth: 4.0, opacity: 0.95 },
  heartbeat: { durationMs: 1400, growth: 1.3, opacity: 0.3 },
  alarm: { durationMs: 2600, growth: 7.0, opacity: 1.0 },
};
const MAX_PULSES = 24;
/** Calm, not strobing: at most one heartbeat per planet in this window. */
const HEARTBEAT_MIN_GAP_MS = 1800;
const ALARM_COLOR = "#fbbf24";
const ALARM_ECHO_DELAY_MS = 380;

let _pulseCounter = 0;

export function pulseKindForFlash(flash: CosmicFlash): PulseKind | null {
  if (isCompletion(flash.type)) return "completion";
  if (flash.type === "world.activity") {
    return flash.world_type === "sensor.tripped" ? "alarm" : "heartbeat";
  }
  return null;
}

/**
 * Expanding ring on a function planet whenever one of its workflows completes.
 * Cinematic confirmation that work just got done — visible at a glance.
 *
 * Listens to flashesRef (no React state for ingestion) and renders one ring
 * per live pulse. We keep the live list in state so React can mount/unmount
 * meshes; ring positions/scales/opacity animate in useFrame on the shared ref.
 */
export function PlanetCompletions({
  flashesRef,
  inFlight,
  functions,
}: PlanetCompletionsProps) {
  const [pulses, setPulses] = useState<Pulse[]>([]);
  const lastVersion = useRef(0);
  const lastHeartbeat = useRef<Map<string, number>>(new Map());
  const planetKeys = useMemo(
    () => new Set(functions.map((f) => f.name ?? f.key ?? "").filter(Boolean)),
    [functions],
  );
  const planetKeysRef = useRef(planetKeys);
  planetKeysRef.current = planetKeys;

  // Keep an in-memory map workflow_id → fn so completion events can resolve
  // the right planet even after the workflow has been removed from inFlight.
  const wfFnCache = useRef<Map<string, string>>(new Map());
  const wfTypeMap = useMemo(() => buildWorkflowTypeToFunction(functions), [functions]);

  useEffect(() => {
    for (const wf of inFlight) {
      const wfType = wf.workflow_type || workflowTypeFromId(wf.id) || "";
      const fn = resolveFunction({ ...wf, workflow_type: wfType }, wfTypeMap);
      wfFnCache.current.set(wf.id, fn);
    }
    if (wfFnCache.current.size > 4000) {
      const arr = Array.from(wfFnCache.current.entries());
      wfFnCache.current = new Map(arr.slice(-2000));
    }
  }, [inFlight, wfTypeMap]);

  // Drain new completions and prune stale ones.
  useEffect(() => {
    const interval = setInterval(() => {
      const now = performance.now();
      const ref = flashesRef.current;

      // Pull only NEW completion flashes — slice the last (ref.version - lastVersion)
      // entries since each push bumps version by exactly 1.
      let added: Pulse[] = [];
      if (ref.version !== lastVersion.current) {
        const delta = Math.max(0, ref.version - lastVersion.current);
        const newSlice = ref.buffer.slice(Math.max(0, ref.buffer.length - delta));
        lastVersion.current = ref.version;
        for (const f of newSlice) {
          const kind = pulseKindForFlash(f);
          if (!kind) continue;
          if (kind !== "completion") {
            // World pulses land only on a planet that exists; never on the hub.
            const fn = f.function;
            if (!fn || !planetKeysRef.current.has(fn)) continue;
            if (kind === "heartbeat") {
              if (now - (lastHeartbeat.current.get(fn) ?? 0) < HEARTBEAT_MIN_GAP_MS) continue;
              lastHeartbeat.current.set(fn, now);
              _pulseCounter += 1;
              added.push({ id: _pulseCounter, fn, kind, startedAt: now, color: colorForFunction(fn) });
            } else {
              for (const delay of [0, ALARM_ECHO_DELAY_MS]) {
                _pulseCounter += 1;
                added.push({ id: _pulseCounter, fn, kind, startedAt: now + delay, color: ALARM_COLOR });
              }
            }
            continue;
          }
          const wid = f.workflow_id;
          if (!wid) continue;
          const fn =
            wfFnCache.current.get(wid) ||
            (f.function && f.function !== "legacy" ? f.function : undefined);
          if (!fn) continue;
          _pulseCounter += 1;
          added.push({
            id: _pulseCounter,
            fn,
            kind,
            startedAt: now,
            color: colorForFunction(fn),
          });
        }
      }

      setPulses((prev) => {
        const live = prev.filter((p) => now - p.startedAt < PULSE_STYLE[p.kind].durationMs);
        const next = [...live, ...added];
        if (next.length > MAX_PULSES) {
          next.splice(0, next.length - MAX_PULSES);
        }
        if (next.length === prev.length && added.length === 0) {
          // No structural change — keep prev to avoid re-renders.
          return prev;
        }
        return next;
      });
    }, 120);
    return () => clearInterval(interval);
  }, [flashesRef]);

  return (
    <group>
      {pulses.map((p) => (
        <PulseRing key={p.id} pulse={p} functions={functions} />
      ))}
    </group>
  );
}

function PulseRing({
  pulse,
  functions,
}: {
  pulse: Pulse;
  functions: FunctionMeta[];
}) {
  const meshRef = useRef<THREE.Mesh>(null);
  const matRef = useRef<THREE.MeshBasicMaterial>(null);

  useFrame((state) => {
    const mesh = meshRef.current;
    const mat = matRef.current;
    if (!mesh || !mat) return;
    const now = performance.now();
    const style = PULSE_STYLE[pulse.kind];
    const age = (now - pulse.startedAt) / style.durationMs; // 0..1
    if (age < 0 || age >= 1) {
      mat.opacity = 0;
      return;
    }
    const t = state.clock.getElapsedTime();
    const planet = planetPosition(pulse.fn, functions, t);
    const r = 0.55 + age * style.growth;
    mesh.position.set(planet[0], planet[1], planet[2]);
    mesh.scale.set(r, r, r);
    // Billboard so the ring always faces the camera as a full circle —
    // a flat horizontal torus is mostly edge-on at our oblique camera angle.
    mesh.lookAt(state.camera.position);
    mat.opacity = style.opacity * (1 - age) ** 1.2;
  });

  return (
    <mesh ref={meshRef}>
      <torusGeometry args={[1, 0.06, 8, 56]} />
      <meshBasicMaterial
        ref={matRef}
        color={pulse.color}
        transparent
        opacity={0}
        depthWrite={false}
        blending={THREE.AdditiveBlending}
      />
    </mesh>
  );
}

function isCompletion(t: string): boolean {
  return (
    t === "workflow.completed" ||
    t === "durable.workflow.completed" ||
    t === "workflow.resolved"
  );
}

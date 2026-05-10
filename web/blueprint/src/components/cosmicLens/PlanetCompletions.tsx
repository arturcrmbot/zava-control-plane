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

interface Pulse {
  id: number;
  fn: string;
  startedAt: number; // ms
  color: string;
}

const PULSE_DURATION_MS = 1600;
const MAX_PULSES = 24;

let _pulseCounter = 0;

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
          if (!isCompletion(f.type)) continue;
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
            startedAt: now,
            color: colorForFunction(fn),
          });
        }
      }

      setPulses((prev) => {
        const live = prev.filter((p) => now - p.startedAt < PULSE_DURATION_MS);
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
    const age = (now - pulse.startedAt) / PULSE_DURATION_MS; // 0..1
    if (age >= 1) {
      mat.opacity = 0;
      return;
    }
    const t = state.clock.getElapsedTime();
    const planet = planetPosition(pulse.fn, functions, t);
    const r = 0.55 + age * 4.0; // expand 0.55 → 4.55
    mesh.position.set(planet[0], planet[1], planet[2]);
    mesh.scale.set(r, r, r);
    // Billboard so the ring always faces the camera as a full circle —
    // a flat horizontal torus is mostly edge-on at our oblique camera angle.
    mesh.lookAt(state.camera.position);
    mat.opacity = 0.95 * (1 - age) ** 1.2;
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

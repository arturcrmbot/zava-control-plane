import { useMemo, useRef } from "react";
import * as THREE from "three";
import { useFrame } from "@react-three/fiber";
import type { FunctionMeta, WorkflowMoonData } from "./lib/types";
import { MoonRegistry } from "./lib/registries";
import { planetPosition } from "./FunctionPlanets";

interface WorkflowMoonsProps {
  inFlight: WorkflowMoonData[];
  functions: FunctionMeta[];
}

const MOON_RADIUS = 0.16;
const MOON_ORBIT_RADIUS = 1.6;
const MAX_MOONS = 600;

const matrix = new THREE.Matrix4();
const position = new THREE.Vector3();
const scale = new THREE.Vector3(1, 1, 1);
const quaternion = new THREE.Quaternion();

/**
 * One small orbiting moon per in-flight workflow.
 * Position = parent planet's position + per-moon rotational offset.
 * Implemented with InstancedMesh for cheap rendering at 200+ moons.
 */
export function WorkflowMoons({ inFlight, functions }: WorkflowMoonsProps) {
  const meshRef = useRef<THREE.InstancedMesh>(null);
  const registry = useMemo(() => new MoonRegistry(), []);

  // Map workflow_id → workflow_type prefix → function lookup. Existing
  // PREFIX_TO_WORKFLOW_TYPE maps in the codebase use prefixes like
  // VKY → vendor-kyc. Phase B adds proper mapping; Phase A just uses
  // workflow.function field if backend provides it.
  const moons = useMemo(() => {
    return inFlight.slice(0, MAX_MOONS).map((wf) => ({
      id: wf.id,
      // Try multiple keys: explicit `function` field first, else workflow_type, else
      // unknown.
      fn: wf.function ?? wf.workflow_type ?? "unknown",
      // Cache offset
      offset: registry.offsetFor(wf.id),
    }));
  }, [inFlight, registry]);

  useFrame((state) => {
    if (!meshRef.current) return;
    const t = state.clock.getElapsedTime();
    const mesh = meshRef.current;
    moons.forEach((moon, i) => {
      const planet = planetPosition(moon.fn, functions, t);
      // Per-moon orbit around the planet
      const moonAngle = t * 0.6 + moon.offset * Math.PI * 2;
      const px = planet[0] + Math.cos(moonAngle) * MOON_ORBIT_RADIUS;
      const pz = planet[2] + Math.sin(moonAngle) * MOON_ORBIT_RADIUS;
      const py = planet[1] + Math.sin(moonAngle * 0.5) * 0.25;
      position.set(px, py, pz);
      matrix.compose(position, quaternion, scale);
      mesh.setMatrixAt(i, matrix);
    });
    // Park unused instances at y=-100
    for (let i = moons.length; i < MAX_MOONS; i++) {
      position.set(0, -100, 0);
      matrix.compose(position, quaternion, scale);
      mesh.setMatrixAt(i, matrix);
    }
    mesh.instanceMatrix.needsUpdate = true;
    mesh.count = MAX_MOONS;
  });

  return (
    <instancedMesh ref={meshRef} args={[undefined, undefined, MAX_MOONS]} castShadow>
      <sphereGeometry args={[MOON_RADIUS, 12, 12]} />
      <meshStandardMaterial
        color="#e2e8f0"
        emissive="#94a3b8"
        emissiveIntensity={0.6}
        metalness={0.1}
        roughness={0.4}
      />
    </instancedMesh>
  );
}

/** Resolve a moon's world position. Used by Rockets to know where rockets launch from. */
export function moonPosition(
  workflowId: string,
  fn: string | undefined,
  functions: FunctionMeta[],
  time: number,
  registry: MoonRegistry,
): [number, number, number] {
  const planet = planetPosition(fn, functions, time);
  const offset = registry.offsetFor(workflowId);
  const moonAngle = time * 0.6 + offset * Math.PI * 2;
  return [
    planet[0] + Math.cos(moonAngle) * MOON_ORBIT_RADIUS,
    planet[1] + Math.sin(moonAngle * 0.5) * 0.25,
    planet[2] + Math.sin(moonAngle) * MOON_ORBIT_RADIUS,
  ];
}

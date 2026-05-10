import { useMemo, useRef } from "react";
import * as THREE from "three";
import { useFrame } from "@react-three/fiber";
import type { FunctionMeta, WorkflowMoonData } from "./lib/types";
import { MoonRegistry } from "./lib/registries";
import { planetPosition } from "./FunctionPlanets";
import { buildWorkflowTypeToFunction, resolveFunction, workflowTypeFromId } from "./lib/workflowFunction";

interface WorkflowMoonsProps {
  inFlight: WorkflowMoonData[];
  functions: FunctionMeta[];
  onMoonClick?: (workflowId: string) => void;
}

const MOON_RADIUS = 0.22;
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
export function WorkflowMoons({ inFlight, functions, onMoonClick }: WorkflowMoonsProps) {
  const meshRef = useRef<THREE.InstancedMesh>(null);
  const registry = useMemo(() => new MoonRegistry(), []);

  // Resolve each workflow to its owning function via the ownsDomains map
  // (workflow.function may be "legacy" for older durable functions).
  const moons = useMemo(() => {
    const wfTypeMap = buildWorkflowTypeToFunction(functions);
    return inFlight.slice(0, MAX_MOONS).map((wf) => {
      const wfType = wf.workflow_type || workflowTypeFromId(wf.id) || "";
      const wfWithType = { ...wf, workflow_type: wfType } as WorkflowMoonData;
      return {
        id: wf.id,
        fn: resolveFunction(wfWithType, wfTypeMap),
        offset: registry.offsetFor(wf.id),
      };
    });
  }, [inFlight, functions, registry]);

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
    <instancedMesh
      ref={meshRef}
      args={[undefined, undefined, MAX_MOONS]}
      castShadow
      onClick={(e) => {
        if (typeof e.instanceId === "number" && e.instanceId < moons.length) {
          e.stopPropagation();
          onMoonClick?.(moons[e.instanceId].id);
        }
      }}
      onPointerOver={(e) => {
        if (typeof e.instanceId === "number" && e.instanceId < moons.length) {
          e.stopPropagation();
          document.body.style.cursor = "pointer";
        }
      }}
      onPointerOut={() => {
        document.body.style.cursor = "default";
      }}
    >
      <sphereGeometry args={[MOON_RADIUS, 12, 12]} />
      <meshStandardMaterial
        color="#f1f5f9"
        emissive="#cbd5e1"
        emissiveIntensity={1.1}
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

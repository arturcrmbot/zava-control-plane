import { useRef } from "react";
import * as THREE from "three";
import { useFrame } from "@react-three/fiber";
import type { FunctionMeta } from "./lib/types";
import { colorForFunction } from "./lib/colors";

interface FunctionPlanetsProps {
  functions: FunctionMeta[];
}

const ORBIT_RADIUS = 14;
const PLANET_RADIUS = 0.7;

/**
 * One sphere per function, positioned in even orbital slots around the hub.
 * Slow rotation around Y so the system feels alive even when no events fire.
 */
export function FunctionPlanets({ functions }: FunctionPlanetsProps) {
  const groupRef = useRef<THREE.Group>(null);

  useFrame((state) => {
    if (!groupRef.current) return;
    // Very slow precession of the entire planet ring so the eye sees motion.
    groupRef.current.rotation.y = state.clock.getElapsedTime() * 0.02;
  });

  if (!functions.length) return null;

  return (
    <group ref={groupRef}>
      {functions.map((fn, i) => {
        const angle = (i * 2 * Math.PI) / functions.length;
        const x = Math.cos(angle) * ORBIT_RADIUS;
        const z = Math.sin(angle) * ORBIT_RADIUS;
        const color = colorForFunction(fn.key);
        return (
          <group key={fn.key} position={[x, 1.5, z]}>
            <mesh castShadow>
              <sphereGeometry args={[PLANET_RADIUS, 24, 24]} />
              <meshStandardMaterial
                color={color}
                emissive={color}
                emissiveIntensity={0.55}
                metalness={0.2}
                roughness={0.6}
              />
            </mesh>
            {/* Soft halo */}
            <mesh>
              <sphereGeometry args={[PLANET_RADIUS * 1.4, 16, 16]} />
              <meshBasicMaterial color={color} transparent opacity={0.08} />
            </mesh>
          </group>
        );
      })}
    </group>
  );
}

/** Resolve a function planet's world position. Used by moons + rockets. */
export function planetPosition(
  fn: string | undefined,
  functions: FunctionMeta[],
  /** Pass world-time so moons see the same precession. */
  time: number,
): [number, number, number] {
  if (!functions.length || !fn) return [0, 1.5, 0];
  const idx = functions.findIndex((f) => f.key === fn);
  if (idx < 0) return [0, 1.5, 0];
  const baseAngle = (idx * 2 * Math.PI) / functions.length;
  const precession = time * 0.02;
  const angle = baseAngle + precession;
  return [Math.cos(angle) * ORBIT_RADIUS, 1.5, Math.sin(angle) * ORBIT_RADIUS];
}

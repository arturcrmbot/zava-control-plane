import { useRef } from "react";
import * as THREE from "three";
import { useFrame } from "@react-three/fiber";
import { Html } from "@react-three/drei";
import type { FunctionMeta } from "./lib/types";
import { colorForFunction } from "./lib/colors";

interface FunctionPlanetsProps {
  functions: FunctionMeta[];
  /** workflow_id-prefix → function key counts (for sizing planets by load). */
  loadByFunction?: Map<string, number>;
  onFunctionClick?: (key: string, label: string) => void;
}

const ORBIT_RADIUS = 14;
const PLANET_RADIUS = 0.7;

/** Backend functions endpoint uses `name`. Some surfaces use `key`. */
function fnKey(fn: FunctionMeta): string {
  return fn.name ?? fn.key ?? "";
}

/**
 * One sphere per function, positioned in even orbital slots around the hub.
 * Slow rotation around Y so the system feels alive even when no events fire.
 */
export function FunctionPlanets({ functions, loadByFunction, onFunctionClick }: FunctionPlanetsProps) {
  const groupRef = useRef<THREE.Group>(null);

  useFrame((state) => {
    if (!groupRef.current) return;
    // Very slow precession of the entire planet ring so the eye sees motion.
    groupRef.current.rotation.y = state.clock.getElapsedTime() * 0.02;
  });

  const visible = functions.filter((f) => fnKey(f));
  if (!visible.length) return null;

  return (
    <group ref={groupRef}>
      {visible.map((fn, i) => {
        const k = fnKey(fn);
        const angle = (i * 2 * Math.PI) / visible.length;
        const x = Math.cos(angle) * ORBIT_RADIUS;
        const z = Math.sin(angle) * ORBIT_RADIUS;
        const color = colorForFunction(k);
        const load = loadByFunction?.get(k) ?? 0;
        // Brighter halo when busy
        const haloOpacity = 0.08 + Math.min(0.25, load / 50);
        const labelText = (fn.display ?? fn.label ?? k).toUpperCase();
        return (
          <group key={k} position={[x, 1.5, z]}>
            <mesh
              castShadow
              onClick={(e) => {
                e.stopPropagation();
                onFunctionClick?.(k, fn.display ?? fn.label ?? k);
              }}
              onPointerOver={(e) => {
                e.stopPropagation();
                document.body.style.cursor = "pointer";
              }}
              onPointerOut={() => {
                document.body.style.cursor = "default";
              }}
            >
              <sphereGeometry args={[PLANET_RADIUS, 24, 24]} />
              <meshStandardMaterial
                color={color}
                emissive={color}
                emissiveIntensity={0.6 + Math.min(0.8, load / 80)}
                metalness={0.2}
                roughness={0.6}
              />
            </mesh>
            {/* Soft halo */}
            <mesh>
              <sphereGeometry args={[PLANET_RADIUS * 1.5, 16, 16]} />
              <meshBasicMaterial color={color} transparent opacity={haloOpacity} />
            </mesh>
            {/* Orbital guide ring — subtle hint of where moons orbit */}
            <mesh rotation={[Math.PI / 2, 0, 0]}>
              <ringGeometry args={[1.55, 1.65, 64]} />
              <meshBasicMaterial color={color} transparent opacity={0.12} side={2} />
            </mesh>
            {/* Function name label */}
            <Html
              position={[0, PLANET_RADIUS + 0.6, 0]}
              center
              style={{
                pointerEvents: "none",
                color: color,
                fontSize: 9,
                fontFamily: "ui-sans-serif, system-ui",
                fontWeight: 700,
                letterSpacing: 1.2,
                textShadow: "0 0 6px rgba(0,0,0,0.9)",
                whiteSpace: "nowrap",
                opacity: 0.9,
              }}
            >
              {labelText}
              {load > 0 && (
                <span style={{ color: "#94a3b8", fontWeight: 400, marginLeft: 6 }}>
                  · {load}
                </span>
              )}
            </Html>
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
  const visible = functions.filter((f) => fnKey(f));
  const idx = visible.findIndex((f) => fnKey(f) === fn);
  if (idx < 0) return [0, 1.5, 0];
  const baseAngle = (idx * 2 * Math.PI) / visible.length;
  const precession = time * 0.02;
  const angle = baseAngle + precession;
  return [Math.cos(angle) * ORBIT_RADIUS, 1.5, Math.sin(angle) * ORBIT_RADIUS];
}

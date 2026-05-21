/**
 * LessonSatellites + DreamPulse — viz pieces that hang off a function
 * planet to show its dream-pass state.
 *
 * - LessonSatellites: a small orbital ring of glowing dots, one per
 *   distilled lesson (capped at MAX_SAT). Each dot orbits the planet
 *   at a slightly different radius and speed for visual life.
 *
 * - WorkingMemoryParticles: faint inflowing dots when the planet's
 *   `dreaming` flag is true — visualises raw working memories being
 *   pulled into consolidation.
 *
 * - DreamPulse: a single bright halo that scales-pulses while the
 *   planet is dreaming and fades on stop.
 *
 * All three are self-contained — they read no global state. The parent
 * (FunctionPlanets) feeds them via props.
 */
import { useMemo, useRef } from "react";
import { useFrame } from "@react-three/fiber";
import * as THREE from "three";

const MAX_SAT = 8;

interface LessonSatellitesProps {
  count: number;
  color: string;
  /** Outer radius hint — satellites orbit just outside the planet body. */
  radius?: number;
}

export function LessonSatellites({ count, color, radius = 1.05 }: LessonSatellitesProps) {
  const visible = Math.min(MAX_SAT, Math.max(0, count));
  const refs = useRef<(THREE.Mesh | null)[]>([]);

  // Stable per-satellite orbit params (radius offset, speed, phase, tilt).
  const params = useMemo(() => {
    return Array.from({ length: MAX_SAT }, (_, i) => {
      const seed = (i * 9301 + 49297) % 233280;
      const u = seed / 233280;
      return {
        r: radius + 0.18 + (i % 3) * 0.12, // 1.23 .. 1.47
        speed: 0.5 + u * 0.7, // 0.5 .. 1.2 rad/s
        phase: (i / MAX_SAT) * Math.PI * 2,
        tilt: 0.2 + (u - 0.5) * 0.6,
      };
    });
  }, [radius]);

  useFrame(({ clock }) => {
    const t = clock.getElapsedTime();
    for (let i = 0; i < visible; i++) {
      const m = refs.current[i];
      if (!m) continue;
      const p = params[i];
      const a = p.phase + t * p.speed;
      m.position.x = Math.cos(a) * p.r;
      m.position.y = Math.sin(a) * Math.sin(p.tilt) * p.r;
      m.position.z = Math.sin(a) * Math.cos(p.tilt) * p.r;
    }
  });

  if (visible === 0) return null;
  return (
    <group>
      {Array.from({ length: visible }, (_, i) => (
        <mesh
          key={i}
          ref={(m) => {
            refs.current[i] = m;
          }}
        >
          <sphereGeometry args={[0.05, 12, 12]} />
          <meshBasicMaterial color={color} toneMapped={false} />
        </mesh>
      ))}
      {count > MAX_SAT && (
        <mesh position={[0, radius + 0.6, 0]}>
          <sphereGeometry args={[0.08, 12, 12]} />
          <meshBasicMaterial color={color} toneMapped={false} />
        </mesh>
      )}
    </group>
  );
}

interface DreamPulseProps {
  active: boolean;
  color: string;
  radius?: number;
}

/** A halo sphere whose scale + opacity pulses while `active`. */
export function DreamPulse({ active, color, radius = 1.0 }: DreamPulseProps) {
  const ref = useRef<THREE.Mesh>(null);
  const matRef = useRef<THREE.MeshBasicMaterial>(null);
  const target = useRef(0); // 0..1
  useFrame((_, dt) => {
    target.current = active ? 1 : Math.max(0, target.current - dt * 1.8);
    if (!ref.current || !matRef.current) return;
    // Pulse: sine envelope on top of target intensity.
    const tNow = performance.now() / 1000;
    const pulse = active ? 0.6 + 0.4 * Math.sin(tNow * 4) : 0;
    const intensity = target.current * pulse;
    const scale = 1.6 + intensity * 0.8;
    ref.current.scale.setScalar(scale * radius);
    matRef.current.opacity = 0.18 * intensity;
  });
  return (
    <mesh ref={ref}>
      <sphereGeometry args={[1, 24, 24]} />
      <meshBasicMaterial
        ref={matRef}
        color={color}
        transparent
        opacity={0}
        depthWrite={false}
      />
    </mesh>
  );
}

interface WorkingMemoryParticlesProps {
  active: boolean;
  count: number;
  color: string;
  radius?: number;
}

/** Small dots streaming from the orbit ring into the planet body
 *  while `active`. Each dot spawns at outer radius, eased in to the
 *  surface, then respawns. */
export function WorkingMemoryParticles({
  active,
  count,
  color,
  radius = 1.0,
}: WorkingMemoryParticlesProps) {
  const N = Math.min(12, Math.max(0, count));
  const refs = useRef<(THREE.Mesh | null)[]>([]);
  const seeds = useMemo(
    () =>
      Array.from({ length: 12 }, (_, i) => ({
        phase: (i / 12) * Math.PI * 2,
        speed: 0.6 + (i % 4) * 0.2,
        tilt: 0.3 + ((i * 7) % 5) * 0.1,
      })),
    [],
  );

  useFrame(({ clock }) => {
    const t = clock.getElapsedTime();
    for (let i = 0; i < N; i++) {
      const m = refs.current[i];
      if (!m) continue;
      const s = seeds[i];
      // Inflow loop: each particle goes from r=2.0 → 0.0 over `period` s.
      const period = 1.8;
      const phase = ((t * s.speed + i * 0.25) % period) / period;
      const r = 2.0 * (1 - phase) * radius;
      const a = s.phase + t * 0.5;
      m.position.x = Math.cos(a) * r;
      m.position.y = Math.sin(a) * Math.sin(s.tilt) * r;
      m.position.z = Math.sin(a) * Math.cos(s.tilt) * r;
      m.visible = active && phase < 0.95;
    }
  });

  if (!active || N === 0) return null;

  return (
    <group>
      {Array.from({ length: N }, (_, i) => (
        <mesh
          key={i}
          ref={(m) => {
            refs.current[i] = m;
          }}
        >
          <sphereGeometry args={[0.035, 8, 8]} />
          <meshBasicMaterial color={color} toneMapped={false} />
        </mesh>
      ))}
    </group>
  );
}

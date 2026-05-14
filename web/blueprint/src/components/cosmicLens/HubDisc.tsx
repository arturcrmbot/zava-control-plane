import { useRef } from "react";
import * as THREE from "three";
import { useFrame } from "@react-three/fiber";

interface HubDiscProps {
  radius?: number;
  thickness?: number;
  /** When the most recent `fleet.tick` arrived (Date.now() ms). The disc
   *  emits a soft 0.8s decay flash after each tick — the substrate's
   *  always-on heartbeat. 0 disables. */
  lastFleetTickAt?: number;
}

/**
 * The central gently-domed disc (mission-control core).
 * - Top is a faint dome so cities feel "on a surface"
 * - Bottom is flat
 * - Slowly emissive pulse on the disc edge so the eye stays anchored
 */
export function HubDisc({ radius = 8, thickness = 0.5, lastFleetTickAt = 0 }: HubDiscProps) {
  const ringRef = useRef<THREE.Mesh>(null);
  const pulseRef = useRef<THREE.Mesh>(null);

  useFrame((state) => {
    if (ringRef.current) {
      const m = ringRef.current.material as THREE.MeshStandardMaterial;
      const t = state.clock.getElapsedTime();
      m.emissiveIntensity = 0.4 + 0.15 * Math.sin(t * 0.6);
    }
    if (pulseRef.current && lastFleetTickAt > 0) {
      const m = pulseRef.current.material as THREE.MeshBasicMaterial;
      const age = (Date.now() - lastFleetTickAt) / 800; // 0.8s decay
      m.opacity = age < 1 ? 0.6 * Math.max(0, 1 - age) : 0;
    }
  });

  return (
    <group>
      {/* Main disc */}
      <mesh receiveShadow>
        <cylinderGeometry args={[radius, radius, thickness, 96]} />
        <meshStandardMaterial
          color="#0f1729"
          metalness={0.6}
          roughness={0.35}
          emissive="#1e293b"
          emissiveIntensity={0.45}
        />
      </mesh>

      {/* Bright emissive edge ring */}
      <mesh ref={ringRef} position={[0, thickness * 0.5 + 0.02, 0]} rotation={[Math.PI / 2, 0, 0]}>
        <torusGeometry args={[radius * 0.99, 0.06, 16, 96]} />
        <meshStandardMaterial
          color="#22d3ee"
          emissive="#22d3ee"
          emissiveIntensity={0.5}
          transparent
          opacity={0.85}
        />
      </mesh>

      {/* B1: fleet.tick heartbeat ring — flashes briefly each tick. */}
      <mesh ref={pulseRef} position={[0, thickness * 0.5 + 0.04, 0]} rotation={[Math.PI / 2, 0, 0]}>
        <torusGeometry args={[radius * 1.05, 0.12, 16, 96]} />
        <meshBasicMaterial color="#67e8f9" transparent opacity={0} />
      </mesh>

      {/* Soft glow puff under the disc */}
      <mesh position={[0, -thickness * 0.7, 0]} rotation={[-Math.PI / 2, 0, 0]}>
        <ringGeometry args={[radius * 0.4, radius * 1.5, 64]} />
        <meshBasicMaterial color="#0ea5e9" transparent opacity={0.06} />
      </mesh>
    </group>
  );
}

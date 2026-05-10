import { useRef } from "react";
import * as THREE from "three";
import { useFrame } from "@react-three/fiber";

interface HubDiscProps {
  radius?: number;
  thickness?: number;
}

/**
 * The central gently-domed disc (mission-control core).
 * - Top is a faint dome so cities feel "on a surface"
 * - Bottom is flat
 * - Slowly emissive pulse on the disc edge so the eye stays anchored
 */
export function HubDisc({ radius = 8, thickness = 0.5 }: HubDiscProps) {
  const ringRef = useRef<THREE.Mesh>(null);

  useFrame((state) => {
    if (!ringRef.current) return;
    const m = ringRef.current.material as THREE.MeshStandardMaterial;
    const t = state.clock.getElapsedTime();
    m.emissiveIntensity = 0.4 + 0.15 * Math.sin(t * 0.6);
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

      {/* Dome cap on top */}
      <mesh position={[0, thickness * 0.5, 0]}>
        <sphereGeometry
          args={[radius * 1.005, 96, 48, 0, Math.PI * 2, 0, Math.PI / 2.6]}
        />
        <meshStandardMaterial
          color="#1e293b"
          metalness={0.4}
          roughness={0.55}
          emissive="#0f172a"
          emissiveIntensity={0.4}
          transparent
          opacity={0.85}
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

      {/* Soft glow puff under the disc */}
      <mesh position={[0, -thickness * 0.7, 0]} rotation={[-Math.PI / 2, 0, 0]}>
        <ringGeometry args={[radius * 0.4, radius * 1.5, 64]} />
        <meshBasicMaterial color="#0ea5e9" transparent opacity={0.06} />
      </mesh>
    </group>
  );
}

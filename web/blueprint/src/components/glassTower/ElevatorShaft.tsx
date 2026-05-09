/**
 * ElevatorShaft — a glowing column running up the back of the building.
 *
 * Workflows visibly travel UP this shaft from the lobby to their floor.
 * The shaft itself is a thin emissive column; brightness pulses with
 * recent traffic.
 */
import { useFrame } from "@react-three/fiber";
import { useRef } from "react";
import * as THREE from "three";

import type { FlashSet } from "../../lib/useLiveOrg";

const TOP_Y = 14.0;
const BACK_Z = -2.2;

interface Props {
  flashesRef: React.MutableRefObject<FlashSet>;
}

export function ElevatorShaft({ flashesRef }: Props) {
  const shaftRef = useRef<THREE.Mesh>(null);

  useFrame(() => {
    const m = shaftRef.current?.material as THREE.MeshStandardMaterial | undefined;
    if (!m) return;
    // Brightness ramps with recent workflow traffic — count workflowFlash
    // entries with kind="started" still alive.
    const now = performance.now();
    let recent = 0;
    flashesRef.current.workflowFlash.forEach((f) => {
      if (f.until > now && f.kind === "started") recent++;
    });
    const target = 0.4 + Math.min(0.6, recent * 0.12);
    m.emissiveIntensity += (target - m.emissiveIntensity) * 0.1;
  });

  return (
    <group>
      {/* Glowing central column. */}
      <mesh ref={shaftRef} position={[0, TOP_Y / 2, BACK_Z]}>
        <cylinderGeometry args={[0.08, 0.08, TOP_Y, 16]} />
        <meshStandardMaterial color="#1a1d28" emissive="#06b6d4" emissiveIntensity={0.5} toneMapped={false} />
      </mesh>
      {/* Thin halo around the shaft. */}
      <mesh position={[0, TOP_Y / 2, BACK_Z]}>
        <cylinderGeometry args={[0.13, 0.13, TOP_Y, 16, 1, true]} />
        <meshBasicMaterial color="#06b6d4" transparent opacity={0.18} side={THREE.DoubleSide} toneMapped={false} />
      </mesh>
    </group>
  );
}

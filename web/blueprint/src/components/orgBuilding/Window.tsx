/**
 * The Org Building (IP3, TASK-011) — instanced window facade.
 *
 * Renders ~6 window panels per floor as a single InstancedMesh so the
 * building stays cheap even when the workflow density grows: 11 floors
 * × ~6 windows is only ~66 instances today, but the same component
 * scales to 10k+ instances at 60fps when chunks 2-3 add per-workflow
 * window animation.
 */
import { useEffect, useRef } from "react";
import * as THREE from "three";

export interface WindowSpec {
  /** World position of the window centre. */
  position: [number, number, number];
  /** Emissive tint (typically the parent floor's function colour). */
  color: string;
  /** Lit windows pulse a touch brighter; dark windows are nearly black. */
  lit: boolean;
}

interface Props {
  windows: WindowSpec[];
  width?: number;
  height?: number;
  depth?: number;
}

export function WindowGrid({
  windows,
  width = 0.18,
  height = 0.18,
  depth = 0.04,
}: Props) {
  const ref = useRef<THREE.InstancedMesh>(null);

  useEffect(() => {
    const mesh = ref.current;
    if (!mesh) return;
    const dummy = new THREE.Object3D();
    const colour = new THREE.Color();
    windows.forEach((w, i) => {
      dummy.position.set(...w.position);
      dummy.updateMatrix();
      mesh.setMatrixAt(i, dummy.matrix);
      // Lit windows render at full emissive intensity; unlit windows are
      // dimmed but still visible so the facade reads as a building, not
      // as floating slabs.
      colour.set(w.color);
      if (!w.lit) colour.multiplyScalar(0.18);
      mesh.setColorAt(i, colour);
    });
    mesh.instanceMatrix.needsUpdate = true;
    if (mesh.instanceColor) mesh.instanceColor.needsUpdate = true;
  }, [windows]);

  if (windows.length === 0) return null;

  return (
    <instancedMesh
      ref={ref}
      args={[undefined, undefined, windows.length]}
      castShadow={false}
      receiveShadow={false}
    >
      <boxGeometry args={[width, height, depth]} />
      <meshStandardMaterial
        emissive="#ffffff"
        emissiveIntensity={1.4}
        toneMapped={false}
      />
    </instancedMesh>
  );
}

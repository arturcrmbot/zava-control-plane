/**
 * SubSpawnArcs — bright magenta arcs that pulse from a parent workflow's
 * floor down/across to a spawned child workflow's floor.
 *
 * Driven by `workflow.sub_spawned` events. Each arc lives ~3.5s, then
 * fades. Visible at any zoom — the meta-workflow story.
 */
import { Line } from "@react-three/drei";
import { useFrame } from "@react-three/fiber";
import { useEffect, useRef, useState } from "react";
import * as THREE from "three";

import type { FlashSet } from "../../lib/useLiveOrg";
import { useObservatory } from "../../lib/useObservatory";

const PREFIX_TO_FN: Record<string, string> = {
  EXP: "finance", HIRE: "hr", TRV: "hr", TRVL: "hr", VKY: "finance", ONB: "hr",
  ITAR: "tech", CRN: "finance", PRR: "hr", API: "finance", POW: "finance",
  CRW: "legal", DPI: "legal", TFX: "finance", CMP: "marketing",
};

function fnFromWid(wid: string | null | undefined): string | null {
  if (!wid) return null;
  const m = wid.match(/^([A-Z]+)-/);
  return m ? PREFIX_TO_FN[m[1]] ?? null : null;
}

interface Arc {
  id: string;
  bornAt: number;
  from: THREE.Vector3;
  to: THREE.Vector3;
  parent: string;
  child: string;
}

const ARC_LIFE_MS = 3500;
const ARC_COLOR = new THREE.Color("#ec4899");

interface Props {
  floorY: Map<string, number>;
  flashesRef: React.MutableRefObject<FlashSet>;
}

export function SubSpawnArcs({ floorY }: Props) {
  const arcsRef = useRef<Arc[]>([]);
  const [, setTick] = useState(0);

  useObservatory({
    bufferSize: 1,
    onEvent: (event) => {
      if (event.type !== "workflow.sub_spawned") return;
      const ev = event as unknown as Record<string, unknown>;
      const parent = (ev.workflow_id as string) ?? (ev.parent_workflow_id as string);
      const child = (ev.child_workflow_id as string) ?? null;
      if (!parent || !child) return;
      const parentFn = fnFromWid(parent);
      const childFn = fnFromWid(child);
      if (!parentFn || !childFn) return;
      const py = floorY.get(parentFn);
      const cy = floorY.get(childFn);
      if (py == null || cy == null) return;
      arcsRef.current.push({
        id: `${parent}-${child}-${Date.now()}`,
        bornAt: performance.now(),
        from: new THREE.Vector3(2.6, py, 0),
        to: new THREE.Vector3(2.6, cy, 0),
        parent,
        child,
      });
      setTick((t) => (t + 1) | 0);
    },
  });

  useFrame(() => {
    const now = performance.now();
    const before = arcsRef.current.length;
    arcsRef.current = arcsRef.current.filter((a) => now - a.bornAt < ARC_LIFE_MS);
    if (arcsRef.current.length !== before) setTick((t) => (t + 1) | 0);
  });

  return (
    <group>
      {arcsRef.current.map((arc) => (
        <SpawnArc key={arc.id} arc={arc} />
      ))}
    </group>
  );
}

function SpawnArc({ arc }: { arc: Arc }) {
  const lineRef = useRef<unknown>(null);
  const headRef = useRef<THREE.Mesh>(null);

  // Build a curved bezier polyline between from and to with an outward bow.
  const points = (() => {
    const out: [number, number, number][] = [];
    const seg = 24;
    const mid = arc.from.clone().lerp(arc.to, 0.5);
    mid.x += 1.8; // bow outward to the right
    for (let i = 0; i <= seg; i++) {
      const t = i / seg;
      const u = 1 - t;
      const x = u * u * arc.from.x + 2 * u * t * mid.x + t * t * arc.to.x;
      const y = u * u * arc.from.y + 2 * u * t * mid.y + t * t * arc.to.y;
      const z = u * u * arc.from.z + 2 * u * t * mid.z + t * t * arc.to.z;
      out.push([x, y, z]);
    }
    return out;
  })();

  useFrame(() => {
    const now = performance.now();
    const t = (now - arc.bornAt) / ARC_LIFE_MS;
    const line = lineRef.current as { material?: { opacity: number } } | null;
    if (line?.material) line.material.opacity = Math.max(0, 1 - t);
    const head = headRef.current;
    if (head && t < 1) {
      const idx = Math.min(points.length - 1, Math.floor(t * points.length));
      const [x, y, z] = points[idx];
      head.position.set(x, y, z);
      const hm = head.material as THREE.MeshBasicMaterial;
      hm.opacity = Math.max(0, 1 - t * 0.6);
    }
  });

  return (
    <group>
      <Line
        ref={lineRef as never}
        points={points}
        color={ARC_COLOR}
        lineWidth={3}
        transparent
        opacity={1}
        toneMapped={false}
      />
      <mesh ref={headRef} position={arc.from.toArray() as [number, number, number]}>
        <sphereGeometry args={[0.09, 12, 12]} />
        <meshBasicMaterial color={ARC_COLOR} transparent opacity={1} toneMapped={false} />
      </mesh>
    </group>
  );
}

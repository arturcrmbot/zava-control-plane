/**
 * DecisionPool — receipts that fly from a desk down to the lobby pool.
 *
 * Reads flashesRef.pendingDecisions (populated by SSE persona.decided
 * events). Each decision flies from the persona's desk → the lobby
 * decision pool, then accumulates as a small glow that decays over
 * 30s.
 */
import { useFrame } from "@react-three/fiber";
import { useRef } from "react";
import * as THREE from "three";

import type { FlashSet } from "../../lib/useLiveOrg";
import { deskPosition, lobbyDecisionPoolPosition } from "./tower-registry";

const FLY_MS = 1400;
const POOL_DECAY_MS = 30000;
const MAX_FLYING = 80;
const MAX_POOL = 60;

interface FlyingState {
  id: string;
  bornAt: number;
  from: THREE.Vector3;
  to: THREE.Vector3;
  color: THREE.Color;
}

interface PoolState {
  id: string;
  bornAt: number;
  position: THREE.Vector3;
  color: THREE.Color;
}

const dummy = new THREE.Object3D();
const tmpColor = new THREE.Color();

const APPROVE_COLOR = new THREE.Color("#5fd49d");
const REJECT_COLOR = new THREE.Color("#e87a5d");
const NEUTRAL_COLOR = new THREE.Color("#a78bfa");

interface Props {
  flashesRef: React.MutableRefObject<FlashSet>;
  floorY: Map<string, number>;
}

export function DecisionPool({ flashesRef, floorY }: Props) {
  const flyingMeshRef = useRef<THREE.InstancedMesh>(null);
  const poolMeshRef = useRef<THREE.InstancedMesh>(null);
  const flyingRef = useRef<Map<string, FlyingState>>(new Map());
  const poolRef = useRef<Map<string, PoolState>>(new Map());

  useFrame(() => {
    const now = performance.now();

    // Drain pendingDecisions queue → spawn flying receipts.
    const queue = flashesRef.current.pendingDecisions;
    while (queue.length > 0 && flyingRef.current.size < MAX_FLYING) {
      const dec = queue.shift()!;
      const fnKey = dec.function ?? "ops";
      const desk = deskPosition(fnKey, dec.persona ?? null);
      const fy = floorY.get(fnKey) ?? 1;
      const from = desk
        ? new THREE.Vector3(desk[0], desk[1] + 0.32, desk[2])
        : new THREE.Vector3(0, fy, 0);
      const pool = lobbyDecisionPoolPosition();
      const to = new THREE.Vector3(
        pool[0] + (Math.random() - 0.5) * 1.6,
        pool[1] + 0.05 + Math.random() * 0.18,
        pool[2] + (Math.random() - 0.5) * 1.0,
      );
      const color =
        dec.verdict === "approve" || dec.verdict === "approved"
          ? APPROVE_COLOR
          : dec.verdict === "reject" || dec.verdict === "rejected" || dec.verdict === "deny"
          ? REJECT_COLOR
          : NEUTRAL_COLOR;
      flyingRef.current.set(dec.id, {
        id: dec.id,
        bornAt: now,
        from,
        to,
        color,
      });
    }

    // Advance flying receipts → land in pool when done.
    flyingRef.current.forEach((f, id) => {
      const t = Math.min(1, (now - f.bornAt) / FLY_MS);
      if (t >= 1) {
        // Land in pool.
        flyingRef.current.delete(id);
        // Cap pool size — drop oldest.
        if (poolRef.current.size >= MAX_POOL) {
          const oldest = [...poolRef.current.entries()].reduce<
            [string, PoolState] | null
          >((acc, cur) => (acc == null || cur[1].bornAt < acc[1].bornAt ? cur : acc), null);
          if (oldest) poolRef.current.delete(oldest[0]);
        }
        poolRef.current.set(id, {
          id,
          bornAt: now,
          position: f.to.clone(),
          color: f.color,
        });
      }
    });

    // Decay pool entries.
    poolRef.current.forEach((p, id) => {
      if (now - p.bornAt > POOL_DECAY_MS) poolRef.current.delete(id);
    });

    // Render flying mesh.
    const flyMesh = flyingMeshRef.current;
    if (flyMesh) {
      let i = 0;
      flyingRef.current.forEach((f) => {
        if (i >= MAX_FLYING) return;
        const t = Math.min(1, (now - f.bornAt) / FLY_MS);
        // Bezier mid above — gives the receipt an arc.
        const mid = f.from.clone().lerp(f.to, 0.5);
        mid.y += 1.2;
        const u = 1 - t;
        const x = u * u * f.from.x + 2 * u * t * mid.x + t * t * f.to.x;
        const y = u * u * f.from.y + 2 * u * t * mid.y + t * t * f.to.y;
        const z = u * u * f.from.z + 2 * u * t * mid.z + t * t * f.to.z;
        dummy.position.set(x, y, z);
        // Slight spin while flying.
        dummy.rotation.set(t * Math.PI, t * Math.PI * 1.5, 0);
        dummy.scale.setScalar(0.1);
        dummy.updateMatrix();
        flyMesh.setMatrixAt(i, dummy.matrix);
        tmpColor.copy(f.color);
        flyMesh.setColorAt(i, tmpColor);
        i++;
      });
      for (; i < MAX_FLYING; i++) {
        dummy.position.set(0, -100, 0);
        dummy.scale.setScalar(0);
        dummy.updateMatrix();
        flyMesh.setMatrixAt(i, dummy.matrix);
      }
      flyMesh.instanceMatrix.needsUpdate = true;
      if (flyMesh.instanceColor) flyMesh.instanceColor.needsUpdate = true;
    }

    // Render pool mesh.
    const poolMesh = poolMeshRef.current;
    if (poolMesh) {
      let i = 0;
      poolRef.current.forEach((p) => {
        if (i >= MAX_POOL) return;
        const age = (now - p.bornAt) / POOL_DECAY_MS;
        const opacityScale = 1 - age * 0.7;
        dummy.position.copy(p.position);
        dummy.rotation.set(0, 0, 0);
        dummy.scale.setScalar(0.06 * opacityScale);
        dummy.updateMatrix();
        poolMesh.setMatrixAt(i, dummy.matrix);
        tmpColor.copy(p.color).multiplyScalar(opacityScale);
        poolMesh.setColorAt(i, tmpColor);
        i++;
      });
      for (; i < MAX_POOL; i++) {
        dummy.position.set(0, -100, 0);
        dummy.scale.setScalar(0);
        dummy.updateMatrix();
        poolMesh.setMatrixAt(i, dummy.matrix);
      }
      poolMesh.instanceMatrix.needsUpdate = true;
      if (poolMesh.instanceColor) poolMesh.instanceColor.needsUpdate = true;
    }
  });

  return (
    <>
      <instancedMesh ref={flyingMeshRef} args={[undefined, undefined, MAX_FLYING]}>
        <boxGeometry args={[1, 1, 0.3]} />
        <meshBasicMaterial color="#ffffff" toneMapped={false} />
      </instancedMesh>
      <instancedMesh ref={poolMeshRef} args={[undefined, undefined, MAX_POOL]}>
        <sphereGeometry args={[1, 8, 8]} />
        <meshBasicMaterial color="#ffffff" toneMapped={false} />
      </instancedMesh>
    </>
  );
}

/**
 * WorkflowMotes — glowing cyan motes traveling lobby → desk → lobby.
 *
 * Reads in-flight workflows + tracks each one's age. New workflows
 * animate from the lobby UP to a desk on their function's floor (200ms
 * lift). They sit at the desk pulsing while the workflow is in flight.
 * When the workflow disappears from the in-flight list (completed),
 * the mote slides DOWN to the decision pool and fades.
 */
import { useFrame } from "@react-three/fiber";
import { useMemo, useRef } from "react";
import * as THREE from "three";

import type { FlashSet, InFlightWorkflow } from "../../lib/useLiveOrg";
import {
  deskPositionForWorkflow,
  lobbyDecisionPoolPosition,
  lobbyEntryPosition,
} from "./tower-registry";

interface MoteState {
  id: string;
  fn: string;
  workflowType: string;
  // Animation phases:
  // 0..1 lift from lobby to desk
  // 1..1+stay sit at desk
  // stay..stay+fall fall back to lobby pool
  // > stay+fall: removed
  bornAt: number;
  endsAt: number | null;
  status: InFlightWorkflow["status"];
  awaitingPersona: boolean;
}

const LIFT_MS = 3000;
const FALL_MS = 2500;

interface Props {
  inFlight: InFlightWorkflow[];
  floorY: Map<string, number>;
  flashesRef: React.MutableRefObject<FlashSet>;
}

const MAX_INSTANCES = 200;
const dummy = new THREE.Object3D();
const tmpFrom = new THREE.Vector3();
const tmpTo = new THREE.Vector3();
const tmpPos = new THREE.Vector3();
const tmpColor = new THREE.Color();

const COLOR_RUNNING = new THREE.Color("#06b6d4");
const COLOR_AWAITING = new THREE.Color("#fbbf24");
const COLOR_COMPLETED = new THREE.Color("#5fd49d");

export function WorkflowMotes({ inFlight, floorY, flashesRef }: Props) {
  const meshRef = useRef<THREE.InstancedMesh>(null);
  const motesRef = useRef<Map<string, MoteState>>(new Map());

  // Reconcile in-flight list against active motes. New workflows spawn
  // motes; disappeared workflows mark their motes for fall-out.
  useMemo(() => {
    const now = performance.now();
    const seen = new Set<string>();
    const map = motesRef.current;
    for (const w of inFlight) {
      seen.add(w.id);
      const cur = map.get(w.id);
      if (!cur) {
        map.set(w.id, {
          id: w.id,
          fn: w.function ?? "ops",
          workflowType: w.workflow_type,
          bornAt: now - Math.min(w.age_s * 1000, LIFT_MS),
          endsAt: null,
          status: w.status,
          awaitingPersona: w.status === "awaiting_hitl",
        });
      } else {
        cur.status = w.status;
        cur.awaitingPersona = w.status === "awaiting_hitl";
      }
    }
    // Workflows that disappeared from in-flight → start fall-out.
    for (const [id, mote] of map.entries()) {
      if (!seen.has(id) && mote.endsAt == null) {
        mote.endsAt = now;
      }
      // Already falling for too long? Drop entirely.
      if (mote.endsAt != null && now - mote.endsAt > FALL_MS + 800) {
        map.delete(id);
      }
    }
  }, [inFlight]);

  useFrame(() => {
    const mesh = meshRef.current;
    if (!mesh) return;
    const map = motesRef.current;
    const now = performance.now();

    let i = 0;
    map.forEach((mote) => {
      if (i >= MAX_INSTANCES) return;
      const fn = mote.fn;
      const desk = deskPositionForWorkflow(fn, mote.id);
      const fy = floorY.get(fn) ?? 1;

      const lobbyEntry = lobbyEntryPosition();
      tmpFrom.set(lobbyEntry[0], lobbyEntry[1], lobbyEntry[2]);
      if (desk) tmpTo.set(desk[0], desk[1] + 0.18, desk[2]);
      else tmpTo.set(0, fy, 0);

      let pos: THREE.Vector3;
      let color: THREE.Color = COLOR_RUNNING;
      let scale = 0.06;
      let opacityProxy = 1.0;

      if (mote.endsAt != null) {
        // Falling phase — desk → decision pool. Route through shaft so the
        // motion reads as "back down the elevator and out".
        const t = Math.min(1, (now - mote.endsAt) / FALL_MS);
        const pool = lobbyDecisionPoolPosition();
        const fallFrom = desk
          ? new THREE.Vector3(desk[0], desk[1] + 0.18, desk[2])
          : new THREE.Vector3(0, fy, 0);
        const fallTo = new THREE.Vector3(pool[0], pool[1] + 0.1, pool[2]);
        // Mid waypoint at the elevator shaft (back of building, x=0, z=-2.2).
        const shaftWaypoint = new THREE.Vector3(0, fallFrom.y * 0.55, -2.2);
        if (t < 0.45) {
          // First leg: desk → shaft.
          const u = t / 0.45;
          pos = fallFrom.clone().lerp(shaftWaypoint, u);
        } else {
          // Second leg: shaft → pool.
          const u = (t - 0.45) / 0.55;
          pos = shaftWaypoint.clone().lerp(fallTo, u);
        }
        color = COLOR_COMPLETED;
        scale = 0.05 * (1 - t * 0.5);
        opacityProxy = 1 - t;
      } else {
        // Lift / dwell phase. Workflows enter at the lobby's right side,
        // ride UP the elevator shaft (x=0, z=-2.2), then slide OUT to the
        // floor's desk. Two-leg path so the motion visibly hugs the shaft.
        const elapsed = now - mote.bornAt;
        if (elapsed < LIFT_MS) {
          const t = elapsed / LIFT_MS;
          const easeT = 1 - Math.pow(1 - t, 2);
          // Mid waypoint inside the shaft at desk's height.
          const shaftWaypoint = new THREE.Vector3(0, tmpTo.y, -2.2);
          if (easeT < 0.55) {
            const u = easeT / 0.55;
            pos = tmpFrom.clone().lerp(shaftWaypoint, u);
          } else {
            const u = (easeT - 0.55) / 0.45;
            pos = shaftWaypoint.clone().lerp(tmpTo, u);
          }
          color = COLOR_RUNNING;
          scale = 0.06 + 0.03 * (1 - easeT);
        } else {
          // Sit at desk, gentle bob.
          const bob = 0.04 * Math.sin((now - mote.bornAt) / 280);
          pos = tmpTo.clone();
          pos.y += bob;
          color = mote.awaitingPersona ? COLOR_AWAITING : COLOR_RUNNING;
          scale = mote.awaitingPersona ? 0.085 + 0.02 * Math.sin(now / 200) : 0.07;
        }
      }

      tmpPos.copy(pos);
      dummy.position.copy(tmpPos);
      // Big enough to read against the building. Was 0.06×1.8 → ~10px;
      // bumped further so the cyan/amber pulse jumps out at zoom-3.
      dummy.scale.setScalar(scale * 3.0 * Math.max(0.1, opacityProxy));
      dummy.updateMatrix();
      mesh.setMatrixAt(i, dummy.matrix);
      tmpColor.copy(color);
      tmpColor.multiplyScalar(opacityProxy * 1.6);
      mesh.setColorAt(i, tmpColor);

      i++;
    });

    // Park unused instances out of view.
    for (; i < MAX_INSTANCES; i++) {
      dummy.position.set(0, -100, 0);
      dummy.scale.setScalar(0);
      dummy.updateMatrix();
      mesh.setMatrixAt(i, dummy.matrix);
    }

    mesh.instanceMatrix.needsUpdate = true;
    if (mesh.instanceColor) mesh.instanceColor.needsUpdate = true;
  });

  return (
    <instancedMesh
      ref={meshRef}
      args={[undefined, undefined, MAX_INSTANCES]}
      castShadow={false}
      receiveShadow={false}
    >
      <sphereGeometry args={[1, 14, 14]} />
      <meshBasicMaterial color="#ffffff" toneMapped={false} />
    </instancedMesh>
  );
}

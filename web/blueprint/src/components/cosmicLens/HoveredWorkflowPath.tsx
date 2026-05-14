/**
 * HoveredWorkflowPath — when the user hovers a workflow moon, this
 * component draws the moon → current-rocket connection AND a polyline
 * through every city the workflow has visited so far.
 *
 * This is the "show the workflow as a continuous step, not a one-off
 * thing" requirement. Without it you can see moons and rockets but you
 * can never trace which rocket belongs to which moon, nor where a
 * workflow has been before its current step.
 *
 * Drawn with depthTest=false so the lines render on top of the disc
 * and any other geometry — they're an annotation layer, not part of
 * the scene.
 */

import { useMemo, useRef } from "react";
import * as THREE from "three";
import { useFrame } from "@react-three/fiber";
import { Html } from "@react-three/drei";
import { cityPosition } from "./Cities";
import { moonPosition } from "./lib/moonPosition";
import { resolveFunction, buildWorkflowTypeToFunction, workflowTypeFromId } from "./lib/workflowFunction";
import type { FunctionMeta, WorkflowMoonData } from "./lib/types";
import { MoonRegistry, type RocketRegistry } from "./lib/registries";

interface HoveredWorkflowPathProps {
  workflowId: string | null;
  inFlight: WorkflowMoonData[];
  functions: FunctionMeta[];
  rocketRegistry: RocketRegistry;
}

const HISTORY_COLOR = "#a78bfa"; // violet — past trail
const ACTIVE_COLOR = "#ec4899";  // hot magenta — moon ↔ current rocket

export function HoveredWorkflowPath({
  workflowId,
  inFlight,
  functions,
  rocketRegistry,
}: HoveredWorkflowPathProps) {
  // Fresh local moon registry — moonPosition() only consults its offsetFor()
  // which is deterministic per workflowId (djb2 hash), so a private instance
  // is identical to any other moonPosition caller's.
  const moonRegistry = useMemo(() => new MoonRegistry(), []);
  // Resolve the workflow's owning function (so we can compute the moon
  // orbit position each frame). Memoised on workflow + functions only —
  // re-resolves when hover target changes.
  const fn = useMemo(() => {
    if (!workflowId) return undefined;
    const wf = inFlight.find((w) => w.id === workflowId);
    if (!wf) return undefined;
    const wfTypeMap = buildWorkflowTypeToFunction(functions);
    const wfType = wf.workflow_type || workflowTypeFromId(wf.id) || "";
    return resolveFunction({ ...wf, workflow_type: wfType }, wfTypeMap);
  }, [workflowId, inFlight, functions]);

  // Pre-compute the historical city polyline points. Depends on
  // rocketRegistry.version so that recordVisit() (which now bumps version)
  // triggers a re-memoise and the polyline grows in real time.
  const historyPoints = useMemo(() => {
    if (!workflowId) return [] as THREE.Vector3[];
    const visits = rocketRegistry.historyFor(workflowId);
    return visits.map((v) => {
      const [x, y, z] = cityPosition(v.city_id);
      return new THREE.Vector3(x, y + 0.1, z);
    });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [workflowId, rocketRegistry, rocketRegistry.version]);

  // Current-rocket connection geometry: a tube from moon to the live rocket
  // position. We rebuild geometry every frame because both endpoints move.
  const liveLineRef = useRef<THREE.BufferGeometry>(null);
  const cityRingRef = useRef<THREE.Mesh>(null);
  // Anchor group for the floating label — useRef on Vector3 won't trigger
  // re-render and the <Html> would stay stuck at (0,0,0). Updating the
  // group's position in useFrame moves the Html anchor every frame.
  const labelAnchorRef = useRef<THREE.Group>(null);

  useFrame((state) => {
    if (!workflowId) return;
    const t = state.clock.getElapsedTime();
    const moonPos = moonPosition(workflowId, fn, functions, t, moonRegistry);

    // Find this workflow's most recent live rocket (outbound/parked/returning).
    const liveRocket = rocketRegistry.latestForWorkflow(workflowId);
    let endX = moonPos[0], endY = moonPos[1], endZ = moonPos[2];
    if (liveRocket && liveRocket.current_city_id) {
      const [cx, cy, cz] = cityPosition(liveRocket.current_city_id);
      endX = cx; endY = cy + 0.45; endZ = cz;

      const ring = cityRingRef.current;
      if (ring) {
        ring.position.set(cx, cy + 0.1, cz);
        const pulse = 1 + 0.3 * Math.sin(t * 6);
        ring.scale.set(pulse, pulse, pulse);
        ring.visible = true;
      }
      if (labelAnchorRef.current) {
        labelAnchorRef.current.position.set(
          (moonPos[0] + cx) / 2,
          (moonPos[1] + cy) / 2 + 0.6,
          (moonPos[2] + cz) / 2,
        );
      }
    } else {
      const ring = cityRingRef.current;
      if (ring) ring.visible = false;
      // No live rocket — anchor label at the moon itself so the user still
      // sees which moon they're hovering.
      if (labelAnchorRef.current) {
        labelAnchorRef.current.position.set(moonPos[0], moonPos[1] + 0.6, moonPos[2]);
      }
    }

    // Update the live moon→city line geometry in place.
    const geom = liveLineRef.current;
    if (geom) {
      const arr = new Float32Array([moonPos[0], moonPos[1], moonPos[2], endX, endY, endZ]);
      geom.setAttribute("position", new THREE.BufferAttribute(arr, 3));
      geom.computeBoundingSphere();
    }
  });

  if (!workflowId) return null;

  return (
    <group>
      {/* Historical city polyline — every city the workflow has parked at */}
      {historyPoints.length >= 2 && (
        <line>
          <bufferGeometry>
            <bufferAttribute
              attach="attributes-position"
              args={[new Float32Array(historyPoints.flatMap((p) => [p.x, p.y, p.z])), 3]}
              count={historyPoints.length}
            />
          </bufferGeometry>
          <lineBasicMaterial color={HISTORY_COLOR} transparent opacity={0.95} depthTest={false} linewidth={4} />
        </line>
      )}
      {historyPoints.map((p, i) => (
        <group key={i} position={p.toArray()}>
          <mesh renderOrder={9999}>
            <sphereGeometry args={[0.18, 12, 12]} />
            <meshBasicMaterial color={HISTORY_COLOR} transparent opacity={0.95} depthTest={false} />
          </mesh>
          <mesh renderOrder={9998}>
            <sphereGeometry args={[0.32, 12, 12]} />
            <meshBasicMaterial color={HISTORY_COLOR} transparent opacity={0.35} depthTest={false} />
          </mesh>
          <Html position={[0, 0.35, 0]} center style={{ pointerEvents: "none" }}>
            <div
              style={{
                background: "rgba(2,6,23,0.95)",
                border: `1px solid ${HISTORY_COLOR}`,
                color: HISTORY_COLOR,
                padding: "0px 5px",
                borderRadius: 999,
                fontSize: 9,
                fontWeight: 700,
                fontFamily: "ui-sans-serif, system-ui",
                whiteSpace: "nowrap",
              }}
            >
              {i + 1}
            </div>
          </Html>
        </group>
      ))}
      <line>
        <bufferGeometry ref={liveLineRef} />
        <lineBasicMaterial color={ACTIVE_COLOR} transparent opacity={1.0} depthTest={false} linewidth={4} />
      </line>
      <mesh ref={cityRingRef} renderOrder={10001}>
        <torusGeometry args={[0.7, 0.08, 14, 36]} />
        <meshBasicMaterial color={ACTIVE_COLOR} transparent opacity={1.0} depthTest={false} />
      </mesh>
      {/* Hint label anchored to a group whose position is updated every
       *  frame in useFrame above, so the label tracks the midpoint of
       *  the moon→city link as both endpoints move. */}
      <group ref={labelAnchorRef}>
        <Html center style={{ pointerEvents: "none" }}>
          <div
            style={{
              background: "rgba(2,6,23,0.95)",
              border: `1px solid ${ACTIVE_COLOR}`,
              color: "#f1f5f9",
              padding: "4px 10px",
              borderRadius: 4,
              fontSize: 11,
              fontWeight: 700,
              fontFamily: "ui-sans-serif, system-ui",
              whiteSpace: "nowrap",
              letterSpacing: 0.4,
              boxShadow: `0 0 16px ${ACTIVE_COLOR}aa`,
            }}
          >
            {workflowId} · {hintFor(workflowId, inFlight, historyPoints.length)}
          </div>
        </Html>
      </group>
    </group>
  );
}

/**
 * Tooltip subtitle for a hovered workflow. Prefers the live phase name
 * because that is what a non-technical reader actually wants to see;
 * falls back to the visited-cities count, then a friendly placeholder
 * when the workflow has only just spawned.
 */
function hintFor(workflowId: string | null, inFlight: WorkflowMoonData[], historyCount: number): string {
  if (!workflowId) return "";
  const wf = inFlight.find((w) => w.id === workflowId);
  if (wf?.phase) return wf.phase;
  if (historyCount > 0) return `${historyCount} stops`;
  return "just spawned";
}

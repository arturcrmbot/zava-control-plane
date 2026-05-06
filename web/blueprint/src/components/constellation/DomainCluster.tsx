/**
 * A domain cluster — a swarm of stars (workflows) softly clustered around a
 * 3D anchor point. No solid shell — just the stars themselves forming the
 * constellation.
 *
 * Three zoom levels:
 *   FAR   (dist > MID_DIST):  swarm of points, cluster name visible
 *   MID   (FOCUS .. MID):     each star labelled with its workflow_id +
 *                             current phase
 *   CLOSE (dist < FOCUS):     per-workflow activity rail — the recent
 *                             skill / tool / validator events as small
 *                             ephemeral text labels next to each star.
 *                             This is the "mind-map per workflow" view
 *                             the user wants when they zoom in.
 *
 * Cluster also exposes a click handler so the parent can fly the camera
 * to focus on it.
 */

import { Billboard, Text } from "@react-three/drei";
import { useFrame, type ThreeEvent } from "@react-three/fiber";
import { useMemo, useRef, useState } from "react";
import * as THREE from "three";

import { computeStarVisual } from "../../lib/constellation/starLifecycle";
import type { Mote } from "../../lib/constellation/types";

interface Props {
  workflowType: string;
  displayName: string;
  position: [number, number, number];
  motesRef: React.MutableRefObject<Map<string, Mote[]>>;
  bornMapRef: React.MutableRefObject<Map<string, number>>;
  diedMapRef: React.MutableRefObject<Map<string, number>>;
  color: string;
  cameraRef: React.MutableRefObject<THREE.Camera | null>;
  /** When set, identifies the cluster the user has focused on. Other
   *  clusters use this to hide their own labels so the focused view is
   *  uncluttered. */
  focusedClusterPos?: THREE.Vector3 | null;
  /** Called when the user clicks anywhere on this cluster. */
  onFocus?: (clusterPos: [number, number, number]) => void;
  /** Called when the user clicks an individual mote at MID/CLOSE LOD —
   *  the trail panel uses this to drill into one workflow. */
  onSelectWorkflow?: (workflowId: string) => void;
}

const N_MAX = 96;
/** Camera-distance thresholds for level-of-detail. */
const FOCUS_DIST = 5.0;
const MID_DIST = 9.0;

// SLA halo thresholds — DEMO-TIME heuristic. We don't have a per-domain
// real SLA budget on the wire yet (server only emits a discrete
// workflow.sla.breach_imminent flag), so the halo uses age-since-birth as
// a proxy. Workflows fresher than AGE_AMBER_MS get no halo (calm canvas
// during normal flow); past that an amber ring; past AGE_RED_MS a red
// ring that grows. Tune these to match how brisk the demo feels — values
// here are tuned for the recorded-template replay pacing.
const AGE_AMBER_MS = 18_000;
const AGE_RED_MS = 40_000;

// Build a soft circular sprite once. Bloom needs round bright cores to
// look like stars — the default square Points sprite kills the magic.
function makeStarTexture(): THREE.Texture {
  const size = 64;
  const canvas = document.createElement("canvas");
  canvas.width = size;
  canvas.height = size;
  const ctx = canvas.getContext("2d")!;
  const grad = ctx.createRadialGradient(
    size / 2,
    size / 2,
    0,
    size / 2,
    size / 2,
    size / 2,
  );
  grad.addColorStop(0, "rgba(255,255,255,1)");
  grad.addColorStop(0.25, "rgba(255,255,255,0.9)");
  grad.addColorStop(0.55, "rgba(255,255,255,0.35)");
  grad.addColorStop(1, "rgba(255,255,255,0)");
  ctx.fillStyle = grad;
  ctx.fillRect(0, 0, size, size);
  const tex = new THREE.CanvasTexture(canvas);
  tex.needsUpdate = true;
  return tex;
}

// Build a hollow ring sprite used to draw the SLA halo around aging
// motes. A thin annulus with soft edges so additive blending + bloom
// reads as a glowing halo, not a hard circle.
function makeRingTexture(): THREE.Texture {
  const size = 96;
  const canvas = document.createElement("canvas");
  canvas.width = size;
  canvas.height = size;
  const ctx = canvas.getContext("2d")!;
  const cx = size / 2;
  const cy = size / 2;
  // Inner edge (transparent) to outer edge (transparent), peaking at
  // ~0.78 radius — that's the visible ring band.
  const grad = ctx.createRadialGradient(cx, cy, 0, cx, cy, size / 2);
  grad.addColorStop(0.0, "rgba(255,255,255,0)");
  grad.addColorStop(0.55, "rgba(255,255,255,0)");
  grad.addColorStop(0.78, "rgba(255,255,255,0.85)");
  grad.addColorStop(0.92, "rgba(255,255,255,0.25)");
  grad.addColorStop(1, "rgba(255,255,255,0)");
  ctx.fillStyle = grad;
  ctx.fillRect(0, 0, size, size);
  const tex = new THREE.CanvasTexture(canvas);
  tex.needsUpdate = true;
  return tex;
}

export function DomainCluster({
  workflowType,
  displayName,
  position,
  motesRef,
  bornMapRef,
  diedMapRef,
  color,
  cameraRef,
  focusedClusterPos,
  onFocus,
  onSelectWorkflow,
}: Props) {
  const groupRef = useRef<THREE.Group>(null);
  const baseColor = useMemo(() => new THREE.Color(color), [color]);
  const starTex = useMemo(makeStarTexture, []);
  const ringTex = useMemo(makeRingTexture, []);

  const jitterRef = useRef<Map<string, [number, number, number]>>(new Map());
  /** Snapshot of motes for the currently-rendered LOD frame so MID/CLOSE
   *  per-workflow components can read positions without recomputing. */
  const moteFrameRef = useRef<
    Array<{ mote: Mote; x: number; y: number; z: number }>
  >([]);
  /** LOD level for this cluster, updated each frame. */
  const [lod, setLod] = useState<"far" | "mid" | "close">("far");
  /** Distance-based label opacity, 0..1, updated each frame. */
  const [labelOpacity, setLabelOpacity] = useState(1);

  const starGeom = useMemo(() => {
    const geom = new THREE.BufferGeometry();
    const pos = new Float32Array(N_MAX * 3);
    const col = new Float32Array(N_MAX * 3);
    const size = new Float32Array(N_MAX);
    geom.setAttribute("position", new THREE.BufferAttribute(pos, 3));
    geom.setAttribute("color", new THREE.BufferAttribute(col, 3));
    geom.setAttribute("size", new THREE.BufferAttribute(size, 1));
    geom.setDrawRange(0, 0);
    return geom;
  }, []);

  // Parallel geometry for SLA halos. Same N_MAX cap; each frame we write
  // a halo only for alive motes whose age has crossed AGE_AMBER_MS.
  const haloGeom = useMemo(() => {
    const geom = new THREE.BufferGeometry();
    geom.setAttribute(
      "position",
      new THREE.BufferAttribute(new Float32Array(N_MAX * 3), 3),
    );
    geom.setAttribute(
      "color",
      new THREE.BufferAttribute(new Float32Array(N_MAX * 3), 3),
    );
    geom.setAttribute(
      "size",
      new THREE.BufferAttribute(new Float32Array(N_MAX), 1),
    );
    geom.setDrawRange(0, 0);
    return geom;
  }, []);

  useFrame(({ clock }) => {
    const motes = motesRef.current.get(workflowType) ?? [];
    const t = clock.getElapsedTime();
    const now = performance.now();
    const posAttr = starGeom.getAttribute("position") as THREE.BufferAttribute;
    const colAttr = starGeom.getAttribute("color") as THREE.BufferAttribute;
    const sizeAttr = starGeom.getAttribute("size") as THREE.BufferAttribute;
    const posArr = posAttr.array as Float32Array;
    const colArr = colAttr.array as Float32Array;
    const sizeArr = sizeAttr.array as Float32Array;

    const haloPosAttr = haloGeom.getAttribute(
      "position",
    ) as THREE.BufferAttribute;
    const haloColAttr = haloGeom.getAttribute(
      "color",
    ) as THREE.BufferAttribute;
    const haloSizeAttr = haloGeom.getAttribute(
      "size",
    ) as THREE.BufferAttribute;
    const haloPosArr = haloPosAttr.array as Float32Array;
    const haloColArr = haloColAttr.array as Float32Array;
    const haloSizeArr = haloSizeAttr.array as Float32Array;
    let haloCount = 0;

    const base = { r: baseColor.r, g: baseColor.g, b: baseColor.b };

    let drawCount = 0;
    const culled: string[] = [];
    const frame: Array<{ mote: Mote; x: number; y: number; z: number }> = [];
    for (let i = 0; i < motes.length && drawCount < N_MAX; i++) {
      const m = motes[i];
      const bornAt = bornMapRef.current.get(m.id) ?? now;
      if (!bornMapRef.current.has(m.id)) bornMapRef.current.set(m.id, now);
      const diedAt = diedMapRef.current.get(m.id) ?? null;

      const v = computeStarVisual(m, base, now, bornAt, diedAt);
      if (v.dead) {
        culled.push(m.id);
        continue;
      }

      let jit = jitterRef.current.get(m.id);
      if (!jit) {
        // Marsaglia rejection sampling for uniform-volume distribution.
        let x = 0,
          y = 0,
          z = 0,
          s = 2;
        while (s >= 1 || s === 0) {
          x = Math.random() * 2 - 1;
          y = Math.random() * 2 - 1;
          z = Math.random() * 2 - 1;
          s = x * x + y * y + z * z;
        }
        const r = Math.cbrt(Math.random()) * 1.3;
        jit = [x * r, y * r, z * r];
        jitterRef.current.set(m.id, jit);
      }
      const drift = 0.05;
      const dx = Math.sin(t * 0.3 + m.seed * 0.7) * drift;
      const dy = Math.cos(t * 0.27 + m.seed * 0.91) * drift;
      const dz = Math.sin(t * 0.21 + m.seed * 1.13) * drift;

      const fx = jit[0] + dx;
      const fy = jit[1] + dy;
      const fz = jit[2] + dz;

      posArr[drawCount * 3] = fx;
      posArr[drawCount * 3 + 1] = fy;
      posArr[drawCount * 3 + 2] = fz;

      colArr[drawCount * 3] = v.r;
      colArr[drawCount * 3 + 1] = v.g;
      colArr[drawCount * 3 + 2] = v.b;
      sizeArr[drawCount] = 0.36 * v.scale;
      frame.push({ mote: m, x: fx, y: fy, z: fz });
      drawCount++;

      // SLA halo: alive motes only, age-based heuristic. Aging amber
      // ring at AGE_AMBER_MS, growing red at AGE_RED_MS, blocked/awaiting/
      // exception/completed states all skip the halo to keep the canvas
      // calm (those states already have their own loud signal). Server-
      // emitted slaBreach forces the red halo regardless of age.
      if (m.state === "alive" && haloCount < N_MAX) {
        const age = now - bornAt;
        const wantHalo = m.slaBreach || age >= AGE_AMBER_MS;
        if (wantHalo) {
          const isRed = m.slaBreach || age >= AGE_RED_MS;
          // Brightness pulses slowly so the halo feels alive rather than
          // pasted on. Faster pulse when red.
          const pulse = isRed
            ? 0.7 + 0.3 * Math.sin(now * 0.005 + m.seed * 0.13)
            : 0.6 + 0.25 * Math.sin(now * 0.0028 + m.seed * 0.21);
          const r = isRed ? 1.0 : 0.95;
          const g = isRed ? 0.25 : 0.62;
          const b = isRed ? 0.18 : 0.1;
          haloPosArr[haloCount * 3] = fx;
          haloPosArr[haloCount * 3 + 1] = fy;
          haloPosArr[haloCount * 3 + 2] = fz;
          haloColArr[haloCount * 3] = r * pulse;
          haloColArr[haloCount * 3 + 1] = g * pulse;
          haloColArr[haloCount * 3 + 2] = b * pulse;
          // Halo grows ~25% as it transitions amber → red, so the visual
          // pressure rises with the colour shift.
          haloSizeArr[haloCount] = isRed ? 1.05 : 0.85;
          haloCount++;
        }
      }
    }

    if (culled.length > 0) {
      for (const id of culled) {
        bornMapRef.current.delete(id);
        diedMapRef.current.delete(id);
        jitterRef.current.delete(id);
      }
      const cleaned = motes.filter((m) => !culled.includes(m.id));
      motesRef.current.set(workflowType, cleaned);
    }

    starGeom.setDrawRange(0, drawCount);
    posAttr.needsUpdate = true;
    colAttr.needsUpdate = true;
    sizeAttr.needsUpdate = true;
    moteFrameRef.current = frame;

    haloGeom.setDrawRange(0, haloCount);
    haloPosAttr.needsUpdate = true;
    haloColAttr.needsUpdate = true;
    haloSizeAttr.needsUpdate = true;

    // Distance + LOD.
    const cam = cameraRef.current;
    if (cam) {
      const wp = new THREE.Vector3(...position);
      const dist = cam.position.distanceTo(wp);
      const next = dist < FOCUS_DIST ? "close" : dist < MID_DIST ? "mid" : "far";
      if (next !== lod) setLod(next);

      // Cluster name visibility: fully visible at FAR, fades through MID,
      // hidden at CLOSE so per-workflow detail isn't drowned out. Also
      // suppressed entirely when another cluster has been focused (the
      // user has zoomed in elsewhere; my label would just be noise).
      let nextOpacity = 0;
      const isFocusedElsewhere = !!(
        focusedClusterPos && focusedClusterPos.distanceTo(wp) > 0.5
      );
      if (isFocusedElsewhere) {
        nextOpacity = 0;
      } else if (dist > MID_DIST) {
        nextOpacity = 1;
      } else if (dist > FOCUS_DIST) {
        nextOpacity = (dist - FOCUS_DIST) / (MID_DIST - FOCUS_DIST);
      }
      const rounded = Math.round(nextOpacity * 10) / 10;
      if (rounded !== labelOpacity) {
        setLabelOpacity(rounded);
      }
    }
  });

  // A transparent invisible click-target sphere — clicks bubble up so the
  // parent can fly the camera here.
  const handleClick = (e: ThreeEvent<MouseEvent>) => {
    e.stopPropagation();
    onFocus?.(position);
  };

  return (
    <group ref={groupRef} position={position}>
      {/* Click target — invisible but pickable. Generous radius so it's
          easy to hit at overview distance. */}
      <mesh onClick={handleClick}>
        <sphereGeometry args={[2.8, 12, 12]} />
        <meshBasicMaterial
          transparent
          opacity={0.001}
          depthWrite={false}
          colorWrite={false}
        />
      </mesh>

      {/* The stars themselves. Round soft sprite + additive blending +
          bloom downstream = actual stars, not square dots. */}
      <points geometry={starGeom}>
        <pointsMaterial
          map={starTex}
          vertexColors
          size={0.35}
          sizeAttenuation
          transparent
          opacity={1}
          depthWrite={false}
          alphaTest={0.01}
          blending={THREE.AdditiveBlending}
        />
      </points>

      {/* SLA halo ring around aging alive motes — drawn before the stars
          but additively, so the star core sits inside the halo. */}
      <points geometry={haloGeom}>
        <pointsMaterial
          map={ringTex}
          vertexColors
          size={1}
          sizeAttenuation
          transparent
          opacity={0.85}
          depthWrite={false}
          alphaTest={0.01}
          blending={THREE.AdditiveBlending}
        />
      </points>

      {/* Cluster label — visible at FAR / MID, hidden at CLOSE. */}
      {labelOpacity > 0.02 ? (
        <Billboard position={[0, 1.5, 0]}>
          <Text
            fontSize={0.32}
            color="#e9e7e3"
            anchorX="center"
            anchorY="middle"
            outlineWidth={0.008}
            outlineColor="#0a0a0c"
            fillOpacity={labelOpacity}
            outlineOpacity={labelOpacity}
          >
            {displayName}
          </Text>
          <Text
            position={[0, -0.32, 0]}
            fontSize={0.16}
            color="#7e7c76"
            anchorX="center"
            anchorY="middle"
            fillOpacity={labelOpacity * 0.85}
          >
            {workflowType}
          </Text>
        </Billboard>
      ) : null}

      {/* MID / CLOSE per-workflow detail. Rendered as React children of
          this group so they inherit the cluster's local space. */}
      {(lod === "mid" || lod === "close") &&
        moteFrameRef.current.map(({ mote, x, y, z }) => (
          <WorkflowDetail
            key={mote.id}
            mote={mote}
            position={[x, y, z]}
            lod={lod}
            onSelect={onSelectWorkflow}
          />
        ))}
    </group>
  );
}

// ---------------------------------------------------------------------------
// Per-workflow detail label — visible only when the camera is close enough.
// ---------------------------------------------------------------------------
function WorkflowDetail({
  mote,
  position,
  lod,
  onSelect,
}: {
  mote: Mote;
  position: [number, number, number];
  lod: "mid" | "close";
  onSelect?: (workflowId: string) => void;
}) {
  // MID: just the wid + most recent skill.
  // CLOSE: full trail.
  return (
    <group position={position}>
      {/* Click target — invisible sphere around the star. Generous radius
          so it's easy to hit even at MID LOD where stars are tiny. */}
      {onSelect ? (
        <mesh
          onClick={(e) => {
            e.stopPropagation();
            onSelect(mote.id);
          }}
        >
          <sphereGeometry args={[0.18, 8, 8]} />
          <meshBasicMaterial
            transparent
            opacity={0.001}
            depthWrite={false}
            colorWrite={false}
          />
        </mesh>
      ) : null}
      <Billboard position={[0.10, 0.05, 0]}>
        {/* anchorX="left" so labels grow rightward and don't overlap the star */}
        <Text
          fontSize={0.05}
          color="#e9e7e3"
          anchorX="left"
          anchorY="middle"
          outlineWidth={0.0015}
          outlineColor="#0a0a0c"
        >
          {mote.id}
        </Text>
        {mote.lastSkill ? (
          <Text
            position={[0, -0.07, 0]}
            fontSize={0.038}
            color="#f4a300"
            anchorX="left"
            anchorY="middle"
            outlineWidth={0.001}
            outlineColor="#0a0a0c"
          >
            {`▸ ${mote.lastSkill}`}
          </Text>
        ) : null}
        {lod === "close" && mote.lastTool ? (
          <Text
            position={[0, -0.13, 0]}
            fontSize={0.038}
            color="#7faed4"
            anchorX="left"
            anchorY="middle"
            outlineWidth={0.001}
            outlineColor="#0a0a0c"
          >
            {`→ ${mote.lastTool}`}
          </Text>
        ) : null}
        {lod === "close" && mote.state === "blocked" ? (
          <Text
            position={[0, -0.19, 0]}
            fontSize={0.038}
            color="#c54a3d"
            anchorX="left"
            anchorY="middle"
            outlineWidth={0.001}
            outlineColor="#0a0a0c"
          >
            ✕ validator blocked
          </Text>
        ) : null}
        {/* HITL satellite — show WHO the bot is waiting on. Magenta to
            match the awaiting-state mote tint. Always rendered when the
            mote is awaiting (not just CLOSE) because the persona is the
            single most demo-worthy answer to "what's it doing?". */}
        {mote.state === "awaiting" && mote.awaitingPersona ? (
          <Text
            position={[0, -0.19, 0]}
            fontSize={0.044}
            color={mote.escalated ? "#ff6fed" : "#d966ec"}
            anchorX="left"
            anchorY="middle"
            outlineWidth={0.0015}
            outlineColor="#0a0a0c"
          >
            {`⊙ ${mote.escalated ? "ESCALATED → " : "asking "}${formatPersona(
              mote.awaitingPersona,
            )}`}
          </Text>
        ) : null}
        {lod === "close" &&
        mote.state === "awaiting" &&
        mote.awaitingReason ? (
          <Text
            position={[0, -0.25, 0]}
            fontSize={0.034}
            color="#a674b8"
            anchorX="left"
            anchorY="middle"
            outlineWidth={0.001}
            outlineColor="#0a0a0c"
          >
            {formatReason(mote.awaitingReason)}
          </Text>
        ) : null}
      </Billboard>
    </group>
  );
}

/** Turn snake_case persona keys ("contract_finance_bp") into a
 *  human-friendly label ("Contract Finance BP"). */
function formatPersona(p: string): string {
  return p
    .split("_")
    .map((seg) =>
      seg.length <= 3
        ? seg.toUpperCase()
        : seg.charAt(0).toUpperCase() + seg.slice(1),
    )
    .join(" ");
}

/** Reason slugs are snake_case verbs ("awaiting_finance_signoff"). */
function formatReason(r: string): string {
  return r.replace(/_/g, " ");
}

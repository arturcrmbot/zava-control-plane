/**
 * The Constellation — substrate sphere at centre, domain clusters scattered
 * in 3D space around it, all rendered as soft additive points + bloom for
 * the luminous look.
 *
 * Navigation: drag to rotate, scroll/pinch to zoom, right-click drag to pan.
 *
 * Cluster positions are deterministic from the workflow_type string so the
 * picture is stable across reloads — the same domain always sits at the
 * same spot in the sky.
 */

import { OrbitControls, PerspectiveCamera } from "@react-three/drei";
import { Canvas, useFrame, useThree } from "@react-three/fiber";
import { Bloom, EffectComposer } from "@react-three/postprocessing";
import { useEffect, useMemo, useRef, useState } from "react";
import * as THREE from "three";

import type { ObservatoryEvent } from "../lib/types";
import { describeDomainOrbits, SUBSTRATE_RADIUS } from "../lib/constellation/types";
import type { Mote, PhotonArc, Pulse } from "../lib/constellation/types";
import { buildSubstrateMap } from "../lib/constellation/substrateMap";
import { sunflowerSphere } from "../lib/constellation/sunflower";
import { useComposition } from "../lib/useComposition";
import { useObservatory } from "../lib/useObservatory";

import { DomainCluster } from "./constellation/DomainCluster";
import { SubstrateSphere, SubstrateLabel } from "./constellation/SubstrateSphere";

interface Props {
  status: "watching" | "connecting" | "offline";
  /** When true, fills its parent (used by the standalone page). */
  fullScreen?: boolean;
}

// Distinct cluster tints. Picked from a warm-cool palette so the orbit
// reads as a constellation, not a heatmap.
const DOMAIN_PALETTE = [
  "#f4a300", // amber
  "#e87a5d", // coral
  "#5fb3a8", // teal
  "#9b7ed4", // violet
  "#d4b95f", // gold
  "#7faed4", // cool blue
  "#c25f9e", // magenta
  "#5fd49d", // mint
  "#d49b5f", // burnt orange
  "#a8d45f", // lime
  "#5f9bd4", // sky
];

const SCENE_RADIUS = 8.5;

/**
 * Place clusters around the substrate as a Fibonacci-on-sphere scatter so
 * they read as a 3D constellation, not a flat ring. Stable per workflow_type.
 */
function clusterPositions(
  workflowTypes: string[],
): Map<string, [number, number, number]> {
  const out = new Map<string, [number, number, number]>();
  const n = workflowTypes.length;
  const phi = Math.PI * (3 - Math.sqrt(5));
  // Sort for determinism.
  const sorted = [...workflowTypes].sort((a, b) => a.localeCompare(b));
  for (let i = 0; i < n; i++) {
    const y = 1 - (i / Math.max(1, n - 1)) * 2;
    const r = Math.sqrt(1 - y * y);
    const theta = phi * i;
    const x = Math.cos(theta) * r;
    const z = Math.sin(theta) * r;
    out.set(sorted[i], [
      x * SCENE_RADIUS,
      // Compress Y a bit so clusters cluster around the equatorial plane —
      // a pure sphere distribution has too many points at the poles for an
      // initial framing camera.
      y * SCENE_RADIUS * 0.55,
      z * SCENE_RADIUS,
    ]);
  }
  return out;
}

export function Constellation({ status, fullScreen = false }: Props) {
  const { data: composition } = useComposition();
  const orbits = useMemo(() => describeDomainOrbits(composition), [composition]);
  const positions = useMemo(
    () => clusterPositions(orbits.map((o) => o.workflowType)),
    [orbits],
  );
  const substrate = useMemo(
    () => buildSubstrateMap(composition, 2400),
    [composition],
  );
  /** Cached substrate dot positions in world space — needed to draw the
   *  arcs from the firing dot to the cluster anchor. Generated with the
   *  exact same sunflower coil at the exact same radius the sphere uses. */
  const substrateDotPositions = useMemo(
    () => sunflowerSphere(substrate.total, SUBSTRATE_RADIUS),
    [substrate.total],
  );

  // Reverse lookup: display name (what the SSE stream emits as `domain`) →
  // canonical workflow_type (what we key clusters by). The composition
  // tree's workflow_types map is workflow_type → display_name; invert.
  // We also fold workflow_id prefixes (EXP, HIRE, ITAR, ...) as a fallback
  // for events that arrive without a `domain` field.
  const nameToType = useMemo(() => {
    const map = new Map<string, string>();
    if (!composition) return map;
    for (const [wt, name] of Object.entries(composition.workflow_types)) {
      map.set(name, wt);
      map.set(wt, wt); // tolerate events that already carry the canonical type
    }
    return map;
  }, [composition]);

  const prefixToType = useMemo(() => {
    const map = new Map<string, string>();
    if (!composition) return map;
    // Workflow_id prefix is the leading uppercase token before "-".
    // We don't have a direct prefix → workflow_type map in the
    // composition tree (it lives in api/shared/domains.py), so derive
    // a best-effort one from the workflow_types map.
    const known: Record<string, string> = {
      EXP: "expense-claim",
      HIRE: "hiring",
      TRV: "travel-preapproval",
      VKY: "vendor-kyc",
      ONB: "employee-onboarding",
      ITAR: "it-access-request",
      CRN: "contract-renewal",
      PRR: "perf-review",
    };
    for (const [prefix, wt] of Object.entries(known)) {
      if (composition.workflow_types[wt]) map.set(prefix, wt);
    }
    return map;
  }, [composition]);

  // Mutable scene state — the canvas reads it inside useFrame, the SSE
  // handler writes it. Decoupled from React so we don't re-render 60Hz.
  const pulsesRef = useRef<Pulse[]>([]);
  const arcsRef = useRef<PhotonArc[]>([]);
  const motesRef = useRef<Map<string, Mote[]>>(new Map());
  const bornMapRef = useRef<Map<string, number>>(new Map());
  const diedMapRef = useRef<Map<string, number>>(new Map());
  const progressRef = useRef<Map<string, number>>(new Map());
  const widToTypeRef = useRef<Map<string, string>>(new Map());
  const cameraRef = useRef<THREE.Camera | null>(null);

  // SSE → state. The canvas is the only thing that re-renders.
  useObservatory({
    bufferSize: 1,
    onEvent: (e) => {
      handleEvent(e, {
        substrate,
        substrateDotPositions,
        clusterPositions: positions,
        pulsesRef,
        arcsRef,
        motesRef,
        bornMapRef,
        diedMapRef,
        progressRef,
        widToTypeRef,
        nameToType,
        prefixToType,
      });
    },
  });

  // Camera fly target. When set, the CameraRig animates the camera to it
  // smoothly. Cleared when arrival completes.
  const [flyTo, setFlyTo] = useState<{
    target: THREE.Vector3;
    camPos: THREE.Vector3;
  } | null>(null);
  /** Persistent focus — the cluster the camera is currently parked at, or
   *  null when in overview. Used so non-focused cluster names hide. */
  const [focusedClusterPos, setFocusedClusterPos] = useState<
    THREE.Vector3 | null
  >(null);
  /** Display name of the cluster the operator just clicked into. Drives
   *  the "FOCUSED · X" pill at the top of the canvas so the click
   *  obviously landed (the camera flight alone is easy to miss). */
  const [focusedClusterName, setFocusedClusterName] = useState<string | null>(
    null,
  );

  const handleClusterFocus = (clusterPos: [number, number, number]) => {
    const target = new THREE.Vector3(...clusterPos);
    // Position the camera ~7 units away so we land in MID lod (cluster
    // labels fade, per-workflow ids appear) without star sprites or text
    // ballooning. User can then zoom further with scroll if they want.
    const dirFromOrigin = target.clone().normalize();
    const camPos = target.clone().add(dirFromOrigin.multiplyScalar(7.5));
    camPos.y += 1.5;
    setFlyTo({ target, camPos });
    setFocusedClusterPos(target);
    // Reverse lookup: which orbit's position matches what we were given.
    // positions is workflow_type → [x,y,z]; find by approx-equal.
    let matchedName: string | null = null;
    for (const o of orbits) {
      const p = positions.get(o.workflowType);
      if (
        p &&
        Math.abs(p[0] - clusterPos[0]) < 0.01 &&
        Math.abs(p[1] - clusterPos[1]) < 0.01 &&
        Math.abs(p[2] - clusterPos[2]) < 0.01
      ) {
        matchedName = o.displayName;
        break;
      }
    }
    setFocusedClusterName(matchedName);
  };

  const handleResetCamera = () => {
    setFlyTo({
      target: new THREE.Vector3(0, 0, 0),
      camPos: new THREE.Vector3(0, 3, 22),
    });
    setFocusedClusterPos(null);
    setFocusedClusterName(null);
  };

  /** workflow_id of the mote currently selected for the inspector panel.
   *  Set by clicking a star at MID/CLOSE LOD; cleared by the panel's
   *  close button or by Escape. */
  const [selectedWid, setSelectedWid] = useState<string | null>(null);

  /** Substrate dot under the pointer, if any. Drives the hover tooltip
   *  that names the skill / tool / validator a dot represents. */
  const [hoveredDot, setHoveredDot] = useState<{
    kind: "skill" | "tool" | "validator";
    label: string;
    x: number;
    y: number;
  } | null>(null);

  // Dev-only hook: lets the visual smoke check open the inspector
  // without trying to mouse-click a tiny 3D sphere from headless Chrome.
  // Production users never see this; nothing in the app calls it.
  useEffect(() => {
    const w = window as unknown as {
      __cstlSelect?: (id: string | null) => void;
      __cstlAnyAliveWid?: () => string | null;
    };
    w.__cstlSelect = setSelectedWid;
    w.__cstlAnyAliveWid = () => {
      for (const list of motesRef.current.values()) {
        for (const m of list) {
          if (m.state === "alive" || m.state === "awaiting") return m.id;
        }
      }
      return null;
    };
    return () => {
      delete w.__cstlSelect;
      delete w.__cstlAnyAliveWid;
    };
  }, []);

  // ----- Keyboard shortcuts -------------------------------------------
  // Number keys 1-9 jump to that cluster's index in the nav-panel order.
  // 0 / Esc returns to overview (Esc closes the inspector first if open).
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      // Don't hijack typing into form elements.
      const tag = (e.target as HTMLElement | null)?.tagName ?? "";
      if (tag === "INPUT" || tag === "TEXTAREA" || tag === "SELECT") return;
      if (e.metaKey || e.ctrlKey || e.altKey) return;
      if (e.key === "0" || e.key === "Escape") {
        if (e.key === "Escape" && selectedWid) {
          setSelectedWid(null);
          return;
        }
        handleResetCamera();
        return;
      }
      const n = parseInt(e.key, 10);
      if (!isNaN(n) && n >= 1 && n <= 9 && orbits[n - 1]) {
        const wt = orbits[n - 1].workflowType;
        const pos = positions.get(wt);
        if (pos) handleClusterFocus(pos);
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [orbits, positions]);

  return (
    <div className={`constellation${fullScreen ? " constellation--full" : ""}`}>
      <Canvas
        dpr={[1, 2]}
        gl={{ antialias: false, alpha: false }}
        style={{ background: "#0a0a0c" }}
      >
        <PerspectiveCamera
          makeDefault
          position={[0, 3, 22]}
          fov={42}
        />
        <CameraHandle cameraRef={cameraRef} />
        <CameraRig flyTo={flyTo} onArrived={() => setFlyTo(null)} />
        <OrbitControls
          enablePan
          enableZoom
          enableRotate
          minDistance={1.5}
          maxDistance={45}
          dampingFactor={0.08}
          rotateSpeed={0.6}
          zoomSpeed={0.8}
        />

        {/* Backdrop: a very faint star field so the empty space doesn't
            read as flat black when the substrate fades to one side. */}
        <BackdropStars count={500} radius={60} />

        {/* Centre: the substrate. */}
        <SubstrateSphere
          substrate={substrate}
          pulsesRef={pulsesRef}
          onHoverDot={setHoveredDot}
        />

        {/* Substrate centre label so the bright sphere has a name. */}
        <SubstrateLabel
          cameraRef={cameraRef}
          focusedClusterPos={focusedClusterPos}
        />

        {/* Photon arcs: substrate dot → cluster anchor on every event. */}
        <PhotonArcs arcsRef={arcsRef} />

        {/* Scattered domain clusters. */}
        {orbits.map((d, i) => {
          const pos = positions.get(d.workflowType) ?? [0, 0, 0];
          return (
            <DomainCluster
              key={d.workflowType}
              workflowType={d.workflowType}
              displayName={d.displayName}
              position={pos as [number, number, number]}
              motesRef={motesRef}
              bornMapRef={bornMapRef}
              diedMapRef={diedMapRef}
              color={DOMAIN_PALETTE[i % DOMAIN_PALETTE.length]}
              cameraRef={cameraRef}
              focusedClusterPos={focusedClusterPos}
              onFocus={handleClusterFocus}
              onSelectWorkflow={setSelectedWid}
            />
          );
        })}

        {/* Subtle fill so the substrate has a hint of form even before bloom. */}
        <ambientLight intensity={0.25} />

        {/* Bloom is what turns the points into stars. */}
        <EffectComposer>
          <Bloom
            intensity={1.4}
            luminanceThreshold={0.15}
            luminanceSmoothing={0.85}
            mipmapBlur
          />
        </EffectComposer>
      </Canvas>

      <div className="constellation__hud">
        <div className="constellation__hud-status">
          {status === "watching"
            ? "● live"
            : status === "connecting"
            ? "○ connecting"
            : "× offline"}
        </div>
        <div className="constellation__hud-help">
          drag · scroll to zoom · click a domain in the panel to fly in
        </div>
        <div className="constellation__hud-legend">
          <div className="constellation__hud-legend-row">
            <span className="constellation__hud-legend-label">substrate</span>
            <span style={{ color: "#f4a300" }}>●</span> skill
            {" · "}
            <span style={{ color: "#7faed4" }}>●</span> tool
            {" · "}
            <span style={{ color: "#c54a3d" }}>●</span> validator block
          </div>
          <div className="constellation__hud-legend-row">
            <span className="constellation__hud-legend-label">workflow</span>
            <span style={{ color: "#bdbdbd" }}>●</span> alive
            {" · "}
            <span style={{ color: "#d966ec" }}>●</span> awaiting human
            {" · "}
            <span style={{ color: "#f28a3d" }}>●</span> exception
            {" · "}
            <span style={{ color: "#c54a3d" }}>●</span> blocked
            {" · "}
            <span style={{ color: "#fff5d8" }}>★</span> completed
          </div>
        </div>
      </div>

      {/* Live counts ribbon — projector-friendly running totals. */}
      <CountsRibbon motesRef={motesRef} orbits={orbits} />

      {/* Domain navigator panel — a guaranteed way to fly to any cluster. */}
      <div className="constellation__nav">
        <div className="constellation__nav-title">domains</div>
        {orbits.map((d, i) => {
          const pos = positions.get(d.workflowType) ?? [0, 0, 0];
          const tint = DOMAIN_PALETTE[i % DOMAIN_PALETTE.length];
          return (
            <button
              key={d.workflowType}
              type="button"
              className="constellation__nav-item"
              onClick={() => handleClusterFocus(pos as [number, number, number])}
            >
              <span
                className="constellation__nav-swatch"
                style={{ background: tint, boxShadow: `0 0 8px ${tint}` }}
              />
              <span className="constellation__nav-label">{d.displayName}</span>
              <DomainNavCount workflowType={d.workflowType} motesRef={motesRef} />
            </button>
          );
        })}
        <button
          type="button"
          className="constellation__nav-item constellation__nav-item--reset"
          onClick={handleResetCamera}
        >
          <span className="constellation__nav-swatch constellation__nav-swatch--reset" />
          <span className="constellation__nav-label">overview</span>
        </button>
      </div>

      <button
        type="button"
        className="constellation__reset"
        onClick={handleResetCamera}
        title="Return to overview (key: 0 / esc)"
      >
        ↺ overview
      </button>

      {/* Workflow inspector — opens when the operator clicks a star at
          MID/CLOSE LOD. Reads its data from motesRef on a slow tick so
          the rolling trail updates while the panel is open. */}
      {selectedWid ? (
        <WorkflowInspector
          workflowId={selectedWid}
          motesRef={motesRef}
          orbits={orbits}
          onClose={() => setSelectedWid(null)}
        />
      ) : null}

      {/* Focused-cluster pill — confirms a click landed. Without this the
          camera flight is easy to miss because the substrate dominates
          the new view; the pill explicitly says "you flew to X". */}
      {focusedClusterName ? (
        <div className="constellation__focus-pill">
          <span className="constellation__focus-pill-label">focused</span>
          <span className="constellation__focus-pill-name">
            {focusedClusterName}
          </span>
          <button
            type="button"
            className="constellation__focus-pill-close"
            onClick={handleResetCamera}
            title="Return to overview (key: 0 / esc)"
          >
            ×
          </button>
        </div>
      ) : null}

      {/* Substrate dot hover tooltip — names the skill / tool / validator
          the operator's pointing at. Positioned next to the cursor; the
          kind colour matches the HUD legend. */}
      {hoveredDot ? (
        <div
          className="constellation__dot-tooltip"
          style={{
            left: hoveredDot.x + 12,
            top: hoveredDot.y + 12,
          }}
        >
          <span
            className="constellation__dot-tooltip-kind"
            style={{
              color:
                hoveredDot.kind === "tool"
                  ? "#7faed4"
                  : hoveredDot.kind === "validator"
                  ? "#c54a3d"
                  : "#f4a300",
            }}
          >
            {hoveredDot.kind}
          </span>
          <span className="constellation__dot-tooltip-label">
            {hoveredDot.label}
          </span>
        </div>
      ) : null}
    </div>
  );
}

// ---------------------------------------------------------------------------
// CameraRig — eased fly-to-target animation. When `flyTo` is set, eases the
// camera position + OrbitControls target toward the requested values. Calls
// `onArrived` once close enough so the parent can clear the request.
// ---------------------------------------------------------------------------
function CameraRig({
  flyTo,
  onArrived,
}: {
  flyTo: { target: THREE.Vector3; camPos: THREE.Vector3 } | null;
  onArrived: () => void;
}) {
  const { camera, controls } = useThree() as {
    camera: THREE.Camera;
    controls: { target: THREE.Vector3; update: () => void } | null;
  };
  const hasArrived = useRef(false);

  useEffect(() => {
    hasArrived.current = false;
  }, [flyTo]);

  useFrame((_, delta) => {
    if (!flyTo || hasArrived.current) return;
    // Higher = snappier. Scale by delta to keep the ease frame-rate independent.
    const k = 1 - Math.exp(-6 * delta);
    camera.position.lerp(flyTo.camPos, k);
    if (controls) {
      controls.target.lerp(flyTo.target, k);
      controls.update();
    }
    const posDelta = camera.position.distanceTo(flyTo.camPos);
    const tgtDelta = controls
      ? controls.target.distanceTo(flyTo.target)
      : 0;
    if (posDelta < 0.05 && tgtDelta < 0.05) {
      hasArrived.current = true;
      onArrived();
    }
  });

  return null;
}

// ---------------------------------------------------------------------------
// Tiny helper: capture the active camera into a ref so DomainCluster can
// distance-fade its label.
// ---------------------------------------------------------------------------
function CameraHandle({
  cameraRef,
}: {
  cameraRef: React.MutableRefObject<THREE.Camera | null>;
}) {
  const { camera } = useThree();
  useEffect(() => {
    cameraRef.current = camera;
  }, [camera, cameraRef]);
  return null;
}

// ---------------------------------------------------------------------------
// Backdrop stars: a far-away point cloud that gives the scene depth.
// ---------------------------------------------------------------------------
function BackdropStars({
  count,
  radius,
}: {
  count: number;
  radius: number;
}) {
  const geom = useMemo(() => {
    const g = new THREE.BufferGeometry();
    const pos = new Float32Array(count * 3);
    const col = new Float32Array(count * 3);
    for (let i = 0; i < count; i++) {
      // Random unit vector × radius, with some variation in distance.
      let x = 0, y = 0, z = 0, s = 2;
      while (s >= 1 || s === 0) {
        x = Math.random() * 2 - 1;
        y = Math.random() * 2 - 1;
        z = Math.random() * 2 - 1;
        s = x * x + y * y + z * z;
      }
      const len = Math.sqrt(s);
      const r = radius * (0.85 + Math.random() * 0.3);
      pos[i * 3] = (x / len) * r;
      pos[i * 3 + 1] = (y / len) * r;
      pos[i * 3 + 2] = (z / len) * r;
      const v = 0.18 + Math.random() * 0.35;
      col[i * 3] = v * 0.95;
      col[i * 3 + 1] = v * 0.92;
      col[i * 3 + 2] = v * 0.90;
    }
    g.setAttribute("position", new THREE.BufferAttribute(pos, 3));
    g.setAttribute("color", new THREE.BufferAttribute(col, 3));
    return g;
  }, [count, radius]);

  return (
    <points geometry={geom}>
      <pointsMaterial
        vertexColors
        size={0.12}
        sizeAttenuation
        transparent
        opacity={0.85}
        depthWrite={false}
        blending={THREE.AdditiveBlending}
      />
    </points>
  );
}

// ---------------------------------------------------------------------------
// PhotonArcs — thin glowing lines from substrate dot → cluster anchor that
// fade over ARC_DECAY_MS. One LineSegments mesh with MAX_ARCS*2 vertices
// per frame. Lines belonging to dead arcs are zero-lengthed (start == end)
// so they collapse to nothing without us needing to resize the buffer.
// ---------------------------------------------------------------------------
const ARC_DECAY_MS = 1100;
const ARC_COL_SKILL = new THREE.Color("#f4a300");
const ARC_COL_TOOL = new THREE.Color("#7faed4");
const ARC_COL_VALIDATOR = new THREE.Color("#c54a3d");

function PhotonArcs({
  arcsRef,
}: {
  arcsRef: React.MutableRefObject<PhotonArc[]>;
}) {
  const linesRef = useRef<THREE.LineSegments>(null);

  const geometry = useMemo(() => {
    const geom = new THREE.BufferGeometry();
    // 2 vertices per arc, 3 floats per vertex (xyz) and 3 per colour.
    geom.setAttribute(
      "position",
      new THREE.BufferAttribute(new Float32Array(MAX_ARCS * 2 * 3), 3),
    );
    geom.setAttribute(
      "color",
      new THREE.BufferAttribute(new Float32Array(MAX_ARCS * 2 * 3), 3),
    );
    geom.setDrawRange(0, 0);
    return geom;
  }, []);

  useEffect(() => () => geometry.dispose(), [geometry]);

  useFrame(() => {
    const lines = linesRef.current;
    if (!lines) return;
    const arcs = arcsRef.current;
    const now = performance.now();
    const posAttr = geometry.getAttribute("position") as THREE.BufferAttribute;
    const colAttr = geometry.getAttribute("color") as THREE.BufferAttribute;
    const posArr = posAttr.array as Float32Array;
    const colArr = colAttr.array as Float32Array;

    let writeIdx = 0;
    for (let i = 0; i < arcs.length && writeIdx < MAX_ARCS; i++) {
      const a = arcs[i];
      const age = now - a.startMs;
      if (age >= ARC_DECAY_MS) continue;
      const k = 1 - age / ARC_DECAY_MS;
      // Ease-out so the head lingers, the tail vanishes fast.
      const fade = k * k;
      const tint =
        a.kind === "validator"
          ? ARC_COL_VALIDATOR
          : a.kind === "tool"
          ? ARC_COL_TOOL
          : ARC_COL_SKILL;
      // Animate the arc head growing from substrate dot toward cluster
      // anchor in the first ~40% of life, then the whole line fades. This
      // gives a "shooting" feel rather than a flicker.
      const grow = Math.min(1, (1 - k) * 2.5);
      const ex = a.fromX + (a.toX - a.fromX) * grow;
      const ey = a.fromY + (a.toY - a.fromY) * grow;
      const ez = a.fromZ + (a.toZ - a.fromZ) * grow;

      const v = writeIdx * 6;
      posArr[v] = a.fromX;
      posArr[v + 1] = a.fromY;
      posArr[v + 2] = a.fromZ;
      posArr[v + 3] = ex;
      posArr[v + 4] = ey;
      posArr[v + 5] = ez;
      // Tail dim, head bright — gives the line directionality.
      colArr[v] = tint.r * fade * 0.35;
      colArr[v + 1] = tint.g * fade * 0.35;
      colArr[v + 2] = tint.b * fade * 0.35;
      colArr[v + 3] = tint.r * fade * 1.4;
      colArr[v + 4] = tint.g * fade * 1.4;
      colArr[v + 5] = tint.b * fade * 1.4;

      arcs[writeIdx++] = a;
    }
    arcs.length = writeIdx;

    geometry.setDrawRange(0, writeIdx * 2);
    posAttr.needsUpdate = true;
    colAttr.needsUpdate = true;
  });

  return (
    <lineSegments ref={linesRef} geometry={geometry}>
      <lineBasicMaterial
        vertexColors
        transparent
        opacity={0.95}
        depthWrite={false}
        blending={THREE.AdditiveBlending}
      />
    </lineSegments>
  );
}

// ---------------------------------------------------------------------------
// CountsRibbon — running totals across all clusters, refreshed on a slow
// tick so it doesn't churn React 60Hz. Also tracks lifetime "completed" by
// observing motes leaving the alive bucket.
// ---------------------------------------------------------------------------
function CountsRibbon({
  motesRef,
  orbits,
}: {
  motesRef: React.MutableRefObject<Map<string, Mote[]>>;
  orbits: { workflowType: string }[];
}) {
  const [tick, setTick] = useState(0);
  const seenCompletedRef = useRef<Map<string, true>>(new Map());
  const completedTotalRef = useRef(0);

  useEffect(() => {
    const id = window.setInterval(() => setTick((t) => t + 1), 750);
    return () => window.clearInterval(id);
  }, []);

  // Walk all motes once per tick to get the snapshot.
  let alive = 0;
  let awaiting = 0;
  let exception = 0;
  let blocked = 0;
  for (const o of orbits) {
    const list = motesRef.current.get(o.workflowType) ?? [];
    for (const m of list) {
      if (m.state === "alive") alive++;
      else if (m.state === "awaiting") awaiting++;
      else if (m.state === "exception") exception++;
      else if (m.state === "blocked") blocked++;
      if (m.state === "completed" && !seenCompletedRef.current.has(m.id)) {
        seenCompletedRef.current.set(m.id, true);
        completedTotalRef.current += 1;
      }
    }
  }
  // Reference tick to avoid the unused-var lint when React isn't tracking it.
  void tick;

  return (
    <div className="constellation__counts" role="status">
      <span className="constellation__counts-item">
        <span className="constellation__counts-num">{alive}</span> alive
      </span>
      <span className="constellation__counts-sep">·</span>
      <span
        className="constellation__counts-item"
        style={{ color: awaiting > 0 ? "#d966ec" : undefined }}
      >
        <span className="constellation__counts-num">{awaiting}</span> awaiting
      </span>
      <span className="constellation__counts-sep">·</span>
      <span
        className="constellation__counts-item"
        style={{ color: exception > 0 ? "#f28a3d" : undefined }}
      >
        <span className="constellation__counts-num">{exception}</span> exception
      </span>
      <span className="constellation__counts-sep">·</span>
      <span
        className="constellation__counts-item"
        style={{ color: blocked > 0 ? "#c54a3d" : undefined }}
      >
        <span className="constellation__counts-num">{blocked}</span> blocked
      </span>
      <span className="constellation__counts-sep">·</span>
      <span className="constellation__counts-item">
        <span className="constellation__counts-num">
          {completedTotalRef.current}
        </span>{" "}
        completed
      </span>
    </div>
  );
}

// ---------------------------------------------------------------------------
// DomainNavCount — small in-flight badge next to a nav-panel domain entry.
// Shares the same slow tick cadence as CountsRibbon.
// ---------------------------------------------------------------------------
function DomainNavCount({
  workflowType,
  motesRef,
}: {
  workflowType: string;
  motesRef: React.MutableRefObject<Map<string, Mote[]>>;
}) {
  const [tick, setTick] = useState(0);
  useEffect(() => {
    const id = window.setInterval(() => setTick((t) => t + 1), 1000);
    return () => window.clearInterval(id);
  }, []);
  void tick;
  const list = motesRef.current.get(workflowType) ?? [];
  let inFlight = 0;
  let awaiting = 0;
  let exception = 0;
  for (const m of list) {
    if (m.state === "alive" || m.state === "awaiting" || m.state === "exception") {
      inFlight++;
    }
    if (m.state === "awaiting") awaiting++;
    if (m.state === "exception") exception++;
  }
  if (inFlight === 0) {
    return <span className="constellation__nav-count constellation__nav-count--zero">·</span>;
  }
  return (
    <span className="constellation__nav-count">
      {inFlight}
      {awaiting > 0 ? (
        <span style={{ color: "#d966ec", marginLeft: 4 }}>⊙{awaiting}</span>
      ) : null}
      {exception > 0 ? (
        <span style={{ color: "#f28a3d", marginLeft: 4 }}>!{exception}</span>
      ) : null}
    </span>
  );
}

// ---------------------------------------------------------------------------
// WorkflowInspector — DOM panel showing the rolling event trail of a single
// workflow. Opened by clicking a star at MID/CLOSE LOD. Polls motesRef on
// a slow tick so the trail updates while the panel is open. Auto-closes
// itself if the workflow vanishes (cluster culled it after fade-out).
// ---------------------------------------------------------------------------
function WorkflowInspector({
  workflowId,
  motesRef,
  orbits,
  onClose,
}: {
  workflowId: string;
  motesRef: React.MutableRefObject<Map<string, Mote[]>>;
  orbits: { workflowType: string; displayName: string }[];
  onClose: () => void;
}) {
  const [tick, setTick] = useState(0);
  useEffect(() => {
    const id = window.setInterval(() => setTick((t) => t + 1), 600);
    return () => window.clearInterval(id);
  }, []);
  void tick;

  // Find the mote across all clusters.
  let foundMote: Mote | null = null;
  let foundDomain: string | null = null;
  for (const o of orbits) {
    const list = motesRef.current.get(o.workflowType) ?? [];
    const m = list.find((x) => x.id === workflowId);
    if (m) {
      foundMote = m;
      foundDomain = o.displayName;
      break;
    }
  }

  if (!foundMote) {
    // Mote was culled — show a faded "ended" panel for a moment, then
    // close. We close immediately here for simplicity.
    return (
      <div className="constellation__inspector constellation__inspector--gone">
        <div className="constellation__inspector-head">
          <span className="constellation__inspector-wid">{workflowId}</span>
          <button
            type="button"
            className="constellation__inspector-close"
            onClick={onClose}
            aria-label="Close"
          >
            ×
          </button>
        </div>
        <div className="constellation__inspector-empty">
          workflow has finished and faded from the cluster
        </div>
      </div>
    );
  }

  const stateColor =
    foundMote.state === "awaiting"
      ? "#d966ec"
      : foundMote.state === "exception"
      ? "#f28a3d"
      : foundMote.state === "blocked"
      ? "#c54a3d"
      : foundMote.state === "completed"
      ? "#fff5d8"
      : "#bdbdbd";

  return (
    <div className="constellation__inspector">
      <div className="constellation__inspector-head">
        <span className="constellation__inspector-wid">{workflowId}</span>
        <span
          className="constellation__inspector-state"
          style={{ color: stateColor }}
        >
          {foundMote.state}
          {foundMote.escalated ? " · escalated" : ""}
          {foundMote.slaBreach ? " · sla breach" : ""}
        </span>
        <button
          type="button"
          className="constellation__inspector-close"
          onClick={onClose}
          aria-label="Close"
        >
          ×
        </button>
      </div>
      <div className="constellation__inspector-domain">{foundDomain}</div>
      {foundMote.state === "awaiting" && foundMote.awaitingPersona ? (
        <div className="constellation__inspector-asking">
          ⊙ asking{" "}
          <span style={{ color: "#d966ec" }}>
            {foundMote.awaitingPersona
              .split("_")
              .map((s) =>
                s.length <= 3
                  ? s.toUpperCase()
                  : s.charAt(0).toUpperCase() + s.slice(1),
              )
              .join(" ")}
          </span>
          {foundMote.awaitingReason ? (
            <span className="constellation__inspector-reason">
              {" — " + foundMote.awaitingReason.replace(/_/g, " ")}
            </span>
          ) : null}
        </div>
      ) : null}
      <div className="constellation__inspector-trail-title">recent events</div>
      <ul className="constellation__inspector-trail">
        {(foundMote.trail ?? []).length === 0 ? (
          <li className="constellation__inspector-empty">(no events yet)</li>
        ) : (
          (foundMote.trail ?? []).map((entry, i) => (
            <li
              key={`${entry.ts}-${i}`}
              className="constellation__inspector-trail-item"
            >
              <span
                className="constellation__inspector-trail-kind"
                style={{
                  color:
                    entry.kind === "tool"
                      ? "#7faed4"
                      : entry.kind === "validator"
                      ? "#c54a3d"
                      : "#f4a300",
                }}
              >
                {entry.kind === "tool"
                  ? "→"
                  : entry.kind === "validator"
                  ? "✕"
                  : "▸"}
              </span>
              <span className="constellation__inspector-trail-label">
                {entry.label}
              </span>
            </li>
          ))
        )}
      </ul>
      <div className="constellation__inspector-foot">
        progress {Math.round((foundMote.progress ?? 0) * 100)}% · esc to close
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// SSE event folding.
// ---------------------------------------------------------------------------

interface FoldCtx {
  substrate: ReturnType<typeof buildSubstrateMap>;
  /** World-space positions of every substrate dot, indexed the same as
   *  substrate.skillIdx / .toolIdx / .validatorIdx values. */
  substrateDotPositions: THREE.Vector3[];
  /** workflow_type → cluster anchor world position. Used as the arc
   *  destination so substrate→domain coupling becomes visible. */
  clusterPositions: Map<string, [number, number, number]>;
  pulsesRef: React.MutableRefObject<Pulse[]>;
  arcsRef: React.MutableRefObject<PhotonArc[]>;
  motesRef: React.MutableRefObject<Map<string, Mote[]>>;
  bornMapRef: React.MutableRefObject<Map<string, number>>;
  diedMapRef: React.MutableRefObject<Map<string, number>>;
  progressRef: React.MutableRefObject<Map<string, number>>;
  widToTypeRef: React.MutableRefObject<Map<string, string>>;
  /** display_name | workflow_type → canonical workflow_type. */
  nameToType: Map<string, string>;
  /** workflow_id prefix ("EXP", "ITAR", ...) → canonical workflow_type. */
  prefixToType: Map<string, string>;
}

/** Hard cap on simultaneously-rendered photon arcs. With the substrate
 *  centre label + dot-hover tooltip giving viewers a way to read what
 *  individual dots are, the arcs' job is reduced to "show the substrate
 *  is firing FOR these domains right now" — and fewer arcs read more
 *  cleanly than more. Oldest arcs are evicted FIFO. */
const MAX_ARCS = 20;

/** Push a photon arc from a substrate dot to a cluster anchor, FIFO-evicting
 *  the oldest if we're at the cap. Silently drops if we can't resolve the
 *  cluster (no wtype yet, or wtype not on the orbit ring). */
function pushArc(
  ctx: FoldCtx,
  dotIdx: number,
  wtype: string | null,
  now: number,
  kind: "skill" | "tool" | "validator",
): void {
  if (!wtype) return;
  const cluster = ctx.clusterPositions.get(wtype);
  if (!cluster) return;
  const from = ctx.substrateDotPositions[dotIdx];
  if (!from) return;
  if (ctx.arcsRef.current.length >= MAX_ARCS) {
    ctx.arcsRef.current.shift();
  }
  ctx.arcsRef.current.push({
    startMs: now,
    fromX: from.x,
    fromY: from.y,
    fromZ: from.z,
    toX: cluster[0],
    toY: cluster[1],
    toZ: cluster[2],
    kind,
  });
}

function handleEvent(e: ObservatoryEvent, ctx: FoldCtx): void {
  const now = performance.now();
  const wid = e.workflow_id ?? null;

  // Resolve the canonical workflow_type. Try, in order:
  //   1. e.domain → look up in nameToType (handles "Finance Compliance" →
  //      "expense-claim" AND already-canonical "expense-claim" passes through)
  //   2. workflow_id prefix → look up in prefixToType ("EXP-0773" → "expense-claim")
  //   3. cached widToType from a prior event for this workflow
  let wtype: string | null = null;
  if (e.domain) wtype = ctx.nameToType.get(e.domain) ?? null;
  if (!wtype && wid) {
    const idx = wid.indexOf("-");
    if (idx > 0) {
      const prefix = wid.slice(0, idx);
      wtype = ctx.prefixToType.get(prefix) ?? null;
    }
  }
  if (!wtype && wid) wtype = ctx.widToTypeRef.current.get(wid) ?? null;
  if (wid && wtype) ctx.widToTypeRef.current.set(wid, wtype);

  // Substrate pulses — colour by category so the legend is honest.
  // Each pulse also fires a photon arc from the substrate dot's world
  // position to the cluster anchor, so substrate↔domain coupling becomes
  // visible. Arcs are best-effort: if we don't know which cluster the
  // event belongs to (no wtype yet), we just skip the arc and keep the
  // pulse — the substrate still reads as alive.
  if (e.skill) {
    const idx = ctx.substrate.skillIdx.get(e.skill);
    if (idx !== undefined) {
      ctx.pulsesRef.current.push({ dotIdx: idx, startMs: now, kind: "skill" });
      pushArc(ctx, idx, wtype, now, "skill");
    }
  }
  if (e.tool) {
    const idx = ctx.substrate.toolIdx.get(e.tool);
    if (idx !== undefined) {
      ctx.pulsesRef.current.push({ dotIdx: idx, startMs: now, kind: "tool" });
      pushArc(ctx, idx, wtype, now, "tool");
    }
  }
  if (e.type === "durable.validator.blocked" && e.skill) {
    // Events emit validator names already snake_case ("validate_*_schema");
    // try the name as-is first, then fall back to constructing one.
    const candidates = [
      e.skill,
      `validate_${e.skill.replace(/-/g, "_")}`,
    ];
    for (const c of candidates) {
      const idx = ctx.substrate.validatorIdx.get(c);
      if (idx !== undefined) {
        ctx.pulsesRef.current.push({
          dotIdx: idx,
          startMs: now,
          kind: "validator",
        });
        pushArc(ctx, idx, wtype, now, "validator");
        break;
      }
    }
  }

  // Workflow lifecycle → stars in the matching cluster.
  if (!wid || !wtype) return;
  const list = ctx.motesRef.current.get(wtype) ?? [];
  let mote = list.find((m) => m.id === wid);
  if (!mote) {
    mote = {
      id: wid,
      lastSeenMs: now,
      workflowType: wtype,
      progress: 0.05,
      state: "alive",
      seed: hashString(wid) % 1000,
      trail: [],
    };
    list.push(mote);
    ctx.motesRef.current.set(wtype, list);
  }
  mote.lastSeenMs = now;

  // Track recent activity so close-zoom can show what each workflow is doing.
  if (e.skill) {
    mote.lastSkill = e.skill;
    mote.trail = [
      { ts: now, label: e.skill, kind: "skill" as const },
      ...(mote.trail ?? []),
    ].slice(0, 6);
  }
  if (e.tool) {
    mote.lastTool = e.tool;
    mote.trail = [
      { ts: now, label: e.tool, kind: "tool" as const },
      ...(mote.trail ?? []),
    ].slice(0, 6);
  }

  const stepCount = (ctx.progressRef.current.get(wid) ?? 0) + 1;
  ctx.progressRef.current.set(wid, stepCount);
  mote.progress = Math.min(0.05 + stepCount * 0.05, 0.95);

  // ---------------------------------------------------------------------
  // State machine. Order matters — terminal states win, then sticky
  // non-fatal states (awaiting / exception), then auto-resume.
  // ---------------------------------------------------------------------
  const isStepEvent =
    e.type === "durable.step.started" ||
    e.type === "durable.step.completed" ||
    e.type === "durable.executor.invoked" ||
    e.type === "agent.completed";

  if (
    e.type === "durable.workflow.completed" ||
    e.type === "workflow.resolved"
  ) {
    if (mote.state !== "completed") {
      mote.state = "completed";
      mote.progress = 1.0;
      ctx.diedMapRef.current.set(wid, now);
    }
  } else if (e.type === "durable.validator.blocked") {
    if (mote.state !== "blocked") {
      mote.state = "blocked";
      ctx.diedMapRef.current.set(wid, now);
    }
  } else if (
    e.type === "workflow.exception.detected" ||
    e.type === "workflow.policy.violation"
  ) {
    // Sticky orange — workflow is in trouble but not terminal. Cleared
    // when a subsequent step or durable.resumed event fires.
    if (mote.state !== "exception" && mote.state !== "blocked") {
      mote.state = "exception";
    }
  } else if (
    e.type === "workflow.hitl.requested" ||
    e.type === "durable.suspended"
  ) {
    // Sticky magenta — the bot stopped to ask a human.
    if (
      mote.state !== "awaiting" &&
      mote.state !== "blocked" &&
      mote.state !== "completed"
    ) {
      mote.state = "awaiting";
      mote.escalated = false;
    }
    // Capture who's being asked and why so the HITL satellite can render.
    if (e.persona) mote.awaitingPersona = e.persona;
    if (e.reason) mote.awaitingReason = e.reason;
  } else if (e.type === "workflow.hitl.escalated") {
    mote.state = "awaiting";
    mote.escalated = true;
    if (e.persona) mote.awaitingPersona = e.persona;
    if (e.reason) mote.awaitingReason = e.reason;
  } else if (e.type === "workflow.sla.breach_imminent") {
    mote.slaBreach = true;
  } else if (e.type === "durable.resumed" || isStepEvent) {
    // Auto-resume: any forward motion clears sticky non-fatal states +
    // the HITL satellite (the human answered, the bot moved on).
    if (mote.state === "awaiting" || mote.state === "exception") {
      mote.state = "alive";
      mote.escalated = false;
      mote.awaitingPersona = null;
      mote.awaitingReason = null;
    }
  }
}

function hashString(s: string): number {
  let h = 5381;
  for (let i = 0; i < s.length; i++) {
    h = (h * 33) ^ s.charCodeAt(i);
  }
  return Math.abs(h);
}

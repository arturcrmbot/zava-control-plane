/**
 * The Org Building (IP2, TASK-006 + IP3, TASK-013-016) — zoom-aware scene root.
 *
 * Mounts the R3F Canvas, the cosmic backdrop (matched to
 * CosmicConstellation for visual continuity), the 11-floor Building,
 * the cadence clock + status pill overlays, and an OrbitControls rig
 * with slow auto-orbit.
 *
 * Chunk 3 (IP6 TASK-031..034): when the operator zooms to a wing, the
 * non-active floors fade to ~30% opacity and the active wing's floors
 * brighten + KPI font scales up. The bottom strip gains a wing
 * indicator. Floor click → emits `org-building:zoom-to` with the
 * floor's wing target.
 */
import { OrbitControls, PerspectiveCamera, Stars } from "@react-three/drei";
import { Canvas } from "@react-three/fiber";
import { Bloom, EffectComposer } from "@react-three/postprocessing";
import { useMemo } from "react";

import { useObservatory } from "../lib/useObservatory";
import { useOrgAnimations, useOrgData } from "../lib/useOrgData";
import { useLayerToggles } from "../lib/layerToggles";
import { FLOOR_TO_WING, WINGS } from "../lib/orgWings";
import type { ZoomTarget } from "../lib/orgZoom";
import { levelForKind } from "../lib/orgZoom";
import { AnimationLayer } from "./orgBuilding/AnimationLayer";
import { Building } from "./orgBuilding/Building";
import { CadenceClock } from "./orgBuilding/CadenceClock";
import { LayerToggles } from "./orgBuilding/LayerToggles";

interface Props {
  /** Reflected on the top-left status pill. */
  status: "watching" | "connecting" | "offline";
  fullScreen?: boolean;
  /** Current zoom target (chunk-3). When `kind === 'wing'` the active
   *  wing's floors brighten and the rest dim. */
  zoomTarget?: ZoomTarget;
}

export function OrgBuilding({ status, fullScreen = false, zoomTarget }: Props) {
  const snap = useOrgData();
  const { functions, entityCounts, cadences } = snap;
  const { layers, setLayer } = useLayerToggles();
  const { entries, dispatch, beams } = useOrgAnimations(snap, layers);

  const activeWing = useMemo(() => {
    if (!zoomTarget) return null;
    if (zoomTarget.kind === "wing" && zoomTarget.id) {
      return (WINGS as Record<string, string[]>)[zoomTarget.id] ?? null;
    }
    return null;
  }, [zoomTarget]);

  const zoomLevel = zoomTarget ? levelForKind(zoomTarget.kind) : 3;

  const wrapperStyle: React.CSSProperties = fullScreen
    ? { position: "absolute", inset: 0 }
    : { position: "relative", width: "100%", height: "100%", minHeight: 640 };

  function handleFloorClick(fnName: string) {
    // At zoom-3 floor click → wing zoom (TASK-034).
    // At zoom-2 floor click → department zoom (TASK-035 entry).
    if (zoomTarget?.kind === "wing") {
      window.dispatchEvent(
        new CustomEvent("org-building:zoom-to", {
          detail: { kind: "department", id: fnName },
        }),
      );
    } else {
      const wing = FLOOR_TO_WING[fnName];
      if (!wing) return;
      window.dispatchEvent(
        new CustomEvent("org-building:zoom-to", {
          detail: { kind: "wing", id: wing },
        }),
      );
    }
  }

  return (
    <div className="org-building" style={wrapperStyle}>
      <Canvas dpr={[1, 2]} gl={{ antialias: true, alpha: false }}>
        <color attach="background" args={["#06070a"]} />
        <PerspectiveCamera makeDefault position={[0, 8, 26]} fov={45} />
        <OrbitControls
          enableDamping
          dampingFactor={0.08}
          autoRotate={zoomTarget?.kind !== "wing"}
          autoRotateSpeed={0.35}
          minDistance={6}
          maxDistance={60}
          target={[0, 5, 0]}
        />

        <ambientLight intensity={0.2} />
        <directionalLight position={[8, 14, 12]} intensity={0.55} />
        <pointLight position={[-10, 8, -8]} intensity={0.22} color="#7faed4" />

        {/* Cosmic backdrop — low-density / low-brightness so the
            building reads as the figure and the stars stay ground.
            Tuned in chunk-4 TASK-054 (was 3500@factor4). */}
        <Stars radius={140} depth={70} count={1800} factor={2.5} fade speed={0.25} />

        <Building
          functions={functions}
          entityCounts={entityCounts}
          activeWing={activeWing}
          onFloorClick={handleFloorClick}
        />

        <CadenceClock cadences={cadences} />

        {/* Live event animation overlay (chunk 2). zoomLevel drives
            mote LOD (chunk-4 TASK-052). */}
        <AnimationLayer
          entries={entries}
          beams={beams}
          onTick={(dt) => dispatch({ type: "tick", dt })}
          zoomLevel={zoomLevel}
        />

        <EffectComposer>
          <Bloom
            intensity={0.85}
            luminanceThreshold={0.18}
            luminanceSmoothing={0.85}
            mipmapBlur
          />
        </EffectComposer>
      </Canvas>

      {/* Status pill — top-left. Mirrors the CosmicConstellation HUD. */}
      <div
        className="org-building__status-pill"
        style={{
          position: "absolute",
          top: 16,
          left: 16,
          padding: "4px 10px",
          fontFamily: "var(--mono-family, monospace)",
          fontSize: 11,
          letterSpacing: "0.1em",
          textTransform: "uppercase",
          background: "rgba(10,10,12,0.65)",
          border: "1px solid rgba(207,210,214,0.25)",
          borderRadius: 999,
          color:
            status === "watching"
              ? "#5fd49d"
              : status === "connecting"
              ? "#ffd76a"
              : "#e87a5d",
          pointerEvents: "none",
          zIndex: 6,
        }}
      >
        {status === "watching"
          ? "● watching"
          : status === "connecting"
          ? "○ connecting"
          : "× offline"}
      </div>

      {/* Wing indicator — bottom strip (TASK-033). Only visible at zoom-2. */}
      {zoomTarget?.kind === "wing" && zoomTarget.id && (
        <div
          style={{
            position: "absolute",
            bottom: 16,
            left: "50%",
            transform: "translateX(-50%)",
            padding: "6px 14px",
            background: "rgba(10,10,12,0.75)",
            border: "1px solid rgba(207,210,214,0.3)",
            borderRadius: 999,
            color: "#cfd2d6",
            fontFamily: "var(--mono-family, monospace)",
            fontSize: 11,
            letterSpacing: "0.12em",
            textTransform: "uppercase",
            zIndex: 7,
            pointerEvents: "none",
          }}
        >
          Wing · <strong style={{ color: "#f5f5f7" }}>{zoomTarget.id}</strong>
        </div>
      )}

      {/* Bottom-strip layer toggles (chunk 2). */}
      <LayerToggles layers={layers} setLayer={setLayer} />
    </div>
  );
}

/**
 * Convenience wrapper that owns its own observatory subscription so the
 * page can drop ``<OrgBuildingStandalone />`` without plumbing status
 * down by hand.
 */
export function OrgBuildingStandalone({ fullScreen = true }: { fullScreen?: boolean }) {
  const { status } = useObservatory({ bufferSize: 1 });
  return <OrgBuilding status={status} fullScreen={fullScreen} />;
}

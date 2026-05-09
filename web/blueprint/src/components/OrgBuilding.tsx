/**
 * The Org Building (IP2, TASK-006 + IP3, TASK-013-016) — zoom-3 scene root.
 *
 * Mounts the R3F Canvas, the cosmic backdrop (matched to
 * CosmicConstellation for visual continuity), the 11-floor Building,
 * the cadence clock + status pill overlays, and an OrbitControls rig
 * with slow auto-orbit.
 *
 * Future zoom levels (0..2) are spec'd in chunks 2-4; this component
 * currently renders the zoom-3 view exclusively.
 */
import { OrbitControls, PerspectiveCamera, Stars } from "@react-three/drei";
import { Canvas } from "@react-three/fiber";
import { Bloom, EffectComposer } from "@react-three/postprocessing";

import { useObservatory } from "../lib/useObservatory";
import { useOrgAnimations, useOrgData } from "../lib/useOrgData";
import { useLayerToggles } from "../lib/layerToggles";
import { AnimationLayer } from "./orgBuilding/AnimationLayer";
import { Building } from "./orgBuilding/Building";
import { CadenceClock } from "./orgBuilding/CadenceClock";
import { LayerToggles } from "./orgBuilding/LayerToggles";

interface Props {
  /** Reflected on the top-left status pill. */
  status: "watching" | "connecting" | "offline";
  fullScreen?: boolean;
}

export function OrgBuilding({ status, fullScreen = false }: Props) {
  const snap = useOrgData();
  const { functions, entityCounts, cadences } = snap;
  const { layers, setLayer } = useLayerToggles();
  const { entries, dispatch, beams } = useOrgAnimations(snap, layers);

  const wrapperStyle: React.CSSProperties = fullScreen
    ? { position: "absolute", inset: 0 }
    : { position: "relative", width: "100%", height: "100%", minHeight: 640 };

  return (
    <div className="org-building" style={wrapperStyle}>
      <Canvas dpr={[1, 2]} gl={{ antialias: true, alpha: false }}>
        <color attach="background" args={["#06070a"]} />
        <PerspectiveCamera makeDefault position={[0, 8, 26]} fov={45} />
        <OrbitControls
          enableDamping
          dampingFactor={0.08}
          autoRotate
          autoRotateSpeed={0.35}
          minDistance={12}
          maxDistance={60}
          target={[0, 5, 0]}
        />

        <ambientLight intensity={0.35} />
        <directionalLight position={[8, 14, 12]} intensity={0.45} />
        <pointLight position={[-10, 8, -8]} intensity={0.25} color="#7faed4" />

        {/* Cosmic backdrop — matches CosmicConstellation aesthetic. */}
        <Stars radius={120} depth={60} count={3500} factor={4} fade speed={0.4} />

        <Building functions={functions} entityCounts={entityCounts} />

        <CadenceClock cadences={cadences} />

        {/* Live event animation overlay (chunk 2). */}
        <AnimationLayer
          entries={entries}
          beams={beams}
          onTick={(dt) => dispatch({ type: "tick", dt })}
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

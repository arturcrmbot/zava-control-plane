import { Canvas } from "@react-three/fiber";
import { OrbitControls, Stars } from "@react-three/drei";
import { Suspense } from "react";
import { HubDisc } from "./HubDisc";
import { FunctionPlanets } from "./FunctionPlanets";
import { WorkflowMoons } from "./WorkflowMoons";
import { Cities } from "./Cities";
import { Rockets } from "./Rockets";
import { useLiveCosmic } from "./lib/useLiveCosmic";

interface CosmicLensProps {
  embed?: boolean;
}

/**
 * Cosmic Lens v2 — scene root.
 *
 * Drag-to-rotate the entire scene (OrbitControls). No auto-rotation.
 * Hub at center; planets orbit; moons orbit planets; rockets fly between
 * moons and cities on the hub.
 */
export function CosmicLens({ embed: _embed }: CosmicLensProps) {
  const live = useLiveCosmic();

  return (
    <div style={{ position: "absolute", inset: 0, background: "#020617" }}>
      <Canvas
        camera={{ position: [0, 12, 22], fov: 45, near: 0.1, far: 200 }}
        dpr={[1, 1.8]}
        gl={{ antialias: true, alpha: false }}
      >
        <color attach="background" args={["#020617"]} />
        <fog attach="fog" args={["#020617", 30, 80]} />

        <ambientLight intensity={0.4} />
        <directionalLight position={[10, 16, 8]} intensity={0.9} castShadow />
        <pointLight position={[0, 6, 0]} intensity={0.6} color="#22d3ee" distance={20} />

        <Suspense fallback={null}>
          <Stars radius={80} depth={50} count={2500} factor={3} saturation={0.6} fade speed={0.4} />
          <HubDisc />
          <FunctionPlanets functions={live.functions} />
          <WorkflowMoons inFlight={live.inFlight} functions={live.functions} />
          <Cities cities={live.cities} mode={live.mode} />
          <Rockets
            flashesRef={live.flashesRef}
            inFlight={live.inFlight}
            cities={live.cities}
            functions={live.functions}
            mode={live.mode}
          />
        </Suspense>

        <OrbitControls
          enablePan={false}
          enableDamping
          dampingFactor={0.08}
          minDistance={10}
          maxDistance={45}
          maxPolarAngle={Math.PI * 0.49}
        />
      </Canvas>

      {/* Minimal status badge — Phase B/C add VitalSignsBar / ActivityRail / Drawer */}
      <div
        style={{
          position: "absolute",
          top: 16,
          left: 16,
          padding: "6px 10px",
          background: "rgba(15, 23, 42, 0.7)",
          color: live.status === "watching" ? "#4ade80" : "#fb923c",
          fontFamily: "ui-sans-serif, system-ui",
          fontSize: 12,
          borderRadius: 6,
          border: "1px solid rgba(148, 163, 184, 0.2)",
          pointerEvents: "none",
        }}
      >
        ● {live.status} · {live.inFlight.length} in-flight · {live.cities.length} cities
      </div>

      {/* Temporary burst button so we can verify rocket flow */}
      <button
        onClick={() => live.injectBurst(8)}
        style={{
          position: "absolute",
          top: 16,
          right: 16,
          padding: "8px 14px",
          background: "linear-gradient(135deg, #6366f1, #ec4899)",
          color: "white",
          border: "none",
          borderRadius: 6,
          cursor: "pointer",
          fontFamily: "ui-sans-serif, system-ui",
          fontSize: 13,
          fontWeight: 600,
        }}
      >
        ⚡ BURST 8
      </button>
    </div>
  );
}

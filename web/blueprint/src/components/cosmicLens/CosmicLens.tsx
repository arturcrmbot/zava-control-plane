import { Canvas } from "@react-three/fiber";
import { OrbitControls, Stars } from "@react-three/drei";
import { Suspense, useEffect, useMemo, useState } from "react";
import { HubDisc } from "./HubDisc";
import { FunctionPlanets } from "./FunctionPlanets";
import { WorkflowMoons } from "./WorkflowMoons";
import { Cities } from "./Cities";
import { Rockets } from "./Rockets";
import { Trails } from "./Trails";
import { EntityEdges } from "./EntityEdges";
import { DirectionalBeams } from "./DirectionalBeams";
import { RocketRegistry, TrailRegistry } from "./lib/registries";
import { useLiveCosmic } from "./lib/useLiveCosmic";
import { VitalSignsBar } from "./HUD/VitalSignsBar";
import { ActivityRail } from "./HUD/ActivityRail";
import { WorkflowDrawer, type DrawerView } from "./HUD/WorkflowDrawer";

interface CosmicLensProps {
  embed?: boolean;
}

/**
 * Cosmic Lens v2 — scene root.
 *
 * Drag-to-rotate the entire scene (OrbitControls). No auto-rotation.
 * Hub at center; planets orbit; moons orbit planets; rockets fly between
 * moons and cities on the hub. Trails fade behind rockets, building
 * operational corridors.
 */
export function CosmicLens({ embed: _embed }: CosmicLensProps) {
  const live = useLiveCosmic();
  const trailRegistry = useMemo(() => new TrailRegistry(500), []);
  const rocketRegistry = useMemo(() => new RocketRegistry(), []);
  const [drawer, setDrawer] = useState<DrawerView>({ type: null });

  // Throttle a "recent events / min" counter from flashesRef
  const [eventsPerMin, setEventsPerMin] = useState(0);
  useEffect(() => {
    let lastVersion = 0;
    let lastSampleTs = Date.now();
    const interval = setInterval(() => {
      const ref = live.flashesRef.current;
      const delta = ref.version - lastVersion;
      const elapsed = (Date.now() - lastSampleTs) / 1000;
      if (elapsed > 0) {
        setEventsPerMin((delta / elapsed) * 60);
      }
      lastVersion = ref.version;
      lastSampleTs = Date.now();
    }, 5000);
    return () => clearInterval(interval);
  }, [live.flashesRef]);

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
          <FunctionPlanets
            functions={live.functions}
            onFunctionClick={(key, label) =>
              setDrawer({ type: "function", id: key, label })
            }
          />
          <WorkflowMoons
            inFlight={live.inFlight}
            functions={live.functions}
            onMoonClick={(workflowId) => setDrawer({ type: "workflow", id: workflowId })}
          />
          <Cities
            cities={live.cities}
            mode={live.mode}
            onCityClick={(id, label) => setDrawer({ type: "city", id, label })}
          />
          <EntityEdges cities={live.cities} visible={live.mode === "entities"} />
          <Rockets
            flashesRef={live.flashesRef}
            inFlight={live.inFlight}
            cities={live.cities}
            functions={live.functions}
            mode={live.mode}
            trailRegistry={trailRegistry}
            rocketRegistry={rocketRegistry}
          />
          <Trails registry={trailRegistry} />
          <DirectionalBeams
            rocketRegistry={rocketRegistry}
            cities={live.cities}
            visible={live.mode === "entities"}
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

      <VitalSignsBar
        inFlight={live.inFlight}
        personas={live.personas}
        status={live.status}
        mode={live.mode}
        setMode={live.setMode}
        onBurst={() => live.injectBurst(8)}
        onSeed={() => live.seedKpis()}
        recentEvents={eventsPerMin}
      />

      <ActivityRail flashesRef={live.flashesRef} mode={live.mode} />

      <WorkflowDrawer
        view={drawer}
        onClose={() => setDrawer({ type: null })}
        onOpenWorkflow={(id) => setDrawer({ type: "workflow", id })}
      />
    </div>
  );
}

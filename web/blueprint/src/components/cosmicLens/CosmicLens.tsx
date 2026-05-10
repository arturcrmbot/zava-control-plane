import { Canvas } from "@react-three/fiber";
import { OrbitControls, Stars } from "@react-three/drei";
import { EffectComposer, Bloom } from "@react-three/postprocessing";
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
import { buildWorkflowTypeToFunction, resolveFunction, workflowTypeFromId } from "./lib/workflowFunction";
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

  // Compute per-function workflow load for planet glow + label.
  const loadByFunction = useMemo(() => {
    const wfTypeMap = buildWorkflowTypeToFunction(live.functions);
    const counts = new Map<string, number>();
    for (const wf of live.inFlight) {
      const wfType = wf.workflow_type || workflowTypeFromId(wf.id) || "";
      const fnKey = resolveFunction({ ...wf, workflow_type: wfType }, wfTypeMap);
      counts.set(fnKey, (counts.get(fnKey) ?? 0) + 1);
    }
    return counts;
  }, [live.inFlight, live.functions]);

  // Throttle a "recent events / min" counter from flashesRef
  const [eventsPerMin, setEventsPerMin] = useState(0);
  // Throughput: workflow.completed events per minute (sample window).
  const [throughputPerMin, setThroughputPerMin] = useState(0);
  useEffect(() => {
    let lastVersion = 0;
    let lastSampleTs = Date.now();
    let totalCompletedSeen = 0;
    const completedHistory: { ts: number; count: number }[] = [];
    const interval = setInterval(() => {
      const ref = live.flashesRef.current;
      const delta = ref.version - lastVersion;
      const elapsed = (Date.now() - lastSampleTs) / 1000;
      if (elapsed > 0) {
        setEventsPerMin((delta / elapsed) * 60);
      }
      // Count NEW completion events in the buffer
      const buffer = ref.buffer;
      const newSlice = buffer.slice(Math.max(0, buffer.length - delta));
      let completedDelta = 0;
      for (const f of newSlice) {
        if (
          f.type === "workflow.resolved" ||
          f.type === "durable.workflow.completed" ||
          f.type === "workflow.completed"
        ) completedDelta++;
      }
      totalCompletedSeen += completedDelta;
      const now = Date.now();
      completedHistory.push({ ts: now, count: totalCompletedSeen });
      const cutoff = now - 60_000;
      while (completedHistory.length && completedHistory[0].ts < cutoff) completedHistory.shift();
      if (completedHistory.length >= 2) {
        const first = completedHistory[0];
        const last = completedHistory[completedHistory.length - 1];
        const seconds = Math.max(1, (last.ts - first.ts) / 1000);
        setThroughputPerMin(((last.count - first.count) / seconds) * 60);
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
            loadByFunction={loadByFunction}
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
            personas={live.personas}
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

        <EffectComposer>
          <Bloom
            intensity={0.55}
            luminanceThreshold={0.4}
            luminanceSmoothing={0.7}
            mipmapBlur
          />
        </EffectComposer>

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
        throughputPerMin={throughputPerMin}
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

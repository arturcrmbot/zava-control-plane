import { Canvas, useThree } from "@react-three/fiber";
import { OrbitControls } from "@react-three/drei";
import { EffectComposer, Bloom } from "@react-three/postprocessing";
import { Suspense, useEffect, useMemo, useRef, useState } from "react";
import * as THREE from "three";
import { HubDisc } from "./HubDisc";
import { FunctionPlanets } from "./FunctionPlanets";
import { Cities, cityPosition } from "./Cities";
import { Rockets } from "./Rockets";
import { HoveredWorkflowPath } from "./HoveredWorkflowPath";
import { Trails } from "./Trails";
import { EntityEdges } from "./EntityEdges";
import { NebulaSky } from "./NebulaSky";
import { ExhaustRegistry, RocketExhaust } from "./RocketExhaust";
import { DirectionalBeams } from "./DirectionalBeams";
import { PlanetCompletions } from "./PlanetCompletions";
import { CameraFocus, type FocusTarget } from "./CameraFocus";
import { HUDLeftStack } from "./HUD/CollapsibleHUDShell";
import { usePanelVisibility } from "./HUD/usePanelVisibility";
import { planetBasePosition } from "./FunctionPlanets";
import { RocketRegistry, TrailRegistry } from "./lib/registries";
import { useLiveCosmic } from "./lib/useLiveCosmic";
import { buildWorkflowTypeToFunction, resolveFunction, workflowTypeFromId } from "./lib/workflowFunction";
import { VitalSignsBar } from "./HUD/VitalSignsBar";
import { ActivityRail } from "./HUD/ActivityRail";
import { WorkflowDrawer, type DrawerView } from "./HUD/WorkflowDrawer";
import { KnowledgePulse } from "./HUD/KnowledgePulse";
import { WorldSignalsPanel } from "./HUD/WorldSignalsPanel";
import { NarrativeArcs } from "./HUD/NarrativeArcs";
import { TimeScrub, type ReplaySnapshot } from "./HUD/TimeScrub";

interface CosmicLensProps {
  embed?: boolean;
}

/** Internal component — runs INSIDE Canvas so useThree works. Publishes
 *  scene / camera / renderer onto window.__cosmicScene so the introspector
 *  helpers in CosmicLens (which run OUTSIDE Canvas) can reach them. */
function SceneIntrospector() {
  const { scene, camera, gl } = useThree();
  useEffect(() => {
    (window as unknown as { __cosmicScene?: unknown }).__cosmicScene = { scene, camera, gl };
  }, [scene, camera, gl]);
  return null;
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
  const exhaustRegistry = useMemo(() => new ExhaustRegistry(), []);
  const rocketRegistry = useMemo(() => new RocketRegistry(), []);
  const [drawer, setDrawer] = useState<DrawerView>({ type: null });
  // pick which HUD panels to render — backed by localStorage. The
  // PanelPicker chip top-right is the canonical UI for toggling these.
  const panelVisibility = usePanelVisibility();
  // Camera focus on click — null = wide overview, non-null = zoomed on a
  // single city / planet / moon. ESC and background click clear it.
  const [focus, setFocus] = useState<FocusTarget | null>(null);
  // Hovered moon's workflow_id — used to highlight its rocket and
  // emphasise its trail to the current city (spec §3.3 close-up rule).
  const [hoveredMoonId, setHoveredMoonId] = useState<string | null>(null);
  // pitch-j4 — when non-null, the cosmic lens is in time-scrub replay
  // mode. The scrub HUD owns the polling; downstream components can
  // read this to switch their data source. For now we expose it via
  // window.__cosmic for tests / introspection.
  const [replaySnap, setReplaySnap] = useState<ReplaySnapshot | null>(null);
  const controlsRef = useRef<{ target: THREE.Vector3; update: () => void } | null>(null);
  useEffect(() => {
    function onKey(e: KeyboardEvent) {
      if (e.key === "Escape") {
        setFocus(null);
        setDrawer({ type: null });
      }
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);

  // ── DEV INTROSPECTION ──────────────────────────────────────────────
  // Expose live state on window.__cosmic so we can query from playwright
  // eval / devtools. Lets us answer "how many rockets alive?", "what
  // event types arrived?", "what mode am I in?" without taking screenshots.
  if (typeof window !== "undefined") {
    (window as unknown as { __cosmic: unknown }).__cosmic = {
      live,
      trailRegistry,
      rocketRegistry,
      drawer,
      // helpers
      eventTypeHistogram: () => {
        const counts: Record<string, number> = {};
        for (const f of live.flashesRef.current.buffer) {
          counts[f.type] = (counts[f.type] ?? 0) + 1;
        }
        return counts;
      },
      rocketSummary: () => {
        const phaseCounts: Record<string, number> = {};
        const cityCounts: Record<string, number> = {};
        for (const r of rocketRegistry.values()) {
          phaseCounts[r.phase] = (phaseCounts[r.phase] ?? 0) + 1;
          if (r.phase === "idle" && r.current_city_id) {
            cityCounts[r.current_city_id] = (cityCounts[r.current_city_id] ?? 0) + 1;
          }
        }
        return { total: rocketRegistry.size(), byPhase: phaseCounts, idleAtCity: cityCounts };
      },
      moonSummary: () => {
        const byFn: Record<string, number> = {};
        const wfTypeMap = buildWorkflowTypeToFunction(live.functions);
        for (const wf of live.inFlight) {
          const wfType = wf.workflow_type || workflowTypeFromId(wf.id) || "";
          const fn = resolveFunction({ ...wf, workflow_type: wfType }, wfTypeMap);
          byFn[fn] = (byFn[fn] ?? 0) + 1;
        }
        return { total: live.inFlight.length, byFunction: byFn };
      },
      // Programmatic focus for testing — sets camera to zoom on a city by id.
      focusCity: (cityId: string) => {
        const c = live.cities.find((x) => x.id === cityId);
        if (!c) return { error: `no city ${cityId}` };
        const [x, y, z] = cityPosition(cityId);
        setFocus({ target: [x, y + 0.4, z], distance: 4.0 });
        return { ok: true, target: [x, y, z] };
      },
      focusPlanet: (key: string) => {
        const [x, y, z] = planetBasePosition(key, live.functions);
        setFocus({ target: [x, y, z], distance: 5.5 });
        const fn = live.functions.find((f) => (f.name ?? f.key) === key);
        if (fn) setDrawer({ type: "function", id: key, label: fn.display ?? fn.label ?? key });
        return { ok: true, target: [x, y, z] };
      },
      unfocus: () => {
        setFocus(null);
        setDrawer({ type: null });
      },
      currentFocus: focus,
      // Programmatic hover for testing — sets the hoveredMoonId so we can
      // screenshot HoveredWorkflowPath without simulating a real mouse hover.
      hoverMoon: (workflowId: string | null) => {
        setHoveredMoonId(workflowId);
        return { ok: true, hovered: workflowId };
      },
      hoveredMoonId,
      // Real scene introspector — walks three.js scene, projects every
      // visible mesh to screen coords, returns its color/material/visibility.
      // Use this instead of taking screenshots: e.g. find the rocket at
      // world (3.2, 0.87, -1.8) and verify its material color is #facc15.
      sceneState: (filter?: string) => {
        const sceneRef = (window as unknown as { __cosmicScene?: { scene: THREE.Scene; camera: THREE.Camera } }).__cosmicScene;
        if (!sceneRef) return { error: "SceneIntrospector hasn't published yet" };
        const canvas = document.querySelector("canvas") as HTMLCanvasElement | null;
        if (!canvas) return { error: "no canvas" };
        const scene = sceneRef.scene;
        const camera = sceneRef.camera;
        const objects: unknown[] = [];
        const projVec = new THREE.Vector3();
        const wp = new THREE.Vector3();
        scene.traverse((obj: THREE.Object3D) => {
          if (!obj.visible) return;
          if (filter && !(obj.name?.includes(filter) || obj.type?.includes(filter) || (obj as { material?: { type?: string } }).material?.type?.includes(filter))) return;
          // Skip the root scene + groups with no geometry of their own
          const mesh = obj as THREE.Mesh;
          const isMesh = mesh.isMesh;
          const isInstanced = (mesh as unknown as THREE.InstancedMesh).isInstancedMesh;
          if (!isMesh && obj.type !== "Group" && obj.type !== "Line") return;
          obj.getWorldPosition(wp);
          projVec.copy(wp).project(camera);
          const sx = (projVec.x + 1) / 2 * canvas.width;
          const sy = (-projVec.y + 1) / 2 * canvas.height;
          const onScreen = Math.abs(projVec.x) <= 1 && Math.abs(projVec.y) <= 1 && projVec.z < 1;
          const mat = (mesh as unknown as { material?: THREE.Material }).material;
          const matColor = (mat as unknown as { color?: THREE.Color })?.color?.getHexString();
          const matEmissive = (mat as unknown as { emissive?: THREE.Color })?.emissive?.getHexString();
          const matVertexColors = (mat as unknown as { vertexColors?: boolean })?.vertexColors;
          const matOpacity = (mat as unknown as { opacity?: number })?.opacity;
          objects.push({
            name: obj.name || "(no-name)",
            type: obj.type,
            isInstanced,
            instanceCount: isInstanced ? (mesh as unknown as THREE.InstancedMesh).count : undefined,
            world: [Number(wp.x.toFixed(3)), Number(wp.y.toFixed(3)), Number(wp.z.toFixed(3))],
            screen: onScreen ? [Math.round(sx), Math.round(sy)] : null,
            depth: Number(projVec.z.toFixed(3)),
            material: mat?.type,
            color: matColor ? `#${matColor}` : null,
            emissive: matEmissive ? `#${matEmissive}` : null,
            vertexColors: matVertexColors,
            opacity: matOpacity,
          });
        });
        return { canvasSize: [canvas.width, canvas.height], cameraPos: [camera.position.x, camera.position.y, camera.position.z], objects };
      },
      // Same but for an InstancedMesh's individual instances — reads the
      // instanceColor + instanceMatrix attribute buffers directly so we
      // can verify what color a SPECIFIC rocket instance is rendering.
      instanceColors: (meshFilter: string) => {
        const sceneRef = (window as unknown as { __cosmicScene?: { scene: THREE.Scene; camera: THREE.Camera } }).__cosmicScene;
        if (!sceneRef) return { error: "SceneIntrospector hasn't published yet" };
        const canvas = document.querySelector("canvas") as HTMLCanvasElement | null;
        if (!canvas) return { error: "no canvas" };
        const camera = sceneRef.camera;
        const projVec = new THREE.Vector3();
        const wp = new THREE.Vector3();
        const m = new THREE.Matrix4();
        const out: unknown[] = [];
        sceneRef.scene.traverse((obj: THREE.Object3D) => {
          const im = obj as unknown as THREE.InstancedMesh;
          if (!im.isInstancedMesh) return;
          if (meshFilter && !(obj.name?.includes(meshFilter) || obj.type?.includes(meshFilter))) return;
          const colorAttr = im.instanceColor;
          const matAttr = im.instanceMatrix;
          const mat = (im as unknown as { material?: { type?: string; vertexColors?: boolean } }).material;
          const samples: unknown[] = [];
          for (let i = 0; i < Math.min(im.count, 60); i++) {
            im.getMatrixAt(i, m);
            wp.setFromMatrixPosition(m).applyMatrix4(im.matrixWorld);
            projVec.copy(wp).project(camera);
            const onScreen = Math.abs(projVec.x) <= 1 && Math.abs(projVec.y) <= 1 && projVec.z < 1 && wp.y > -10;
            let r = 0, g = 0, b = 0;
            if (colorAttr) {
              r = colorAttr.getX(i);
              g = colorAttr.getY(i);
              b = colorAttr.getZ(i);
            }
            samples.push({
              i,
              world: [Number(wp.x.toFixed(2)), Number(wp.y.toFixed(2)), Number(wp.z.toFixed(2))],
              screen: onScreen ? [Math.round((projVec.x + 1) / 2 * canvas.width), Math.round((-projVec.y + 1) / 2 * canvas.height)] : null,
              colorRGB: colorAttr ? [Number(r.toFixed(3)), Number(g.toFixed(3)), Number(b.toFixed(3))] : null,
              colorHex: colorAttr ? `#${Math.round(r * 255).toString(16).padStart(2, "0")}${Math.round(g * 255).toString(16).padStart(2, "0")}${Math.round(b * 255).toString(16).padStart(2, "0")}` : null,
            });
          }
          out.push({
            name: obj.name || "(no-name)",
            type: obj.type,
            count: im.count,
            instanceColorBuffer: !!colorAttr,
            instanceMatrixBuffer: !!matAttr,
            materialType: mat?.type,
            vertexColors: mat?.vertexColors,
            samples,
          });
        });
        return out;
      },
      // Diagnostic snapshot: returns what's actually being rendered for
      // rockets so we can verify yellow without a screenshot. The Rockets
      // component publishes its diagRef onto rocketRegistry.__diag in a
      // mount effect.
      rocketDiag: () => {
        const diag = (rocketRegistry as unknown as {
          __diag?: {
            ticks: number;
            lastDrawnCount: number;
            lastDefaultHex: string;
            instanceColorReady: boolean;
            haloInstanceColorReady: boolean;
          };
        }).__diag;
        const sample = rocketRegistry.values().slice(0, 5).map((r) => ({
          id: r.id,
          wf: r.workflow_id,
          phase: r.phase,
          city: r.current_city_id,
          is_read: r.is_read,
          is_write: r.is_write,
          is_wounded: r.is_wounded,
        }));
        return {
          registrySize: rocketRegistry.size(),
          diag: diag ?? "Rockets component has not mounted yet",
          sample,
        };
      },
    };
  }
  // ───────────────────────────────────────────────────────────────────


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
  // Parked-rocket counts by city, polled from the registry so Cities
  // can show "▲N" badges and the docked rockets are visible to operators.
  const [parkedByCity, setParkedByCity] = useState<Map<string, number>>(new Map());
  useEffect(() => {
    const interval = setInterval(() => {
      const counts = new Map<string, number>();
      for (const r of rocketRegistry.values()) {
        if (r.phase === "idle" && r.current_city_id) {
          counts.set(r.current_city_id, (counts.get(r.current_city_id) ?? 0) + 1);
        }
      }
      setParkedByCity(counts);
    }, 500);
    return () => clearInterval(interval);
  }, [rocketRegistry]);
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
      // Count NEW step-completion events in the buffer. Many workflows
      // park indefinitely at HITL gates so workflow-level completions can
      // be rare; step completions are a more honest "is the system doing
      // work right now" signal.
      const buffer = ref.buffer;
      const newSlice = buffer.slice(Math.max(0, buffer.length - delta));
      let completedDelta = 0;
      for (const f of newSlice) {
        if (
          f.type === "workflow.resolved" ||
          f.type === "durable.workflow.completed" ||
          f.type === "workflow.completed" ||
          f.type === "durable.step.completed"
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

  // B1: render the always-on substrate heartbeat — fleet.tick → hub pulse,
  // kpi.published → planet glow, ambient.decided → planet glow (city
  // sparkle deferred — ambient decisions don't carry a city id directly).
  const [lastFleetTickAt, setLastFleetTickAt] = useState(0);
  const planetGlowRef = useRef<Map<string, number>>(new Map());
  useEffect(() => {
    let lastVersion = 0;
    const interval = setInterval(() => {
      const ref = live.flashesRef.current;
      if (ref.version === lastVersion) return;
      const newCount = Math.max(1, Math.min(ref.buffer.length, ref.version - lastVersion));
      const tail = ref.buffer.slice(ref.buffer.length - newCount);
      lastVersion = ref.version;
      let sawTick = false;
      for (const f of tail) {
        if (f.type === "fleet.tick") {
          sawTick = true;
        } else if (f.type === "kpi.published" && f.function) {
          planetGlowRef.current.set(f.function, Date.now());
        } else if (f.type === "ambient.decided") {
          const fnKey = (f as unknown as { function?: string }).function;
          if (fnKey) planetGlowRef.current.set(fnKey, Date.now());
        }
      }
      if (sawTick) setLastFleetTickAt(Date.now());
    }, 100);
    return () => clearInterval(interval);
  }, [live.flashesRef]);

  return (
    <div style={{ position: "absolute", inset: 0, background: "#020617" }}>
      <Canvas
        camera={{ position: [0, 16, 26], fov: 45, near: 0.1, far: 200 }}
        dpr={[1, 1.8]}
        gl={{ antialias: true, alpha: false }}
      >
        <color attach="background" args={["#020617"]} />
        <fog attach="fog" args={["#0b0d2c", 30, 80]} />

        <ambientLight intensity={0.4} />
        <directionalLight position={[10, 16, 8]} intensity={0.9} castShadow />
        <pointLight position={[0, 6, 0]} intensity={0.6} color="#22d3ee" distance={20} />

        <Suspense fallback={null}>
          <NebulaSky />
          <HubDisc lastFleetTickAt={lastFleetTickAt} />
          <SceneIntrospector />
          <FunctionPlanets
            functions={live.functions}
            loadByFunction={loadByFunction}
            onFunctionClick={(key, label) => {
              // Zoom to the planet AND open the function drawer (workflow list).
              // Drawer makes sense here since planets are the main filter axis.
              const [x, y, z] = planetBasePosition(key, live.functions);
              setFocus({ target: [x, y, z], distance: 5.5 });
              setDrawer({ type: "function", id: key, label });
            }}
          />
          <Cities
            cities={live.cities}
            mode={live.mode}
            personas={live.personas}
            parkedRocketsByCity={parkedByCity}
            flashesRef={live.flashesRef}
            onCityClick={(id, lbl) => {
              // Click city = zoom in PLUS open the right-hand inspector
              // drawer. The drawer renders a CapabilityView (capabilities
              // mode) or per-kind EntityView (entities mode) so the user
              // can see what the clicked thing is, what it does, who's
              // parked there, etc.
              const [x, y, z] = cityPosition(id);
              setFocus({ target: [x, y + 0.4, z], distance: 4.0 });
              setDrawer({ type: "city", id, label: lbl });
            }}
          />
          <EntityEdges cities={live.cities} visible={live.mode === "entities"} />
          <Rockets
            flashesRef={live.flashesRef}
            inFlight={live.inFlight}
            cities={live.cities}
            functions={live.functions}
            mode={live.mode}
            trailRegistry={trailRegistry}
            exhaustRegistry={exhaustRegistry}
            rocketRegistry={rocketRegistry}
            highlightWorkflowId={hoveredMoonId}
            onRocketHover={setHoveredMoonId}
            onRocketClick={(rocket) => {
              const eid = (rocket as unknown as { last_entity_id?: string }).last_entity_id;
              if (live.mode === "entities" && eid) {
                setDrawer({ type: "entity", id: eid });
              } else {
                setDrawer({ type: "workflow", id: rocket.workflow_id });
              }
            }}
          />
          <HoveredWorkflowPath
            workflowId={hoveredMoonId}
            inFlight={live.inFlight}
            functions={live.functions}
            rocketRegistry={rocketRegistry}
          />
          <Trails registry={trailRegistry} />
          <RocketExhaust registry={exhaustRegistry} />
          <DirectionalBeams
            rocketRegistry={rocketRegistry}
            cities={live.cities}
            visible={live.mode === "entities"}
          />
          <PlanetCompletions
            flashesRef={live.flashesRef}
            inFlight={live.inFlight}
            functions={live.functions}
          />
          <CameraFocus
            focus={focus}
            overviewPosition={[0, 16, 26]}
            overviewTarget={[0, 1, 0]}
            controlsRef={controlsRef}
          />
        </Suspense>

        <EffectComposer>
          <Bloom
            intensity={0.14}
            luminanceThreshold={0.85}
            luminanceSmoothing={0.5}
            mipmapBlur
          />
        </EffectComposer>

        <OrbitControls
          ref={controlsRef as unknown as React.MutableRefObject<null>}
          enablePan={false}
          enableDamping
          dampingFactor={0.08}
          minDistance={3}
          maxDistance={45}
          maxPolarAngle={Math.PI * 0.49}
        />
      </Canvas>

      {/* Cast — the only collapsible left-stack panel that survived the
       *  audit. Agency KPIs (mostly mocked), What's New (routing-noise
       *  dev plumbing) and Network Effects (perpetually-empty subsections)
       *  were removed under the 'less is more' demo cleanup. */}
      <HUDLeftStack>
        {panelVisibility.visible("narrative-arcs") && <NarrativeArcs />}
      </HUDLeftStack>

      {/* VitalSignsBar is always rendered: it hosts the PanelPicker chip,
          which is the only way to toggle the other HUD panels. Hiding it
          would strand the user with no escape hatch. */}
      <VitalSignsBar
        inFlight={live.inFlight}
        personas={live.personas}
        status={live.status}
        mode={live.mode}
        setMode={live.setMode}
        onBurst={() => live.injectBurst(8)}
        recentEvents={eventsPerMin}
        throughputPerMin={throughputPerMin}
      />

      {panelVisibility.visible("time-scrub") && (
        <TimeScrub onSnapshot={setReplaySnap} />
      )}
      {replaySnap && (
        <div
          data-testid="replay-banner"
          style={{
            position: "absolute",
            bottom: 64,
            left: "50%",
            transform: "translateX(-50%)",
            zIndex: 26,
            padding: "4px 12px",
            background: "rgba(245,158,11,0.18)",
            border: "1px solid rgba(245,158,11,0.55)",
            color: "#fcd34d",
            borderRadius: 4,
            fontSize: 11,
            fontFamily: "ui-sans-serif, system-ui",
          }}
        >
          replay · {replaySnap.entities.length} entities · {replaySnap.in_flight_workflows.length} in-flight
        </div>
      )}

      {panelVisibility.visible("activity-rail") && (
        <ActivityRail
          flashesRef={live.flashesRef}
          mode={live.mode}
          inFlight={live.inFlight}
          functions={live.functions}
          onFunctionClick={(key, label) => setDrawer({ type: "function", id: key, label })}
        />
      )}

      <WorkflowDrawer
        view={drawer}
        onClose={() => {
          setDrawer({ type: null });
          setFocus(null); // unfocus camera too when drawer closed
        }}
        onOpenWorkflow={(id) => setDrawer({ type: "workflow", id })}
        onOpenEntity={(id) => setDrawer({ type: "entity", id })}
        flashesRef={live.flashesRef}
      />

      {live.mode === "entities" && panelVisibility.visible("knowledge-pulse") && (
        <KnowledgePulse
          pulse={live.pulse}
          flashesRef={live.flashesRef}
          onOpenEntity={(id) => setDrawer({ type: "entity", id })}
        />
      )}

      {/* World simulator live readout — self-hides when the engine is off. */}
      <WorldSignalsPanel />

      {/* Back-to-overview button — visible whenever camera is focused. */}
      {focus && (
        <button
          onClick={() => {
            setFocus(null);
            setDrawer({ type: null });
          }}
          style={{
            position: "absolute",
            top: 70,
            left: 16,
            zIndex: 30,
            padding: "8px 14px",
            background: "rgba(15,23,42,0.92)",
            color: "#cbd5e1",
            border: "1px solid rgba(99,102,241,0.5)",
            borderRadius: 6,
            cursor: "pointer",
            fontSize: 12,
            fontWeight: 500,
            fontFamily: "ui-sans-serif, system-ui",
            boxShadow: "0 0 12px rgba(99,102,241,0.3)",
          }}
          title="Press ESC to return"
        >
          ← back to overview
        </button>
      )}
    </div>
  );
}

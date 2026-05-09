/**
 * Glass Tower — the agentic org as a living building.
 *
 * Scene composition:
 *   - 11 stacked floors (CEO penthouse + 9 functions + lobby base)
 *   - Each floor is a glass slab; you can see desks + persona avatars inside
 *   - Workflows are glowing cyan motes that travel from the lobby UP to the
 *     correct floor, sit at a persona desk, then return as a green/red
 *     decision-tag back down to the lobby
 *   - Lobby has a "decision pool" that grows with recent decisions
 *   - HUD: top vital-signs bar + bottom strip with persona snapshot
 */
import { Canvas, useFrame } from "@react-three/fiber";
import { OrbitControls, PerspectiveCamera, Stars, Text } from "@react-three/drei";
import { Bloom, EffectComposer } from "@react-three/postprocessing";
import { useMemo, useRef } from "react";
import * as THREE from "three";

import { useLiveOrg } from "../../lib/useLiveOrg";
import type {
  FunctionSpec,
  InFlightWorkflow,
  PersonaRow,
  RecentDecision,
} from "../../lib/useLiveOrg";
import { Floor } from "./Floor";
import { Lobby } from "./Lobby";
import { WorkflowMotes } from "./WorkflowMotes";
import { DecisionPool } from "./DecisionPool";
import { ElevatorShaft } from "./ElevatorShaft";
import { VitalSignsBar } from "./VitalSignsBar";
import { PersonaStrip } from "./PersonaStrip";

const FLOOR_ORDER_BOTTOM_UP: string[] = [
  // Lobby is rendered separately at y=0
  "customer-success",
  "data",
  "tech",
  "marketing",
  "legal",
  "ops",
  "hr",
  "revenue",
  "finance",
  "ceo",
];

interface Props {
  status: "watching" | "connecting" | "offline";
}

export function GlassTower({ status }: Props) {
  const live = useLiveOrg();
  const { functionByName, inFlight, personas, recentDecisions, vital, flashesRef } = live;

  // Y-position per function (lobby = 0; floors stack upward, height 1.2 each).
  const floorY = useMemo(() => {
    const m = new Map<string, number>();
    let cursor = 1.4; // lobby is 1.0 tall, gap 0.4
    for (const name of FLOOR_ORDER_BOTTOM_UP) {
      m.set(name, cursor);
      cursor += 1.2;
    }
    return m;
  }, []);

  // workflows partitioned by function so each Floor renders its own desks.
  const inFlightByFn = useMemo(() => {
    const m = new Map<string, InFlightWorkflow[]>();
    for (const w of inFlight) {
      const fn = w.function ?? "ops";
      if (!m.has(fn)) m.set(fn, []);
      m.get(fn)!.push(w);
    }
    return m;
  }, [inFlight]);

  const personaByRole = useMemo(() => {
    const m = new Map<string, PersonaRow>();
    for (const p of personas) m.set(p.role, p);
    return m;
  }, [personas]);

  return (
    <div style={{ position: "absolute", inset: 0, background: "#04050a" }}>
      <Canvas dpr={[1, 2]} gl={{ antialias: true, alpha: false }}>
        <color attach="background" args={["#04050a"]} />
        <fog attach="fog" args={["#04050a", 28, 70]} />
        <PerspectiveCamera makeDefault position={[14, 9, 18]} fov={42} />
        <OrbitControls
          enableDamping
          dampingFactor={0.08}
          autoRotate={false}
          minDistance={6}
          maxDistance={70}
          target={[0, 7, 0]}
          maxPolarAngle={Math.PI / 2.05}
        />

        {/* Lighting — warm key from above-front, cool fill from behind. */}
        <ambientLight intensity={0.18} />
        <directionalLight position={[10, 18, 10]} intensity={0.55} color="#fff3d6" />
        <directionalLight position={[-12, 6, -10]} intensity={0.25} color="#7faed4" />
        <pointLight position={[0, 14, 0]} intensity={0.4} color="#ffd76a" distance={40} />

        <Stars radius={140} depth={70} count={2000} factor={2.2} fade speed={0.2} />

        {/* Lobby base. */}
        <Lobby
          y={0}
          inFlightCount={vital.in_flight}
          recentDecisions={recentDecisions}
        />

        {/* Function floors. */}
        {FLOOR_ORDER_BOTTOM_UP.map((fnName) => {
          const fn = functionByName.get(fnName);
          if (!fn) return null;
          const y = floorY.get(fnName) ?? 1;
          const fnInFlight = inFlightByFn.get(fnName) ?? [];
          return (
            <Floor
              key={fnName}
              fn={fn}
              y={y}
              isPenthouse={fnName === "ceo"}
              inFlight={fnInFlight}
              personaByRole={personaByRole}
              flashesRef={flashesRef}
            />
          );
        })}

        {/* Workflow motes traveling lobby → desk → lobby. */}
        <WorkflowMotes
          inFlight={inFlight}
          floorY={floorY}
          flashesRef={flashesRef}
        />

        {/* Glowing back-shaft. Visual hint that workflows travel up. */}
        <ElevatorShaft flashesRef={flashesRef} />

        {/* Decision pool — receipts flying down from desks. */}
        <DecisionPool
          flashesRef={flashesRef}
          floorY={floorY}
        />

        <EffectComposer>
          <Bloom
            intensity={0.9}
            luminanceThreshold={0.2}
            luminanceSmoothing={0.85}
            mipmapBlur
          />
        </EffectComposer>
      </Canvas>

      {/* HUDs. */}
      <VitalSignsBar status={status} vital={vital} />
      <PersonaStrip personas={personas} />
    </div>
  );
}

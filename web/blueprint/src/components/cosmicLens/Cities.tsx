import { useEffect, useMemo, useRef, useState } from "react";
import { Html } from "@react-three/drei";
import { useFrame } from "@react-three/fiber";
import * as THREE from "three";
import type { CityMeta, CosmicFlash, CosmicMode, PersonaState } from "./lib/types";
import { colorForKind, colorForEntityType } from "./lib/colors";
import { prettyActor, humanWorkflowType } from "../../../../shared/humanize";
import {
  aggregateCities,
  applyLod,
  LOD_DISTANCE_THRESHOLD,
  type AggregatableCity,
} from "./lib/cityAggregation";
import { entityGeomFor } from "./EntityShape";

interface CitiesProps {
  cities: CityMeta[];
  mode: CosmicMode;
  personas?: PersonaState[];
  /** Map of city_id → number of rockets currently parked there. */
  parkedRocketsByCity?: Map<string, number>;
  onCityClick?: (id: string, label: string) => void;
  /** Flash buffer used to pulse cities on entity-event arrival. */
  flashesRef?: React.MutableRefObject<{ buffer: CosmicFlash[]; version: number }>;
}

const CITY_RADIUS = 0.18;
const DISC_RADIUS = 7.2;
const HUB_TOP_Y = 0.42;

/** Compute deterministic random position on the disc surface for a city id.
 *  Exported so Rockets and other consumers reach the same coordinate. */
export function cityPosition(id: string): [number, number, number] {
  let hash = 5381;
  for (let i = 0; i < id.length; i++) {
    hash = ((hash << 5) + hash + id.charCodeAt(i)) | 0;
  }
  const rNorm = (Math.abs(hash) % 1000) / 1000;
  const tNorm = (Math.abs(hash >> 8) % 1000) / 1000;
  const r = Math.sqrt(rNorm) * DISC_RADIUS; // sqrt for even areal distribution
  const angle = tNorm * Math.PI * 2;
  return [Math.cos(angle) * r, HUB_TOP_Y, Math.sin(angle) * r];
}

/**
 * Cities scattered on the disc surface.
 *
 * Each city = sphere + halo. HITL personas always show their pending-count
 * badge. Every city shows a permanent dim label so the operator can read
 * the topology; on hover the label expands and the city pulls forward
 * (per spec §"Visual conventions / hover").
 */
export function Cities({ cities, mode, personas, parkedRocketsByCity, onCityClick, flashesRef }: CitiesProps) {
  // Camera-distance-driven LOD. We sample the camera position each frame
  // but only mutate state when we cross the threshold, so the React tree
  // doesn't re-render on every frame. The threshold is exposed as
  // `LOD_DISTANCE_THRESHOLD` in cityAggregation.ts.
  const [lodActive, setLodActive] = useState(false);
  const lodActiveRef = useRef(false);
  useFrame(({ camera }) => {
    const dist = camera.position.length(); // hub origin is (0,0,0)
    const next = dist > LOD_DISTANCE_THRESHOLD;
    if (next !== lodActiveRef.current) {
      lodActiveRef.current = next;
      setLodActive(next);
    }
  });

  const renderedCities = useMemo(() => {
    const aggregated = aggregateCities(cities as AggregatableCity[]);
    return applyLod(aggregated, lodActive ? LOD_DISTANCE_THRESHOLD + 1 : 0);
  }, [cities, lodActive]);

  const pendingByPersona = useMemo(() => {
    const m = new Map<string, number>();
    if (personas) {
      for (const p of personas) {
        if ((p.pending_count ?? 0) > 0) m.set(p.role, p.pending_count);
      }
    }
    return m;
  }, [personas]);

  // Track per-kind last-touch timestamps for entity-mode pulse.
  const lastTouchRef = useRef<Map<string, number>>(new Map());
  useEffect(() => {
    if (mode !== "entities" || !flashesRef) return;
    const iv = setInterval(() => {
      const buf = flashesRef.current.buffer;
      const recent = buf.slice(-20);
      for (const f of recent) {
        if (f.type === "entity.read" || f.type === "entity.upserted" || f.type === "entity.linked") {
          const k = (f as unknown as { kind?: string }).kind;
          if (k) lastTouchRef.current.set(k, Date.now());
        }
      }
    }, 200);
    return () => clearInterval(iv);
  }, [mode, flashesRef]);

  const positioned = useMemo(() => {
    return renderedCities.map((city) => {
      const [x, y, z] = cityPosition(city.id);
      // In entities mode the API marks each city's `kind` as "entity_type"
      // and stuffs the actual Kuzu node kind name into `id` ("Person",
      // "Organisation", "Decision" …). Both the colour palette and the
      // per-kind 3D shape lookup need that real kind name, not the marker.
      const entityKind = city.kind === "entity_type" ? city.id : city.kind;
      const color =
        mode === "entities" ? colorForEntityType(entityKind) : colorForKind(city.kind);
      const pending = city.kind === "persona" ? pendingByPersona.get(city.id) ?? 0 : 0;
      // Hot personas pulse with a brighter halo + bigger size
      const sizeBoost = pending > 0 ? Math.min(2.0, 1 + pending * 0.2) : 1;
      const parked = parkedRocketsByCity?.get(city.id) ?? 0;
      return {
        ...city,
        x,
        y,
        z,
        color,
        entityKind,
        pending,
        sizeBoost,
        parked,
        count: city.count,
        active: city.active,
      };
    });
  }, [renderedCities, mode, pendingByPersona, parkedRocketsByCity]);

  if (positioned.length === 0) return <PlaceholderRing />;

  return (
    <group>
      {positioned.map((c) => (
        <CityNode key={c.id} city={c} onCityClick={onCityClick} mode={mode} lastTouchRef={lastTouchRef} />
      ))}
    </group>
  );
}

interface CityNodeData {
  id: string;
  label: string;
  kind: string;
  /** Resolved entity kind in entities mode (e.g. "Person"). Falls back to
   *  `kind` when the city's kind isn't the "entity_type" marker. Used to
   *  pick both colour and 3D shape. */
  entityKind: string;
  x: number;
  y: number;
  z: number;
  color: string;
  pending: number;
  sizeBoost: number;
  parked: number;
  count?: number;
  active?: boolean;
}

function CityNode({
  city: c,
  onCityClick,
  mode,
  lastTouchRef,
}: {
  city: CityNodeData;
  onCityClick?: (id: string, label: string) => void;
  mode: CosmicMode;
  lastTouchRef: React.MutableRefObject<Map<string, number>>;
}) {
  const [hover, setHover] = useState(false);
  // Persist "recently active" state for ~12s after activity stops, so labels
  // don't flicker off the second a parked rocket departs (the user is still
  // looking at that area; flashing labels make the scene feel unstable).
  const [recentlyActive, setRecentlyActive] = useState(false);
  const lastActiveAtRef = useRef<number>(0);
  useEffect(() => {
    if (c.pending > 0 || c.parked > 0) {
      lastActiveAtRef.current = Date.now();
      if (!recentlyActive) setRecentlyActive(true);
      return;
    }
    if (lastActiveAtRef.current === 0) return;
    const gracePeriodMs = 12_000;
    const elapsed = Date.now() - lastActiveAtRef.current;
    const remaining = Math.max(0, gracePeriodMs - elapsed);
    if (remaining === 0) {
      if (recentlyActive) setRecentlyActive(false);
      return;
    }
    const timer = setTimeout(() => {
      // Re-check inside the timer: activity may have resumed between
      // scheduling and firing. Without this guard the label flickers off
      // even when the city is still busy.
      if (Date.now() - lastActiveAtRef.current >= gracePeriodMs) {
        setRecentlyActive(false);
      }
    }, remaining);
    return () => clearTimeout(timer);
  }, [c.pending, c.parked, recentlyActive]);

  // Hover lifts the city + brightens it. Per-spec the city "pulls forward".
  const liftedY = hover ? c.y + 0.25 : c.y;
  const meshScale = c.sizeBoost * (hover ? 1.6 : 1);
  // Label policy:
  //   - In ENTITIES mode: keep labels always-visible for the 13 entity-type
  //     anchors (there are only 13 of them — the labels ARE the legend).
  //   - In CAPABILITIES mode: labels are HOVER-ONLY by default (per user
  //     feedback — 110 cities of permanent labels was visual noise). The
  //     ONLY exception is personae with pending HITL work — those keep
  //     their labels so you can see at a glance who's blocking the queue.
  const isPersona = c.kind === "persona";
  const isEntityType = c.kind === "entity_type";
  const labelAlwaysVisible =
    isEntityType ||
    (isPersona && c.pending > 0);
  const showLabel = hover || labelAlwaysVisible;
  const [, setPulseTick] = useState(0);
  useEffect(() => {
    if (mode !== "entities") return;
    const iv = setInterval(() => setPulseTick(t => (t + 1) % 1000), 100);
    return () => clearInterval(iv);
  }, [mode]);

  // Persona cities arrive with a raw role id as their label (see
  // `_gather_personas` in api/server/routes/cities.py). Route them through
  // `prettyActor()` so role ids like `cpo` / `gc` / `fpa_analyst` render as
  // the job title from `PERSONA_LABELS` rather than the ugly title-cased
  // snake_case that `formatCityLabel` would produce.
  // Workflow cities (entity-mode) carry either the kind name "Workflow" or,
  // once aggregated by workflow_type, an id like "hiring" / "vendor-kyc".
  // Route them through `humanWorkflowType()` so they read as "Hiring" /
  // "Vendor KYC" instead of being lossily title-cased by `formatCityLabel`.
  const isWorkflowCity =
    mode === "entities" && (c.id === "Workflow" || c.label === "Workflow");
  const baseLabel =
    c.kind === "persona"
      ? prettyActor(c.label)
      : isWorkflowCity
      ? humanWorkflowType(c.id)
      : formatCityLabel(c.label);
  const labelText =
    c.count !== undefined && c.count > 0 ? `${baseLabel} · ${c.count}` : baseLabel;

  // Entity-mode rocket-arrival pulse: brighten emissive briefly.
  const touched = mode === "entities" ? lastTouchRef.current.get(c.id) ?? 0 : 0;
  const sinceTouched = touched > 0 ? Date.now() - touched : Infinity;
  const pulse = sinceTouched < 600 ? 1 - sinceTouched / 600 : 0;
  const emissiveBoost = pulse * 0.6;

  return (
    <group position={[c.x, liftedY, c.z]}>
      {/* Body geometry — picks a per-kind primitive in BOTH modes:
          - Entities mode: Kuzu node kind (Person/Decision/Brand/…) — see
            entityGeomFor for the 13 distinct shapes.
          - Capabilities mode: persona = capsule (the holographic
            standing-figure forest), mcp = hex prism (docking station),
            skill = dodecahedron (chunk of compiled logic), validator =
            torus ring (gatekeeper scanner). */}
      <RotatingShapeGroup
        scale={meshScale}
        rotateForKind={c.kind}
        mode={mode}
        seed={c.id}
      >
        <mesh
          onClick={(e) => {
            e.stopPropagation();
            onCityClick?.(c.id, c.label);
          }}
          onPointerOver={(e) => {
            e.stopPropagation();
            document.body.style.cursor = "pointer";
            setHover(true);
          }}
          onPointerOut={() => {
            document.body.style.cursor = "default";
            setHover(false);
          }}
        >
          {mode === "entities" ? (
            <primitive object={entityGeomFor(c.entityKind)} attach="geometry" />
          ) : (
            <primitive object={entityGeomFor(c.kind)} attach="geometry" />
          )}
          <meshStandardMaterial
            color={c.color}
            emissive={c.color}
            emissiveIntensity={(c.pending > 0 ? 1.6 : hover ? 1.5 : 1.0) + emissiveBoost}
            metalness={0.2}
            roughness={0.4}
            opacity={c.active === false ? 0.35 : 1.0}
            transparent={c.active === false}
          />
        </mesh>
      </RotatingShapeGroup>
      {/* Halo */}
      <mesh scale={meshScale}>
        <sphereGeometry args={[CITY_RADIUS * 1.8, 10, 10]} />
        <meshBasicMaterial
          color={c.color}
          transparent
          opacity={hover ? 0.45 : c.pending > 0 ? 0.35 : 0.18}
        />
      </mesh>
      {/* Holographic projector base — small additive ring at floor level
          that reads as 'this hologram is being projected from here'. Pulses
          subtly on cities that are currently busy (pending > 0 or hovered). */}
      <mesh scale={meshScale} rotation={[Math.PI / 2, 0, 0]} position={[0, -CITY_RADIUS * 1.2, 0]}>
        <ringGeometry args={[CITY_RADIUS * 0.9, CITY_RADIUS * 1.4, 24]} />
        <meshBasicMaterial
          color={c.color}
          transparent
          opacity={(c.pending > 0 || hover ? 0.55 : 0.22) + pulse * 0.3}
          blending={THREE.AdditiveBlending}
          depthWrite={false}
          side={THREE.DoubleSide}
        />
      </mesh>
      {/* Pending count badge above HITL persona cities */}
      {c.pending > 0 && (
        <Html
          position={[0, CITY_RADIUS * meshScale + 0.18, 0]}
          center
          style={{
            pointerEvents: "none",
            color: "#fff",
            fontSize: 10,
            fontWeight: 700,
            background: c.color,
            borderRadius: 999,
            padding: "1px 6px",
            whiteSpace: "nowrap",
            fontFamily: "ui-sans-serif, system-ui",
            boxShadow: `0 0 8px ${c.color}`,
            textShadow: "0 0 2px rgba(0,0,0,0.5)",
          }}
        >
          {c.pending}
        </Html>
      )}
      {/* Parked-rocket count chip (cool-coloured cities that have docked work) */}
      {c.parked > 0 && c.pending === 0 && (
        <Html
          position={[0, CITY_RADIUS * meshScale + 0.18, 0]}
          center
          style={{
            pointerEvents: "none",
            color: c.color,
            fontSize: 9,
            fontWeight: 600,
            background: "rgba(2,6,23,0.85)",
            border: `1px solid ${c.color}80`,
            borderRadius: 999,
            padding: "0px 5px",
            whiteSpace: "nowrap",
            fontFamily: "ui-sans-serif, system-ui",
          }}
        >
          ▲{c.parked}
        </Html>
      )}
      {/* City name label — visible on hover, on busy cities, and on HITL queues. */}
      {showLabel && (
        <Html
          position={[0, -(CITY_RADIUS * meshScale + 0.16), 0]}
          center
          style={{
            pointerEvents: "none",
            color: hover ? "#f1f5f9" : "rgba(226,232,240,0.65)",
            fontSize: hover ? 11 : 9,
            fontWeight: hover ? 600 : 500,
            background: hover ? "rgba(2,6,23,0.92)" : "rgba(2,6,23,0.6)",
            padding: hover ? "2px 8px" : "1px 5px",
            borderRadius: 4,
            border: `1px solid ${hover ? c.color : c.color + "40"}`,
            whiteSpace: "nowrap",
            fontFamily: "ui-sans-serif, system-ui",
            letterSpacing: 0.2,
            transition: "all 0.15s ease-out",
          }}
        >
          {labelText}
        </Html>
      )}
    </group>
  );
}

/** City labels can be ugly (snake_case ids). Make them readable. */
function formatCityLabel(s: string): string {
  return s
    .replace(/[_\-]/g, " ")
    .replace(/\bmcp\b/gi, "MCP")
    .replace(/\bhitl\b/gi, "HITL")
    .replace(/\bid\b/gi, "ID")
    .replace(/\bbp\b/gi, "BP")
    .replace(/\bhr\b/gi, "HR")
    .replace(/\bit\b/gi, "IT")
    .replace(/\bui\b/gi, "UI")
    .replace(/\bdpo\b/gi, "DPO")
    .replace(/\bcfo\b/gi, "CFO");
}

/** A simple ring of placeholder dots so the hub doesn't look empty before /api/cities returns. */
function PlaceholderRing() {
  const dots = 30;
  const items = [];
  for (let i = 0; i < dots; i++) {
    const angle = (i / dots) * Math.PI * 2;
    const r = 5.5;
    const x = Math.cos(angle) * r;
    const z = Math.sin(angle) * r;
    items.push(
      <mesh key={i} position={[x, HUB_TOP_Y, z]}>
        <sphereGeometry args={[0.1, 8, 8]} />
        <meshBasicMaterial color="#475569" transparent opacity={0.5} />
      </mesh>,
    );
  }
  return <group>{items}</group>;
}

/** Wraps a group with optional slow Y-rotation. Used to spin the chunky
 *  faceted shapes (Decision icosahedron, Asset octahedron, Brand diamond,
 *  MCP hex prism, Skill dodecahedron) so their facets read. Persona
 *  capsules (in BOTH modes — Person in entities mode, persona in
 *  capabilities mode) stay still — a standing figure shouldn't spin. */
function RotatingShapeGroup({
  children,
  scale,
  rotateForKind,
  mode,
  seed,
}: {
  children: React.ReactNode;
  scale: number;
  rotateForKind: string;
  mode: CosmicMode;
  seed: string;
}) {
  const ref = useRef<THREE.Group>(null);
  const seedNum = useMemo(() => {
    let h = 0;
    for (let i = 0; i < seed.length; i++) h = (h * 31 + seed.charCodeAt(i)) | 0;
    return h >>> 0;
  }, [seed]);
  const speed = 0.18 + ((seedNum >> 4) % 100) / 1000; // 0.18 .. 0.28 rad/s
  const phase = ((seedNum % 1000) / 1000) * Math.PI * 2;

  // Persona capsules stay still in BOTH modes — they're meant to read as
  // 'people standing on the deck'. Everything else (faceted entity kinds
  // in entities mode, mcp/skill/validator in capabilities mode) spins
  // slowly so its silhouette is felt rather than guessed.
  const isStillStanding =
    rotateForKind === "persona" ||
    (mode === "entities" && rotateForKind === "Person");
  const shouldRotate = !isStillStanding;

  useFrame((state) => {
    if (!ref.current || !shouldRotate) return;
    ref.current.rotation.y = phase + state.clock.elapsedTime * speed;
  });
  return (
    <group ref={ref} scale={scale}>
      {children}
    </group>
  );
}

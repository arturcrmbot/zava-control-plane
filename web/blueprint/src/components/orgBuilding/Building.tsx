/**
 * The Org Building (IP3, TASK-010 + TASK-013 + TASK-014) — 3D skyscraper.
 *
 * Eleven stacked floors, top-down:
 *   ceo (penthouse, smaller + brighter)
 *   finance
 *   revenue
 *   hr
 *   ops
 *   legal
 *   marketing
 *   tech
 *   data
 *   customer-success
 *   lobby (entity-counts row, wider than the other floors)
 *
 * Each function floor carries: a translucent slab, a coloured backdrop
 * accent, a text label, a KPI ticker on the facade, and a row of
 * instanced windows. The lobby renders 7 small kind-icon meshes (one
 * per entity kind) labelled with the live count.
 *
 * Driven by ``useOrgData`` (poll: 5s) for the function registry +
 * entity counts and ``useFunctionKpis`` (poll: 5s, one per floor) for
 * the marquee KPI strings.
 */
import { Text } from "@react-three/drei";
import { useFrame } from "@react-three/fiber";
import type { ReactElement } from "react";
import { useRef } from "react";
import * as THREE from "three";

import { useFunctionKpis } from "../../lib/useOrgData";
import type { OrgFunction } from "../../lib/useOrgData";
import { WindowGrid } from "./Window";
import type { WindowSpec } from "./Window";

const FLOOR_ORDER_TOP_DOWN: string[] = [
  "ceo",
  "finance",
  "revenue",
  "hr",
  "ops",
  "legal",
  "marketing",
  "tech",
  "data",
  "customer-success",
];

// Distinct emissive tints — seeded from the Cosmic constellation
// palette so cross-scene transitions feel of a piece. Picked per
// function so cross-floor reads are unambiguous.
const FUNCTION_COLORS: Record<string, string> = {
  ceo: "#ffd76a",
  finance: "#5fd49d",
  revenue: "#f4a300",
  hr: "#7faed4",
  ops: "#e87a5d",
  legal: "#9b7ed4",
  marketing: "#c25f9e",
  tech: "#5fb3a8",
  data: "#a8d45f",
  "customer-success": "#d4b95f",
};

// Lobby kind palette. Spec callout #6.
const KIND_PALETTE: { kind: string; color: string; label: string }[] = [
  { kind: "Person", color: "#7faed4", label: "Person" },
  { kind: "Organisation", color: "#f4a300", label: "Org" },
  { kind: "Asset", color: "#5fb3a8", label: "Asset" },
  { kind: "Money", color: "#ffd76a", label: "Money" },
  { kind: "Decision", color: "#9b7ed4", label: "Decision" },
  { kind: "Place", color: "#5fd49d", label: "Place" },
  { kind: "Period", color: "#f1f1f1", label: "Period" },
];

const FLOOR_HEIGHT = 1.0;
const FLOOR_WIDTH = 3.2;
const FLOOR_DEPTH = 2.0;
const PENTHOUSE_WIDTH = 2.2;
const LOBBY_WIDTH = 4.2;
const WINDOWS_PER_FLOOR = 6;

interface FloorProps {
  fn: OrgFunction;
  y: number;
  isPenthouse?: boolean;
  /** Renders at ~30% opacity (TASK-033 — wing-level fade-out). */
  dimmed?: boolean;
  /** Slightly brighter emissive accent for floors in the active wing. */
  boosted?: boolean;
  onClick?: () => void;
}

function Floor({ fn, y, isPenthouse = false, dimmed = false, boosted = false, onClick }: FloorProps) {
  const color = FUNCTION_COLORS[fn.name] ?? "#cccccc";
  const width = isPenthouse ? PENTHOUSE_WIDTH : FLOOR_WIDTH;
  const kpis = useFunctionKpis(fn.name);
  const slabRef = useRef<THREE.Mesh>(null);

  // CEO penthouse pulses gently (spec callout #5).
  useFrame((state) => {
    if (!slabRef.current || !isPenthouse) return;
    const t = state.clock.getElapsedTime();
    const m = slabRef.current.material as THREE.MeshStandardMaterial;
    m.emissiveIntensity = 0.6 + 0.25 * Math.sin(t * 1.4);
  });

  // Pre-compute the marquee text. Empty store → "—" placeholder per spec.
  const tickerText = (() => {
    if (fn.kpis.length === 0) return "";
    const parts = fn.kpis.map((metric) => {
      const m = kpis.metrics[metric];
      if (!m) return `${metric.toUpperCase()} —`;
      const v = Number.isFinite(m.value) ? m.value : 0;
      const display = Math.abs(v) >= 100 ? v.toFixed(0) : v.toFixed(1);
      return `${metric.toUpperCase()} ${display}`;
    });
    return parts.join("   ·   ");
  })();

  // Lay out windows along the front facade in a single row.
  const windows: WindowSpec[] = (() => {
    const out: WindowSpec[] = [];
    const span = width * 0.72;
    const z = FLOOR_DEPTH / 2 + 0.025;
    const yOffset = FLOOR_HEIGHT * 0.05;
    for (let i = 0; i < WINDOWS_PER_FLOOR; i += 1) {
      const t = i / Math.max(1, WINDOWS_PER_FLOOR - 1);
      const x = -span / 2 + t * span;
      // Deterministic lit/unlit pattern per floor: alternate-ish so the
      // facade reads as inhabited without animation. Chunks 2-3 will
      // drive `lit` from per-window workflow signals.
      const lit = (i + fn.name.length) % 3 !== 0;
      out.push({ position: [x, yOffset, z], color, lit });
    }
    return out;
  })();

  return (
    <group
      position={[0, y, 0]}
      onClick={onClick ? (e) => { e.stopPropagation(); onClick(); } : undefined}
    >
      {/* Translucent floor slab */}
      <mesh ref={slabRef}>
        <boxGeometry args={[width, FLOOR_HEIGHT * 0.92, FLOOR_DEPTH]} />
        <meshStandardMaterial
          color={"#16181c"}
          emissive={color}
          emissiveIntensity={isPenthouse ? 0.6 : boosted ? 0.42 : 0.18}
          transparent
          opacity={dimmed ? 0.28 : 0.78}
          metalness={0.1}
          roughness={0.65}
        />
      </mesh>

      {/* Coloured backdrop accent — a thin emissive plane behind the slab. */}
      <mesh position={[0, 0, -FLOOR_DEPTH / 2 - 0.02]}>
        <planeGeometry args={[width * 1.04, FLOOR_HEIGHT * 0.92]} />
        <meshBasicMaterial color={color} transparent opacity={dimmed ? 0.12 : boosted ? 0.45 : 0.32} />
      </mesh>

      {/* Function label on the front facade. */}
      <Text
        position={[-width / 2 + 0.12, FLOOR_HEIGHT * 0.28, FLOOR_DEPTH / 2 + 0.03]}
        fontSize={boosted ? 0.2 : 0.16}
        color={dimmed ? "#6b7077" : "#f5f5f7"}
        anchorX="left"
        anchorY="middle"
        outlineWidth={0.005}
        outlineColor="#000"
      >
        {fn.display}
      </Text>

      {/* KPI count badge tucked under the label. */}
      <Text
        position={[-width / 2 + 0.12, FLOOR_HEIGHT * 0.08, FLOOR_DEPTH / 2 + 0.03]}
        fontSize={0.07}
        color="#9aa0a6"
        anchorX="left"
        anchorY="middle"
      >
        {fn.kpis.length} KPI{fn.kpis.length === 1 ? "" : "s"}
      </Text>

      {/* Marquee KPI ticker — re-renders on each poll tick. */}
      <Text
        position={[0, -FLOOR_HEIGHT * 0.28, FLOOR_DEPTH / 2 + 0.03]}
        fontSize={boosted ? 0.11 : 0.075}
        maxWidth={width * 0.95}
        color={dimmed ? "#6b7077" : color}
        anchorX="center"
        anchorY="middle"
        outlineWidth={0.003}
        outlineColor="#000"
      >
        {tickerText || "—"}
      </Text>

      <WindowGrid windows={windows} />
    </group>
  );
}

interface LobbyProps {
  y: number;
  entityCounts: Record<string, number>;
}

function Lobby({ y, entityCounts }: LobbyProps) {
  return (
    <group position={[0, y, 0]}>
      {/* Wider base slab. */}
      <mesh>
        <boxGeometry args={[LOBBY_WIDTH, FLOOR_HEIGHT * 0.96, FLOOR_DEPTH * 1.08]} />
        <meshStandardMaterial
          color={"#1c1f24"}
          emissive={"#3b3f4a"}
          emissiveIntensity={0.25}
          transparent
          opacity={0.85}
          metalness={0.15}
          roughness={0.6}
        />
      </mesh>

      <Text
        position={[-LOBBY_WIDTH / 2 + 0.12, FLOOR_HEIGHT * 0.32, FLOOR_DEPTH / 2 * 1.08 + 0.03]}
        fontSize={0.14}
        color="#f5f5f7"
        anchorX="left"
        anchorY="middle"
      >
        Lobby
      </Text>

      {/* Seven kind-icon stations across the lobby front. */}
      {KIND_PALETTE.map((k, i) => {
        const span = LOBBY_WIDTH * 0.86;
        const t = i / (KIND_PALETTE.length - 1);
        const x = -span / 2 + t * span;
        const count = entityCounts[k.kind] ?? 0;
        return (
          <group key={k.kind} position={[x, -FLOOR_HEIGHT * 0.06, FLOOR_DEPTH / 2 * 1.08 + 0.06]}>
            <mesh>
              <sphereGeometry args={[0.09, 16, 16]} />
              <meshStandardMaterial
                color={k.color}
                emissive={k.color}
                emissiveIntensity={0.85}
                toneMapped={false}
              />
            </mesh>
            <Text
              position={[0, -0.16, 0]}
              fontSize={0.06}
              color="#cfd2d6"
              anchorX="center"
              anchorY="middle"
            >
              {k.label}
            </Text>
            <Text
              position={[0, -0.26, 0]}
              fontSize={0.075}
              color="#f5f5f7"
              anchorX="center"
              anchorY="middle"
            >
              {count}
            </Text>
          </group>
        );
      })}
    </group>
  );
}

interface BuildingProps {
  functions: OrgFunction[];
  entityCounts: Record<string, number>;
  /** When set, floors NOT in this wing render at ~30% opacity so the
   *  named wing stands out at zoom-2. Floors in the wing also tick a
   *  brighter material accent. */
  activeWing?: string[] | null;
  /** Click-to-zoom callback — fires when the operator clicks a floor.
   *  At zoom-3 the page wires this to "zoom to the wing of this floor". */
  onFloorClick?: (fnName: string) => void;
}

export function Building({
  functions,
  entityCounts,
  activeWing = null,
  onFloorClick,
}: BuildingProps) {
  const byName = new Map(functions.map((f) => [f.name, f]));

  const renderedFloors: ReactElement[] = [];
  const reversed = [...FLOOR_ORDER_TOP_DOWN].reverse();
  let cursorY = FLOOR_HEIGHT;
  reversed.forEach((name) => {
    const fn = byName.get(name);
    if (!fn) return;
    const isPenthouse = name === "ceo";
    const dimmed = activeWing != null && !activeWing.includes(name);
    renderedFloors.push(
      <Floor
        key={name}
        fn={fn}
        y={cursorY}
        isPenthouse={isPenthouse}
        dimmed={dimmed}
        boosted={activeWing != null && activeWing.includes(name)}
        onClick={onFloorClick ? () => onFloorClick(name) : undefined}
      />,
    );
    cursorY += FLOOR_HEIGHT;
  });

  return (
    <group>
      <Lobby y={0} entityCounts={entityCounts} />
      {renderedFloors}
    </group>
  );
}

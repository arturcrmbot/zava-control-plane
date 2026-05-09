/**
 * Floor — one function's storey of the glass tower.
 *
 * Glass slab + back-wall billboard + 4-6 desks (one per persona role) +
 * a hovering workflow-mote layer (those are rendered by WorkflowMotes
 * for proper instancing; this component just exposes desk positions
 * via the global registry).
 */
import { Text } from "@react-three/drei";
import { useFrame } from "@react-three/fiber";
import { useMemo, useRef } from "react";
import * as THREE from "three";

import type { FlashSet, FunctionSpec, InFlightWorkflow, PersonaRow } from "../../lib/useLiveOrg";
import { Persona } from "./Persona";
import { registerDeskPositions } from "./tower-registry";

const FLOOR_HEIGHT = 1.0;
const FLOOR_DEPTH = 3.4;
const FLOOR_WIDTH = 5.0;
const PENTHOUSE_WIDTH = 3.4;

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

interface Props {
  fn: FunctionSpec;
  y: number;
  isPenthouse?: boolean;
  inFlight: InFlightWorkflow[];
  personaByRole: Map<string, PersonaRow>;
  flashesRef: React.MutableRefObject<FlashSet>;
  onClick?: () => void;
}

function flattenPersonas(node: { role: string; manages: unknown[] }, max = 6): string[] {
  const out: string[] = [];
  function walk(n: { role: string; manages: unknown[] }) {
    if (out.length >= max) return;
    out.push(n.role);
    for (const child of (n.manages as { role: string; manages: unknown[] }[]) || []) {
      if (out.length >= max) return;
      walk(child);
    }
  }
  walk(node);
  return out;
}

export function Floor({ fn, y, isPenthouse = false, inFlight, personaByRole, flashesRef, onClick }: Props) {
  const slabRef = useRef<THREE.Mesh>(null);
  const color = FUNCTION_COLORS[fn.name] ?? "#cccccc";
  const width = isPenthouse ? PENTHOUSE_WIDTH : FLOOR_WIDTH;

  const personas = useMemo(() => flattenPersonas(fn.personaHierarchy as { role: string; manages: unknown[] }), [fn]);

  // Anchor desks along the front of the floor in a row.
  const deskPositions = useMemo(() => {
    const span = width * 0.75;
    const z = FLOOR_DEPTH / 2 - 0.25;
    const yLocal = -FLOOR_HEIGHT * 0.15;
    return personas.map((role, i) => {
      const t = personas.length === 1 ? 0.5 : i / (personas.length - 1);
      const x = -span / 2 + t * span;
      return { role, position: [x, yLocal, z] as [number, number, number] };
    });
  }, [personas, width]);

  // Register absolute world positions of these desks so other components
  // (workflow motes, decision pool) can address them.
  useMemo(() => {
    for (const d of deskPositions) {
      registerDeskPositions(fn.name, d.role, [
        d.position[0],
        y + d.position[1],
        d.position[2],
      ]);
    }
  }, [deskPositions, fn.name, y]);

  // Floor heat — emissive ramp based on count of in-flight workflows on
  // this floor. Real signal: 0 in-flight = dim, many in-flight = bright.
  // Plus per-workflow flash on workflow.completed for any wf on this floor.
  useFrame(() => {
    if (!slabRef.current) return;
    const m = slabRef.current.material as THREE.MeshStandardMaterial;
    let flashBoost = 0;
    const now = performance.now();
    const flashes = flashesRef.current.workflowFlash;
    // Walk inFlight ids that map to this floor + check workflowFlash.
    for (const w of inFlight) {
      const f = flashes.get(w.id);
      if (f && f.until > now && (f.kind === "completed" || f.kind === "exception")) {
        const remaining = (f.until - now) / 2500;
        flashBoost = Math.max(flashBoost, remaining * (f.kind === "exception" ? 1.0 : 0.7));
      }
    }
    const target = 0.08 + Math.min(0.55, inFlight.length * 0.07) + flashBoost;
    m.emissiveIntensity += (target - m.emissiveIntensity) * 0.16;
  });

  return (
    <group
      position={[0, y, 0]}
      onClick={onClick ? (e) => { e.stopPropagation(); onClick(); } : undefined}
      onPointerOver={onClick ? () => (document.body.style.cursor = "pointer") : undefined}
      onPointerOut={onClick ? () => (document.body.style.cursor = "auto") : undefined}
    >
      {/* Glass slab — the floor surface. */}
      <mesh ref={slabRef} position={[0, -FLOOR_HEIGHT * 0.45, 0]}>
        <boxGeometry args={[width, FLOOR_HEIGHT * 0.08, FLOOR_DEPTH]} />
        <meshStandardMaterial
          color="#0a0c12"
          emissive={color}
          emissiveIntensity={0.15}
          metalness={0.4}
          roughness={0.5}
        />
      </mesh>

      {/* Glass walls — left + right + back, semi-transparent dark. */}
      <mesh position={[-width / 2, 0, 0]}>
        <boxGeometry args={[0.04, FLOOR_HEIGHT * 0.92, FLOOR_DEPTH]} />
        <meshStandardMaterial color="#0a0c12" transparent opacity={0.35} metalness={0.6} roughness={0.4} />
      </mesh>
      <mesh position={[width / 2, 0, 0]}>
        <boxGeometry args={[0.04, FLOOR_HEIGHT * 0.92, FLOOR_DEPTH]} />
        <meshStandardMaterial color="#0a0c12" transparent opacity={0.35} metalness={0.6} roughness={0.4} />
      </mesh>
      <mesh position={[0, 0, -FLOOR_DEPTH / 2]}>
        <boxGeometry args={[width, FLOOR_HEIGHT * 0.92, 0.04]} />
        <meshStandardMaterial color="#0a0c12" transparent opacity={0.55} metalness={0.6} roughness={0.4} />
      </mesh>

      {/* Function label on the RIGHT side wall, oriented like building
          signage. Faces +X toward the camera (camera at +X,+Z). Never
          occluded by persona avatars sitting at the floor's front. */}
      <Text
        position={[width / 2 + 0.06, 0.05, 0]}
        rotation={[0, Math.PI / 2, 0]}
        fontSize={0.32}
        color="#f5f5f7"
        anchorX="center"
        anchorY="middle"
        outlineWidth={0.008}
        outlineColor="#000"
      >
        {fn.display.toUpperCase()}
      </Text>
      <Text
        position={[width / 2 + 0.06, -0.22, 0]}
        rotation={[0, Math.PI / 2, 0]}
        fontSize={0.1}
        color={color}
        anchorX="center"
        anchorY="middle"
      >
        {personas.length} {personas.length === 1 ? "person" : "people"} · {inFlight.length} in flight
      </Text>

      {/* Back-wall ambient floor color slab — provides the warm interior glow. */}
      <mesh position={[0, 0, -FLOOR_DEPTH / 2 + 0.025]}>
        <planeGeometry args={[width * 0.96, FLOOR_HEIGHT * 0.85]} />
        <meshBasicMaterial color={color} transparent opacity={0.12} />
      </mesh>

      {/* Desks + persona avatars at the front. */}
      {deskPositions.map((d) => (
        <Persona
          key={d.role}
          role={d.role}
          position={d.position}
          state={personaByRole.get(d.role)?.state ?? "idle"}
          flashesRef={flashesRef}
          tint={color}
          showLabel={isPenthouse}
        />
      ))}
    </group>
  );
}

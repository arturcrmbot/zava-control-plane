import { useMemo } from "react";
import { Html } from "@react-three/drei";
import type { CityMeta, CosmicMode, PersonaState } from "./lib/types";
import { colorForKind, colorForEntityType } from "./lib/colors";

interface CitiesProps {
  cities: CityMeta[];
  mode: CosmicMode;
  personas?: PersonaState[];
  onCityClick?: (id: string, label: string) => void;
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
 * Phase A: deterministic random layout (hashed off city id).
 * Phase C replaces with force-directed layout.
 *
 * Each city = sphere + halo. Non-instanced because per-instance emissive
 * isn't supported by InstancedMesh standard materials, and 110 cities
 * is well within budget for individual meshes.
 */
export function Cities({ cities, mode, personas, onCityClick }: CitiesProps) {
  const pendingByPersona = useMemo(() => {
    const m = new Map<string, number>();
    if (personas) {
      for (const p of personas) {
        if ((p.pending_count ?? 0) > 0) m.set(p.role, p.pending_count);
      }
    }
    return m;
  }, [personas]);

  const positioned = useMemo(() => {
    return cities.map((city) => {
      const [x, y, z] = cityPosition(city.id);
      const color =
        mode === "entities" ? colorForEntityType(city.kind) : colorForKind(city.kind);
      const pending = city.kind === "persona" ? pendingByPersona.get(city.id) ?? 0 : 0;
      // Hot personas pulse with a brighter halo + bigger size
      const sizeBoost = pending > 0 ? Math.min(2.0, 1 + pending * 0.2) : 1;
      return { ...city, x, y, z, color, pending, sizeBoost };
    });
  }, [cities, mode, pendingByPersona]);

  if (positioned.length === 0) return <PlaceholderRing />;

  return (
    <group>
      {positioned.map((c) => (
        <group key={c.id} position={[c.x, c.y, c.z]}>
          {/* The city itself — emissive sphere */}
          <mesh
            scale={c.sizeBoost}
            onClick={(e) => {
              e.stopPropagation();
              onCityClick?.(c.id, c.label);
            }}
            onPointerOver={(e) => {
              e.stopPropagation();
              document.body.style.cursor = "pointer";
            }}
            onPointerOut={() => {
              document.body.style.cursor = "default";
            }}
          >
            <sphereGeometry args={[CITY_RADIUS, 12, 12]} />
            <meshStandardMaterial
              color={c.color}
              emissive={c.color}
              emissiveIntensity={c.pending > 0 ? 1.6 : 1.0}
              metalness={0.2}
              roughness={0.4}
            />
          </mesh>
          {/* Halo */}
          <mesh scale={c.sizeBoost}>
            <sphereGeometry args={[CITY_RADIUS * 1.8, 10, 10]} />
            <meshBasicMaterial
              color={c.color}
              transparent
              opacity={c.pending > 0 ? 0.35 : 0.18}
            />
          </mesh>
          {/* Pending count badge above HITL persona cities */}
          {c.pending > 0 && (
            <Html
              position={[0, CITY_RADIUS * 2 + 0.15, 0]}
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
        </group>
      ))}
    </group>
  );
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

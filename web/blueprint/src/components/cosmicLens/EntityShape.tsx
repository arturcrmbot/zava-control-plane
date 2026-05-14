/**
 * EntityShape — one geometric primitive per Kuzu entity kind.
 *
 * In capabilities mode every persona is a holographic capsule, but in
 * entities mode the central disc is a Kuzu graph slice and we want each
 * kind of node to read at a glance:
 *
 *   Person       → capsule (a standing figure)
 *   Organisation → cube (a corporate building block)
 *   Subsidiary   → smaller cube (a nested org)
 *   Asset        → octahedron (crystalline, inventoried)
 *   Money        → flat cylinder (a coin)
 *   Decision     → icosahedron (multi-faceted, considered)
 *   Place        → 4-sided pyramid (geographic landmark)
 *   Period       → torus (cyclic time)
 *   Workflow     → sphere (encapsulated process)
 *   Brand        → diamond / rotated octahedron (premium asset)
 *   Campaign     → 4-point star (marketing burst)
 *   Pitch        → tetrahedron (sharp, presented)
 *   MediaPlan    → flat box (document-like)
 *
 * Each shape uses meshStandardMaterial with the kind's colour as both
 * `color` and `emissive` (intensity 0.6) so it glows on its own without
 * needing scene lighting to read. All shapes occupy roughly the same
 * bounding-sphere volume so the disc layout stays balanced.
 */
import { useMemo } from "react";
import * as THREE from "three";

const RADIUS = 0.18;

interface Props {
  kind: string;
  color: string;
  emissiveIntensity?: number;
  scale?: number;
}

/** A 4-point star geometry (×, like a sparkle / marketing burst). Two
 *  thin elongated boxes crossed at right angles, merged into a single
 *  buffer geometry so it renders as one mesh. */
function makeStarGeometry(size: number): THREE.BufferGeometry {
  const a = new THREE.BoxGeometry(size * 2.2, size * 0.35, size * 0.35);
  const b = new THREE.BoxGeometry(size * 0.35, size * 2.2, size * 0.35);
  const c = new THREE.BoxGeometry(size * 0.35, size * 0.35, size * 2.2);
  // mergeGeometries lives in BufferGeometryUtils; rather than pull that in,
  // build by hand: copy attributes from a + b + c into one buffer.
  const merge = (geos: THREE.BufferGeometry[]): THREE.BufferGeometry => {
    let totalVerts = 0;
    for (const g of geos) totalVerts += (g.attributes.position as THREE.BufferAttribute).count;
    const pos = new Float32Array(totalVerts * 3);
    const norm = new Float32Array(totalVerts * 3);
    let off = 0;
    for (const g of geos) {
      const p = g.attributes.position as THREE.BufferAttribute;
      const n = g.attributes.normal as THREE.BufferAttribute;
      pos.set(p.array as Float32Array, off * 3);
      norm.set(n.array as Float32Array, off * 3);
      off += p.count;
    }
    const out = new THREE.BufferGeometry();
    out.setAttribute("position", new THREE.BufferAttribute(pos, 3));
    out.setAttribute("normal", new THREE.BufferAttribute(norm, 3));
    return out;
  };
  return merge([a, b, c]);
}

/** Per-kind geometry factory. Cached in a module-level map so we don't
 *  rebuild the same primitive every entity render. Exported so callers
 *  who already manage their own mesh / material (e.g. the city renderer
 *  with hover handlers) can reuse the same cached geometry without
 *  going through the EntityShape wrapper component.
 *
 *  Handles BOTH:
 *    - Kuzu node kinds in entities mode (TitleCase: Person, Decision, …)
 *    - Capability kinds in capabilities mode (lowercase: mcp, skill, …)
 *  Falls through to a default sphere for unknown kinds so the scene
 *  never goes empty if the API adds a new kind we haven't styled yet.
 */
const _geomCache = new Map<string, THREE.BufferGeometry>();
export function entityGeomFor(kind: string): THREE.BufferGeometry {
  const cached = _geomCache.get(kind);
  if (cached) return cached;
  let g: THREE.BufferGeometry;
  switch (kind) {
    // ── Kuzu entity-mode kinds ────────────────────────────────────────
    case "Person":
      g = new THREE.CapsuleGeometry(RADIUS * 0.7, RADIUS * 1.6, 4, 12);
      break;
    case "Organisation":
      g = new THREE.BoxGeometry(RADIUS * 1.6, RADIUS * 1.6, RADIUS * 1.6);
      break;
    case "Subsidiary":
      g = new THREE.BoxGeometry(RADIUS * 1.2, RADIUS * 1.2, RADIUS * 1.2);
      break;
    case "Asset":
      g = new THREE.OctahedronGeometry(RADIUS * 1.2, 0);
      break;
    case "Money":
      g = new THREE.CylinderGeometry(RADIUS * 1.1, RADIUS * 1.1, RADIUS * 0.35, 24);
      // Lay the coin flat (rotate around X so it faces up like a coin on a table).
      g.rotateX(Math.PI / 2);
      break;
    case "Decision":
      g = new THREE.IcosahedronGeometry(RADIUS * 1.15, 0);
      break;
    case "Place":
      // 4-sided pyramid = cone with 4 radial segments and a flat bottom.
      g = new THREE.ConeGeometry(RADIUS * 1.25, RADIUS * 1.8, 4);
      break;
    case "Period":
      g = new THREE.TorusGeometry(RADIUS * 1.1, RADIUS * 0.28, 10, 24);
      break;
    case "Workflow":
      g = new THREE.SphereGeometry(RADIUS * 1.1, 18, 14);
      break;
    case "Brand":
      // Stretched octahedron rotated so it sits as a diamond pointing up.
      g = new THREE.OctahedronGeometry(RADIUS * 1.15, 0);
      g.scale(0.85, 1.4, 0.85);
      break;
    case "Campaign":
      g = makeStarGeometry(RADIUS);
      break;
    case "Pitch":
      g = new THREE.TetrahedronGeometry(RADIUS * 1.4, 0);
      break;
    case "MediaPlan":
      g = new THREE.BoxGeometry(RADIUS * 2.0, RADIUS * 0.18, RADIUS * 1.4);
      break;

    // ── Capabilities-mode kinds ───────────────────────────────────────
    case "persona":
      // Standing-figure capsule — same as Person. Kept as a separate case
      // so the persona forest in capabilities mode reads consistently.
      g = new THREE.CapsuleGeometry(RADIUS * 0.7, RADIUS * 1.6, 4, 12);
      break;
    case "mcp":
      // Hexagonal prism — reads as a 'docking station' / external service
      // connector. Six-sided cylinder gives the unmistakable hex silhouette
      // of an MCP server in our cosmic vocabulary.
      g = new THREE.CylinderGeometry(RADIUS * 1.15, RADIUS * 1.15, RADIUS * 1.7, 6);
      break;
    case "skill":
      // Dodecahedron — a 12-faced 'chunk of compiled logic'. Distinct from
      // the Decision icosahedron (20 faces) but in the same faceted family,
      // so the two read as 'related ideas' (skills serve decisions).
      g = new THREE.DodecahedronGeometry(RADIUS * 1.05, 0);
      break;
    case "validator":
      // Torus — a 'gatekeeper ring' / scanner. Validators check things
      // pass through them; the ring silhouette reads as that.
      g = new THREE.TorusGeometry(RADIUS * 1.05, RADIUS * 0.32, 10, 22);
      break;

    default:
      g = new THREE.SphereGeometry(RADIUS, 12, 12);
  }
  _geomCache.set(kind, g);
  return g;
}

export function EntityShape({ kind, color, emissiveIntensity = 0.6, scale = 1 }: Props) {
  const geom = useMemo(() => entityGeomFor(kind), [kind]);
  return (
    <mesh geometry={geom} scale={scale}>
      <meshStandardMaterial
        color={color}
        emissive={color}
        emissiveIntensity={emissiveIntensity}
        metalness={0.3}
        roughness={0.45}
      />
    </mesh>
  );
}

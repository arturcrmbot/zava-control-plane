import { useMemo, useRef } from "react";
import * as THREE from "three";
import { useFrame } from "@react-three/fiber";
import type { CityMeta, CosmicMode } from "./lib/types";
import { colorForKind, colorForEntityType } from "./lib/colors";

interface CitiesProps {
  cities: CityMeta[];
  mode: CosmicMode;
}

const CITY_RADIUS = 0.18;
const DISC_RADIUS = 7.2; // stay inside the hub disc edge
const HUB_TOP_Y = 0.42; // disc thickness/2 + small lift

const MAX_CITIES = 80;

const matrix = new THREE.Matrix4();
const position = new THREE.Vector3();
const scale = new THREE.Vector3(1, 1, 1);
const quaternion = new THREE.Quaternion();
const tmpColor = new THREE.Color();

/**
 * Cities scattered on the disc surface.
 *
 * Phase A: deterministic random layout (hashed off city id) so positions
 * don't change per render. Phase C replaces with force-directed layout.
 */
export function Cities({ cities, mode }: CitiesProps) {
  const meshRef = useRef<THREE.InstancedMesh>(null);

  const layout = useMemo(() => {
    return cities.slice(0, MAX_CITIES).map((city) => {
      // Deterministic random position using djb2 hash of city id
      let hash = 5381;
      for (let i = 0; i < city.id.length; i++) {
        hash = ((hash << 5) + hash + city.id.charCodeAt(i)) | 0;
      }
      const rNorm = (Math.abs(hash) % 1000) / 1000; // 0..1
      const tNorm = (Math.abs(hash >> 8) % 1000) / 1000;
      const r = Math.sqrt(rNorm) * DISC_RADIUS; // sqrt for even areal distribution
      const angle = tNorm * Math.PI * 2;
      const x = Math.cos(angle) * r;
      const z = Math.sin(angle) * r;
      const color =
        mode === "entities" ? colorForEntityType(city.kind) : colorForKind(city.kind);
      return { id: city.id, x, z, color };
    });
  }, [cities, mode]);

  useFrame(() => {
    if (!meshRef.current) return;
    const mesh = meshRef.current;
    layout.forEach((c, i) => {
      position.set(c.x, HUB_TOP_Y, c.z);
      matrix.compose(position, quaternion, scale);
      mesh.setMatrixAt(i, matrix);
      tmpColor.set(c.color);
      mesh.setColorAt(i, tmpColor);
    });
    for (let i = layout.length; i < MAX_CITIES; i++) {
      position.set(0, -100, 0);
      matrix.compose(position, quaternion, scale);
      mesh.setMatrixAt(i, matrix);
    }
    mesh.instanceMatrix.needsUpdate = true;
    if (mesh.instanceColor) mesh.instanceColor.needsUpdate = true;
    mesh.count = MAX_CITIES;
  });

  if (cities.length === 0) {
    // Phase A may have no cities until Phase B endpoint exists; render
    // a small placeholder ring so the disc isn't empty.
    return <PlaceholderRing />;
  }

  return (
    <instancedMesh ref={meshRef} args={[undefined, undefined, MAX_CITIES]} castShadow>
      <sphereGeometry args={[CITY_RADIUS, 12, 12]} />
      <meshStandardMaterial
        emissive="#22d3ee"
        emissiveIntensity={0.8}
        metalness={0.2}
        roughness={0.4}
        vertexColors
      />
    </instancedMesh>
  );
}

/** A simple cluster of glowing dots so the hub doesn't look empty before /api/cities exists. */
function PlaceholderRing() {
  const ref = useRef<THREE.InstancedMesh>(null);
  const count = 30;

  useFrame((state) => {
    if (!ref.current) return;
    const mesh = ref.current;
    const t = state.clock.getElapsedTime();
    for (let i = 0; i < count; i++) {
      const angle = (i / count) * Math.PI * 2;
      const r = 4 + Math.sin(t * 0.5 + i) * 0.2;
      position.set(Math.cos(angle) * r, HUB_TOP_Y, Math.sin(angle) * r);
      matrix.compose(position, quaternion, scale);
      mesh.setMatrixAt(i, matrix);
    }
    mesh.instanceMatrix.needsUpdate = true;
    mesh.count = count;
  });

  return (
    <instancedMesh ref={ref} args={[undefined, undefined, count]}>
      <sphereGeometry args={[0.14, 10, 10]} />
      <meshStandardMaterial
        color="#94a3b8"
        emissive="#22d3ee"
        emissiveIntensity={0.5}
        transparent
        opacity={0.6}
      />
    </instancedMesh>
  );
}

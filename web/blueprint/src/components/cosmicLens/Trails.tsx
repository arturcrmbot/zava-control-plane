import { useEffect, useRef } from "react";
import * as THREE from "three";
import { useFrame } from "@react-three/fiber";
import { TrailRegistry } from "./lib/registries";

interface TrailsProps {
  registry: TrailRegistry;
  decayMs?: number;
}

const MAX_TRAILS = 500;
const SEGMENTS_PER_TRAIL = 1; // straight line per trail sample (cheap)

const tmpColor = new THREE.Color();

/**
 * Fading trails left by completed rocket flights. Each trail = a single
 * straight line segment from rocket origin to its city, fading over decayMs.
 *
 * Rendered as a `<lineSegments>` with vertex colors so alpha can fade per
 * sample.
 */
export function Trails({ registry, decayMs = 60_000 }: TrailsProps) {
  const meshRef = useRef<THREE.LineSegments>(null);
  const positionsRef = useRef<Float32Array>(new Float32Array(MAX_TRAILS * 6));
  const colorsRef = useRef<Float32Array>(new Float32Array(MAX_TRAILS * 6));
  const lastVersionRef = useRef(0);

  useFrame(() => {
    if (!meshRef.current) return;
    const now = Date.now();
    const visible = registry.visible(now, decayMs);
    const positions = positionsRef.current;
    const colors = colorsRef.current;

    let i = 0;
    for (const { sample, alpha } of visible) {
      if (i >= MAX_TRAILS) break;
      const base = i * 6;
      positions[base + 0] = sample.from[0];
      positions[base + 1] = sample.from[1];
      positions[base + 2] = sample.from[2];
      positions[base + 3] = sample.to[0];
      positions[base + 4] = sample.to[1];
      positions[base + 5] = sample.to[2];

      tmpColor.set(sample.color);
      colors[base + 0] = tmpColor.r * alpha;
      colors[base + 1] = tmpColor.g * alpha;
      colors[base + 2] = tmpColor.b * alpha;
      colors[base + 3] = tmpColor.r * alpha;
      colors[base + 4] = tmpColor.g * alpha;
      colors[base + 5] = tmpColor.b * alpha;
      i++;
    }
    // Park unused
    for (let j = i * 6; j < MAX_TRAILS * 6; j++) {
      positions[j] = 0;
      colors[j] = 0;
    }

    const geom = meshRef.current.geometry;
    const posAttr = geom.attributes.position as THREE.BufferAttribute;
    const colAttr = geom.attributes.color as THREE.BufferAttribute;
    posAttr.needsUpdate = true;
    colAttr.needsUpdate = true;
    geom.setDrawRange(0, i * 2);
    lastVersionRef.current = registry.version;
  });

  return (
    <lineSegments ref={meshRef}>
      <bufferGeometry>
        <bufferAttribute
          attach="attributes-position"
          args={[positionsRef.current, 3]}
          count={MAX_TRAILS * 2}
        />
        <bufferAttribute
          attach="attributes-color"
          args={[colorsRef.current, 3]}
          count={MAX_TRAILS * 2}
        />
      </bufferGeometry>
      <lineBasicMaterial vertexColors transparent />
    </lineSegments>
  );
}

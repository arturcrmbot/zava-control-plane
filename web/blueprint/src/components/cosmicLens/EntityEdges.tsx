import { useEffect, useState } from "react";
import * as THREE from "three";
import { cityPosition } from "./Cities";
import type { CityMeta } from "./lib/types";
import { ENDPOINTS } from "./lib/types";

interface EntityEdgesProps {
  cities: CityMeta[];
  /** When false (Capabilities mode), this component renders nothing. */
  visible: boolean;
}

interface Edge {
  from_kind: string;
  to_kind: string;
  label: string;
}

/**
 * Persistent Kuzu graph relationships between entity-type cities.
 * Only rendered in Entities mode.
 */
export function EntityEdges({ cities, visible }: EntityEdgesProps) {
  const [edges, setEdges] = useState<Edge[]>([]);

  useEffect(() => {
    if (!visible) return;
    let cancelled = false;
    fetch(`${ENDPOINTS.cities}/edges`)
      .then((r) => r.json())
      .then((data) => {
        if (cancelled) return;
        setEdges(data.edges ?? []);
      })
      .catch((err) => console.warn("entity edges fetch failed", err));
    return () => {
      cancelled = true;
    };
  }, [visible]);

  if (!visible || edges.length === 0) return null;

  // Build a city-id → position map for quick lookup
  const positionByLabel = new Map<string, [number, number, number]>();
  cities.forEach((c) => {
    positionByLabel.set(c.label, cityPosition(c.id));
    positionByLabel.set(c.id, cityPosition(c.id));
  });

  return (
    <group>
      {edges.map((edge, i) => {
        const from = positionByLabel.get(edge.from_kind);
        const to = positionByLabel.get(edge.to_kind);
        if (!from || !to) return null;
        return <EdgeLine key={i} from={from} to={to} />;
      })}
    </group>
  );
}

function EdgeLine({
  from,
  to,
}: {
  from: [number, number, number];
  to: [number, number, number];
}) {
  // Slight arc above the disc by lifting the midpoint
  const mid = new THREE.Vector3(
    (from[0] + to[0]) / 2,
    Math.max(from[1], to[1]) + 0.6,
    (from[2] + to[2]) / 2,
  );
  const fromV = new THREE.Vector3(...from);
  const toV = new THREE.Vector3(...to);
  const curve = new THREE.QuadraticBezierCurve3(fromV, mid, toV);
  const points = curve.getPoints(20);
  const positions = new Float32Array(points.length * 3);
  points.forEach((p, i) => {
    positions[i * 3] = p.x;
    positions[i * 3 + 1] = p.y;
    positions[i * 3 + 2] = p.z;
  });
  return (
    <line>
      <bufferGeometry>
        <bufferAttribute
          attach="attributes-position"
          args={[positions, 3]}
          count={points.length}
        />
      </bufferGeometry>
      <lineBasicMaterial color="#475569" transparent opacity={0.35} />
    </line>
  );
}

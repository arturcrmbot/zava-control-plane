import { useEffect, useMemo, useState } from "react";
import * as THREE from "three";
import { cityPosition } from "./Cities";
import type { CityMeta } from "./lib/types";
import { ENDPOINTS } from "./lib/types";
import { colorForRelationship } from "./lib/relationshipColors";

interface EntityEdgesProps {
  cities: CityMeta[];
  /** When false (Capabilities mode), this component renders nothing. */
  visible: boolean;
}

interface Edge {
  from_kind: string;
  to_kind: string;
  label: string;
  rel?: string;
  count?: number;
}

/**
 * Persistent Kuzu graph relationships between entity-type cities.
 * Only rendered in Entities mode.
 *
 * Each edge is a coloured bezier arc (colour from colorForRelationship,
 * arching above the disc plane) plus a small pulsing additive sphere that
 * travels along the curve so the type AND direction-of-flow are both
 * obvious at a glance. Edge thickness modulated by activity count.
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

  // Pre-compute curve metadata once per edges/cities pair so the per-frame
  // path-traversal animation just samples a cached curve rather than
  // rebuilding bezier on every tick.
  const computedEdges = useMemo(() => {
    if (!visible || edges.length === 0) return [];
    const positionByLabel = new Map<string, [number, number, number]>();
    cities.forEach((c) => {
      positionByLabel.set(c.label, cityPosition(c.id));
      positionByLabel.set(c.id, cityPosition(c.id));
    });
    const out: ComputedEdge[] = [];
    for (const e of edges) {
      const from = positionByLabel.get(e.from_kind);
      const to = positionByLabel.get(e.to_kind);
      if (!from || !to) continue;
      out.push({
        from,
        to,
        rel: e.rel ?? e.label,
        count: e.count ?? 0,
      });
    }
    return out;
  }, [edges, cities, visible]);

  if (!visible || computedEdges.length === 0) return null;

  return (
    <group>
      {computedEdges.map((e, i) => (
        <EdgeArc key={i} edge={e} />
      ))}
    </group>
  );
}

interface ComputedEdge {
  from: [number, number, number];
  to: [number, number, number];
  rel: string;
  count: number;
}

function EdgeArc({ edge }: { edge: ComputedEdge }) {
  // Build the bezier curve once per edge instance. The midpoint is lifted
  // above the disc plane so the arc humps over rather than crossing
  // through the central capsules.
  const { points, color } = useMemo(() => {
    const fromV = new THREE.Vector3(...edge.from);
    const toV = new THREE.Vector3(...edge.to);
    const distance = fromV.distanceTo(toV);
    const lift = Math.min(2.0, 0.4 + distance * 0.15);
    const mid = new THREE.Vector3(
      (edge.from[0] + edge.to[0]) / 2,
      Math.max(edge.from[1], edge.to[1]) + lift,
      (edge.from[2] + edge.to[2]) / 2,
    );
    const c = new THREE.QuadraticBezierCurve3(fromV, mid, toV);
    const pts = c.getPoints(28);
    return { points: pts, color: colorForRelationship(edge.rel) };
  }, [edge.from, edge.to, edge.rel]);

  // Build the line geometry once. Static — we don't animate the arc itself.
  const lineGeom = useMemo(() => {
    const positions = new Float32Array(points.length * 3);
    points.forEach((p, i) => {
      positions[i * 3 + 0] = p.x;
      positions[i * 3 + 1] = p.y;
      positions[i * 3 + 2] = p.z;
    });
    const g = new THREE.BufferGeometry();
    g.setAttribute("position", new THREE.BufferAttribute(positions, 3));
    return g;
  }, [points]);

  // Edges with zero count get a heavily faded line — they're 'capacity
  // for this relationship type exists' but no live activity. Edges with
  // live counts get full opacity. NOTHING animates per-frame on edges:
  // decorative travelling pulses were removed because they suggested
  // activity that wasn't actually happening (real events should drive
  // motion; here there were none, so the pulses were just noise).
  const opacity = edge.count === 0 ? 0.18 : 0.55;

  return (
    <line>
      <primitive object={lineGeom} attach="geometry" />
      <lineBasicMaterial
        color={color}
        transparent
        opacity={opacity}
        depthWrite={false}
        blending={THREE.AdditiveBlending}
      />
    </line>
  );
}

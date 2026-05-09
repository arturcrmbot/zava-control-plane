/**
 * The Org Building (IP4, TASK-019..-025) — animation overlay.
 *
 * Sits inside the OrgBuilding R3F <Canvas>. Owns the per-frame loop
 * that:
 *   - drives the AnimEntry queue forward (dispatch 'tick' each frame)
 *   - renders motes via a single InstancedMesh (cap ~200)
 *   - renders sparks as bright spheres at lerped positions
 *   - renders filaments + cross-function beams as drei <Line>s
 *   - renders pulses as expanding rings (sensor/window flashes)
 *
 * Visual props (positions, scales, opacities) update via refs in
 * useFrame — no React state thrash per frame.
 */
import { Line } from "@react-three/drei";
import { useFrame } from "@react-three/fiber";
import { useMemo, useRef } from "react";
import * as THREE from "three";

import type { AnimEntry } from "../../lib/animationQueue";
import type { CrossFunctionBeam } from "../../lib/useOrgData";
import { ANIM_COLORS } from "../../lib/useOrgData";
import { floorFrontCentre } from "../../lib/floorLayout";

const MOTE_CAP = 200;
// Chunk-4 LOD (TASK-052): at zoom-3 (org / wing) the camera is far
// enough that individual motes blur into pixels; we render only every
// Nth mote and dim the material so the floor reads as "busy" without
// burning fragment-shader time on hundreds of sub-pixel sprites.
const LOD_FAR_STRIDE = 3;
const LOD_FAR_OPACITY = 0.55;
const LOD_NEAR_OPACITY = 0.9;

interface Props {
  entries: AnimEntry[];
  beams: CrossFunctionBeam[];
  onTick: (dt: number) => void;
  /** Spec zoom level (3=org … 0=workflow). Drives mote LOD: at 3 we
   *  stride the mote pool and dim it; at ≤2 we render every entry full
   *  brightness. Defaults to 3 so consumers without zoom plumbing get
   *  the cheaper render. */
  zoomLevel?: 0 | 1 | 2 | 3;
}

/** Quadratic bezier midpoint with a small upward arch — used by the
 *  filament curve so cross-floor connections read as arcs, not chords. */
function bezier(from: THREE.Vector3, to: THREE.Vector3, t: number, dst: THREE.Vector3) {
  const mid = from.clone().lerp(to, 0.5);
  mid.y += from.distanceTo(to) * 0.18;
  const u = 1 - t;
  dst.set(
    u * u * from.x + 2 * u * t * mid.x + t * t * to.x,
    u * u * from.y + 2 * u * t * mid.y + t * t * to.y,
    u * u * from.z + 2 * u * t * mid.z + t * t * to.z,
  );
}

export function AnimationLayer({ entries, beams, onTick, zoomLevel = 3 }: Props) {
  const motesRef = useRef<THREE.InstancedMesh>(null);
  const motesMaterialRef = useRef<THREE.MeshBasicMaterial>(null);
  const sparksGroupRef = useRef<THREE.Group>(null);
  const pulsesGroupRef = useRef<THREE.Group>(null);
  const filamentsGroupRef = useRef<THREE.Group>(null);
  const farLod = zoomLevel >= 3;

  // Per-frame: advance queue + push positions/scales/opacities to refs.
  // We keep three reusable Object3D / Vector3 / Color helpers to avoid
  // per-frame allocation churn.
  const helpers = useMemo(
    () => ({
      dummy: new THREE.Object3D(),
      vec: new THREE.Vector3(),
      from: new THREE.Vector3(),
      to: new THREE.Vector3(),
      color: new THREE.Color(),
    }),
    [],
  );

  useFrame((_, dt) => {
    onTick(dt);

    // Motes — instanced. We pack the first N mote entries into the mesh
    // and zero-scale the rest so the cap acts as a circular buffer.
    // LOD: at far zoom we stride the source list (every Nth mote)
    // because individual sub-pixel sprites just add fragment cost
    // without visible signal.
    const stride = farLod ? LOD_FAR_STRIDE : 1;
    const allMotes = entries.filter((e) => e.kind === "mote");
    const motes: AnimEntry[] = [];
    for (let i = 0; i < allMotes.length && motes.length < MOTE_CAP; i += stride) {
      motes.push(allMotes[i]);
    }
    const motesMat = motesMaterialRef.current;
    if (motesMat) {
      const target = farLod ? LOD_FAR_OPACITY : LOD_NEAR_OPACITY;
      // Cheap one-step lerp avoids opacity popping when zoom changes.
      motesMat.opacity += (target - motesMat.opacity) * Math.min(1, dt * 6);
    }
    const mesh = motesRef.current;
    if (mesh) {
      for (let i = 0; i < MOTE_CAP; i += 1) {
        const e = motes[i];
        if (!e || !e.to) {
          helpers.dummy.position.set(0, -100, 0);
          helpers.dummy.scale.setScalar(0);
        } else {
          helpers.from.set(...e.from);
          helpers.to.set(...e.to);
          helpers.vec.copy(helpers.from).lerp(helpers.to, e.t);
          helpers.dummy.position.copy(helpers.vec);
          // Mote shrinks slightly as it lands, so the lobby vault feels
          // like it absorbs the entity rather than just collecting motes.
          const s = 0.05 + 0.02 * (1 - e.t);
          helpers.dummy.scale.setScalar(s);
        }
        helpers.dummy.updateMatrix();
        mesh.setMatrixAt(i, helpers.dummy.matrix);
        if (e && mesh.instanceColor) {
          helpers.color.set(e.color);
          mesh.setColorAt(i, helpers.color);
        }
      }
      mesh.instanceMatrix.needsUpdate = true;
      if (mesh.instanceColor) mesh.instanceColor.needsUpdate = true;
    }

    // Sparks — small bright spheres travelling from window → lobby
    // along a bezier arc with a violet trail (decision spark).
    const sparkGroup = sparksGroupRef.current;
    if (sparkGroup) {
      const sparks = entries.filter((e) => e.kind === "spark");
      const children = sparkGroup.children;
      for (let i = 0; i < children.length; i += 1) {
        const child = children[i] as THREE.Mesh;
        const e = sparks[i];
        if (!e || !e.to) {
          child.visible = false;
          continue;
        }
        child.visible = true;
        helpers.from.set(...e.from);
        helpers.to.set(...e.to);
        bezier(helpers.from, helpers.to, e.t, helpers.vec);
        child.position.copy(helpers.vec);
        const m = child.material as THREE.MeshBasicMaterial;
        m.color.set(e.color);
        m.opacity = Math.max(0.05, 1 - e.t);
        const s = 0.06 + 0.05 * Math.sin(e.t * Math.PI);
        child.scale.setScalar(s);
      }
    }

    // Pulses — expanding ring + brightness ramp at a fixed location
    // (window-completed flash, ambient sensor flash, cadence flash).
    const pulseGroup = pulsesGroupRef.current;
    if (pulseGroup) {
      const pulses = entries.filter((e) => e.kind === "pulse");
      const children = pulseGroup.children;
      for (let i = 0; i < children.length; i += 1) {
        const child = children[i] as THREE.Mesh;
        const e = pulses[i];
        if (!e) {
          child.visible = false;
          continue;
        }
        child.visible = true;
        child.position.set(...e.from);
        const m = child.material as THREE.MeshBasicMaterial;
        m.color.set(e.color);
        // Soft ease-in-out brightness pulse.
        const env = Math.sin(e.t * Math.PI);
        m.opacity = 0.85 * env;
        const s = 0.08 + 0.18 * e.t;
        child.scale.setScalar(s);
      }
    }

    // Filaments are rebuilt per render below (drei <Line> needs re-keying
    // when the entry list mutates) — nothing to do here.
    void filamentsGroupRef.current;
  });

  // Pre-allocate enough sphere instances to cover the per-kind caps.
  // Using fixed-count children avoids React reconciliation in the hot
  // path; visibility/scale are toggled in useFrame above.
  const sparkSlots = useMemo(() => Array.from({ length: 64 }, (_, i) => i), []);
  const pulseSlots = useMemo(() => Array.from({ length: 64 }, (_, i) => i), []);

  // Filaments + beams render as drei <Line> components. Both lists are
  // small (≤32 entries) so the per-frame React work is negligible.
  const filaments = entries.filter((e) => e.kind === "filament" && e.to);

  return (
    <group>
      {/* Mote pool — single InstancedMesh. Material is white-emissive +
          per-instance colour override. Material opacity is animated by
          useFrame for zoom LOD (chunk-4 TASK-052). */}
      <instancedMesh
        ref={motesRef}
        args={[undefined, undefined, MOTE_CAP]}
        frustumCulled={false}
      >
        <sphereGeometry args={[1, 8, 8]} />
        <meshBasicMaterial
          ref={motesMaterialRef}
          color="#ffffff"
          transparent
          opacity={LOD_NEAR_OPACITY}
          toneMapped={false}
        />
      </instancedMesh>

      {/* Spark pool. */}
      <group ref={sparksGroupRef}>
        {sparkSlots.map((i) => (
          <mesh key={`spark-${i}`} visible={false}>
            <sphereGeometry args={[1, 12, 12]} />
            <meshBasicMaterial
              color={ANIM_COLORS.decision}
              transparent
              opacity={0}
              toneMapped={false}
            />
          </mesh>
        ))}
      </group>

      {/* Pulse pool. */}
      <group ref={pulsesGroupRef}>
        {pulseSlots.map((i) => (
          <mesh key={`pulse-${i}`} visible={false}>
            <sphereGeometry args={[1, 12, 12]} />
            <meshBasicMaterial
              color="#ffffff"
              transparent
              opacity={0}
              toneMapped={false}
            />
          </mesh>
        ))}
      </group>

      {/* Filaments — magenta arcs between parent + child workflow windows. */}
      <group ref={filamentsGroupRef}>
        {filaments.map((e) => {
          const points = filamentPoints(e);
          if (!points) return null;
          const opacity = Math.max(0.05, 1 - e.t);
          return (
            <Line
              key={e.id}
              points={points}
              color={e.color}
              lineWidth={1.2}
              transparent
              opacity={opacity}
              toneMapped={false}
            />
          );
        })}
      </group>

      {/* Cross-function beams — persistent teal lines, thickness scaled
          by weight (capped so a hot entity storm doesn't drown out the
          rest of the scene). */}
      <group>
        {beams.map((b) => {
          const a = floorFrontCentre(b.fromFn);
          const z = floorFrontCentre(b.toFn);
          if (!a || !z) return null;
          const thickness = Math.min(4, 0.6 + b.weight * 0.4);
          return (
            <Line
              key={`${b.fromFn}-${b.toFn}`}
              points={[a, z]}
              color={ANIM_COLORS.beam}
              lineWidth={thickness}
              transparent
              opacity={0.55}
              toneMapped={false}
            />
          );
        })}
      </group>
    </group>
  );
}

function filamentPoints(e: AnimEntry): [number, number, number][] | null {
  if (!e.to) return null;
  const from = new THREE.Vector3(...e.from);
  const to = new THREE.Vector3(...e.to);
  const tmp = new THREE.Vector3();
  const N = 20;
  // Reveal the arc as `t` advances — the head walks ahead of the tail.
  const head = Math.min(1, e.t * 1.4);
  const tail = Math.max(0, e.t * 1.4 - 0.6);
  const out: [number, number, number][] = [];
  for (let i = 0; i <= N; i += 1) {
    const u = tail + (head - tail) * (i / N);
    bezier(from, to, u, tmp);
    out.push([tmp.x, tmp.y, tmp.z]);
  }
  return out;
}

/**
 * RocketExhaust — GPU particle plume that trails a moving rocket.
 *
 * Replaces the line-segment Trails rendering for in-flight rockets. Each
 * particle is a soft additive point sprite that spawns at the rocket's nozzle
 * (just behind the engine), drifts back along the inverse of its travel
 * velocity, expands slightly, and fades over ~1s. Dense regions accumulate
 * into a luminous plume; sparse regions look like wispy contrail.
 *
 * Architecture
 * ────────────
 *   • `ExhaustRegistry` (defined here) owns a single GPU buffer of up to
 *     MAX_PARTICLES slots. Rockets push emit requests via `registry.emit`,
 *     which finds an inactive slot and seeds it.
 *   • `<RocketExhaust>` runs a useFrame loop that advances every active
 *     particle (age, position, alpha) and updates the BufferAttributes.
 *   • The rendering is a single Points mesh with a custom ShaderMaterial —
 *     ONE draw call regardless of particle count. Soft circular alpha falloff
 *     in the fragment shader.
 *
 * Why not <Trails>? Line segments rendered with WebGL2 have a fixed 1px
 * width and turn into hard candy-stripes after bloom. Particles look soft,
 * volumetric, and read as 'engine plume' instead of 'wireframe path'.
 */
import { useMemo, useRef } from "react";
import * as THREE from "three";
import { useFrame } from "@react-three/fiber";

const MAX_PARTICLES = 2400;

/** Parsed colour cache so we don't re-parse `#rrggbb` every emit. */
const _colorCache = new Map<string, THREE.Color>();
function _parseColor(c: string): THREE.Color {
  const cached = _colorCache.get(c);
  if (cached) return cached;
  const col = new THREE.Color(c);
  _colorCache.set(c, col);
  return col;
}

/** Simple ring-buffer registry for rocket particle emissions. Mutates a
 *  shared Float32Array storage. The Points mesh reads the same arrays —
 *  no copies. */
export class ExhaustRegistry {
  positions: Float32Array;
  velocities: Float32Array;
  colors: Float32Array;
  ages: Float32Array;
  lifetimes: Float32Array;
  sizes: Float32Array;
  /** 0 = inactive (free slot), >0 = active. Use a Uint8Array for compactness. */
  active: Uint8Array;
  /** Hint: where to start scanning for free slots. Wraps. */
  cursor: number = 0;
  /** Bumped whenever any slot changes — useFrame uses this to know it should
   *  flush BufferAttributes back to the GPU. Updated continuously by the
   *  rendering useFrame so always >0; left as a counter for parity with
   *  TrailRegistry. */
  version: number = 0;

  constructor() {
    this.positions = new Float32Array(MAX_PARTICLES * 3);
    this.velocities = new Float32Array(MAX_PARTICLES * 3);
    this.colors = new Float32Array(MAX_PARTICLES * 3);
    this.ages = new Float32Array(MAX_PARTICLES);
    this.lifetimes = new Float32Array(MAX_PARTICLES);
    this.sizes = new Float32Array(MAX_PARTICLES);
    this.active = new Uint8Array(MAX_PARTICLES);
  }

  /** Find a free slot starting at `cursor`. Linear scan, wraps. Returns -1
   *  if all slots are active (caller should drop the emission). */
  private _allocate(): number {
    for (let i = 0; i < MAX_PARTICLES; i++) {
      const idx = (this.cursor + i) % MAX_PARTICLES;
      if (this.active[idx] === 0) {
        this.cursor = (idx + 1) % MAX_PARTICLES;
        return idx;
      }
    }
    return -1;
  }

  emit(
    pos: [number, number, number],
    velocity: [number, number, number],
    color: string,
    /** seconds */ lifetime = 1.0,
    size = 0.18,
  ): void {
    const slot = this._allocate();
    if (slot < 0) return;
    const i3 = slot * 3;
    this.positions[i3 + 0] = pos[0];
    this.positions[i3 + 1] = pos[1];
    this.positions[i3 + 2] = pos[2];
    this.velocities[i3 + 0] = velocity[0];
    this.velocities[i3 + 1] = velocity[1];
    this.velocities[i3 + 2] = velocity[2];
    const col = _parseColor(color);
    this.colors[i3 + 0] = col.r;
    this.colors[i3 + 1] = col.g;
    this.colors[i3 + 2] = col.b;
    this.ages[slot] = 0;
    this.lifetimes[slot] = lifetime;
    this.sizes[slot] = size;
    this.active[slot] = 1;
  }
}

const VERT = /* glsl */ `
  attribute float aAge;
  attribute float aLifetime;
  attribute float aSize;
  attribute vec3 aColor;
  varying float vAlpha;
  varying vec3 vColor;
  void main() {
    vec4 mvPosition = modelViewMatrix * vec4(position, 1.0);
    float lifeT = clamp(aAge / max(aLifetime, 0.001), 0.0, 1.0);
    // Particles START at full opacity then fade — simple curve so the engine
    // looks brightest right at the nozzle.
    vAlpha = pow(1.0 - lifeT, 1.4);
    vColor = aColor;
    // Particles GROW as they age, so the plume feathers out behind the rocket.
    float currentSize = aSize * (0.6 + 1.2 * lifeT);
    // Scale point size by distance for perspective consistency.
    gl_PointSize = currentSize * (300.0 / -mvPosition.z);
    gl_Position = projectionMatrix * mvPosition;
  }
`;

const FRAG = /* glsl */ `
  varying float vAlpha;
  varying vec3 vColor;
  void main() {
    vec2 d = gl_PointCoord - vec2(0.5);
    float dist = length(d);
    if (dist > 0.5) discard;
    // Smooth circular falloff — concentrated centre, soft edges. Multiplied
    // by the per-particle age fade.
    float falloff = pow(1.0 - dist * 2.0, 1.8);
    gl_FragColor = vec4(vColor, vAlpha * falloff);
  }
`;

interface RocketExhaustProps {
  registry: ExhaustRegistry;
}

export function RocketExhaust({ registry }: RocketExhaustProps) {
  const pointsRef = useRef<THREE.Points>(null);
  // The buffer attributes share the SAME backing arrays as the registry —
  // no copies. We just flip needsUpdate every frame.
  const geometry = useMemo(() => {
    const geom = new THREE.BufferGeometry();
    geom.setAttribute("position", new THREE.BufferAttribute(registry.positions, 3));
    geom.setAttribute("aColor", new THREE.BufferAttribute(registry.colors, 3));
    geom.setAttribute("aAge", new THREE.BufferAttribute(registry.ages, 1));
    geom.setAttribute("aLifetime", new THREE.BufferAttribute(registry.lifetimes, 1));
    geom.setAttribute("aSize", new THREE.BufferAttribute(registry.sizes, 1));
    geom.setDrawRange(0, MAX_PARTICLES);
    geom.boundingSphere = new THREE.Sphere(new THREE.Vector3(), 1000);
    return geom;
  }, [registry]);

  const material = useMemo(
    () =>
      new THREE.ShaderMaterial({
        vertexShader: VERT,
        fragmentShader: FRAG,
        transparent: true,
        depthWrite: false,
        blending: THREE.AdditiveBlending,
      }),
    [],
  );

  useFrame((_state, delta) => {
    const dt = Math.min(delta, 0.06);
    const positions = registry.positions;
    const velocities = registry.velocities;
    const ages = registry.ages;
    const lifetimes = registry.lifetimes;
    const active = registry.active;

    for (let i = 0; i < MAX_PARTICLES; i++) {
      if (active[i] === 0) continue;
      ages[i] += dt;
      if (ages[i] >= lifetimes[i]) {
        active[i] = 0;
        // Park dead particle far away so it doesn't pop in if the geometry
        // somehow renders it during the flush.
        const i3 = i * 3;
        positions[i3 + 0] = 0;
        positions[i3 + 1] = -10000;
        positions[i3 + 2] = 0;
        continue;
      }
      const i3 = i * 3;
      positions[i3 + 0] += velocities[i3 + 0] * dt;
      positions[i3 + 1] += velocities[i3 + 1] * dt;
      positions[i3 + 2] += velocities[i3 + 2] * dt;
      // Slight drag so velocity decays — particles slow down behind the
      // rocket instead of streaking out forever, looks more like real
      // exhaust diffusing in space.
      velocities[i3 + 0] *= 1 - 0.7 * dt;
      velocities[i3 + 1] *= 1 - 0.7 * dt;
      velocities[i3 + 2] *= 1 - 0.7 * dt;
    }

    if (!pointsRef.current) return;
    const geom = pointsRef.current.geometry;
    (geom.attributes.position as THREE.BufferAttribute).needsUpdate = true;
    (geom.attributes.aAge as THREE.BufferAttribute).needsUpdate = true;
    registry.version++;
  });

  return (
    <points ref={pointsRef} geometry={geometry} material={material} frustumCulled={false} />
  );
}

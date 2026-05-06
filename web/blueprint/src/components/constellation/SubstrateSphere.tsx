/**
 * The substrate sphere — the centre of the Constellation.
 *
 * Renders ~2400 dots on a sunflower-coiled unit sphere, each one a vertex
 * of a single THREE.Points. Dots have a per-vertex colour attribute that
 * we mutate every frame to apply pulse decay.
 *
 * Resting state: every dot twinkles at low intensity tinted by category
 * (skills warm, tools cool-ish, validators slightly warmer). When a pulse
 * fires for a dot, that dot brightens to amber (or red if blocked) and
 * decays over ~1.2s.
 */

import { useFrame } from "@react-three/fiber";
import { useEffect, useMemo, useRef } from "react";
import * as THREE from "three";

import { sunflowerSphere } from "../../lib/constellation/sunflower";
import type { Pulse, SubstrateMap } from "../../lib/constellation/types";
import { SUBSTRATE_RADIUS } from "../../lib/constellation/types";

interface Props {
  substrate: SubstrateMap;
  /** Live ref to the rolling pulse list, mutated outside React. */
  pulsesRef: React.MutableRefObject<Pulse[]>;
  /** Sphere radius in scene units. */
  radius?: number;
  /** Optional caption (e.g. "the substrate"). */
}

const PULSE_DECAY_MS = 1400;

// Resting palette — kept very dim so the sphere reads as the substrate
// breathing, not as a Christmas tree.
const COL_FILLER = new THREE.Color("#3a342a"); // warm grey-brown
const COL_SKILL = new THREE.Color("#5a4824"); // dim warm
const COL_TOOL = new THREE.Color("#3d4658"); // dim cool
const COL_VALIDATOR = new THREE.Color("#5a3024"); // dim warm-red

const COL_PULSE_SKILL = new THREE.Color("#f4a300"); // amber — matches HUD legend
const COL_PULSE_TOOL = new THREE.Color("#7faed4"); // cool blue — matches HUD legend
const COL_PULSE_VALIDATOR = new THREE.Color("#c54a3d"); // red — alarm, only on .blocked

export function SubstrateSphere({
  substrate,
  pulsesRef,
  radius = SUBSTRATE_RADIUS,
}: Props) {
  const pointsRef = useRef<THREE.Points>(null);

  const geometry = useMemo(() => {
    const positions = sunflowerSphere(substrate.total, radius);
    const geom = new THREE.BufferGeometry();
    const posArr = new Float32Array(substrate.total * 3);
    const colArr = new Float32Array(substrate.total * 3);
    const sizeArr = new Float32Array(substrate.total);
    for (let i = 0; i < substrate.total; i++) {
      const p = positions[i];
      posArr[i * 3] = p.x;
      posArr[i * 3 + 1] = p.y;
      posArr[i * 3 + 2] = p.z;
      const cat = substrate.category[i];
      const c =
        cat === 1
          ? COL_SKILL
          : cat === 2
          ? COL_TOOL
          : cat === 3
          ? COL_VALIDATOR
          : COL_FILLER;
      colArr[i * 3] = c.r;
      colArr[i * 3 + 1] = c.g;
      colArr[i * 3 + 2] = c.b;
      sizeArr[i] = cat === 0 ? 0.022 : 0.034;
    }
    geom.setAttribute("position", new THREE.BufferAttribute(posArr, 3));
    geom.setAttribute("color", new THREE.BufferAttribute(colArr, 3));
    geom.setAttribute("size", new THREE.BufferAttribute(sizeArr, 1));
    return geom;
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [substrate.total, radius]);

  // Cached resting colour so we know what to fade back to per dot.
  const restingColors = useMemo(() => {
    const arr = new Float32Array(substrate.total * 3);
    for (let i = 0; i < substrate.total; i++) {
      const cat = substrate.category[i];
      const c =
        cat === 1
          ? COL_SKILL
          : cat === 2
          ? COL_TOOL
          : cat === 3
          ? COL_VALIDATOR
          : COL_FILLER;
      arr[i * 3] = c.r;
      arr[i * 3 + 1] = c.g;
      arr[i * 3 + 2] = c.b;
    }
    return arr;
  }, [substrate]);

  // Per-dot phase for the resting twinkle — random offsets so the sphere
  // doesn't pulse in unison.
  const twinklePhase = useMemo(() => {
    const arr = new Float32Array(substrate.total);
    for (let i = 0; i < substrate.total; i++) {
      arr[i] = Math.random() * Math.PI * 2;
    }
    return arr;
  }, [substrate.total]);

  useEffect(() => {
    return () => {
      geometry.dispose();
    };
  }, [geometry]);

  useFrame(({ clock }) => {
    const points = pointsRef.current;
    if (!points) return;
    const colorAttr = points.geometry.getAttribute(
      "color",
    ) as THREE.BufferAttribute;
    const arr = colorAttr.array as Float32Array;
    const t = clock.getElapsedTime();
    const now = performance.now();

    // Reset to resting colour + add subtle twinkle.
    for (let i = 0; i < substrate.total; i++) {
      const r = restingColors[i * 3];
      const g = restingColors[i * 3 + 1];
      const b = restingColors[i * 3 + 2];
      // 0.6 .. 1.4 modulation — keeps sphere alive when nothing is pulsing.
      const tw = 0.7 + 0.5 * (0.5 + 0.5 * Math.sin(t * 1.6 + twinklePhase[i]));
      arr[i * 3] = r * tw;
      arr[i * 3 + 1] = g * tw;
      arr[i * 3 + 2] = b * tw;
    }

    // Apply active pulses on top.
    const pulses = pulsesRef.current;
    let writeIdx = 0;
    for (let p = 0; p < pulses.length; p++) {
      const pulse = pulses[p];
      const age = now - pulse.startMs;
      if (age >= PULSE_DECAY_MS) continue; // drop dead pulse
      const k = 1 - age / PULSE_DECAY_MS;
      const targetCol =
        pulse.kind === "validator"
          ? COL_PULSE_VALIDATOR
          : pulse.kind === "tool"
          ? COL_PULSE_TOOL
          : COL_PULSE_SKILL;
      const idx = pulse.dotIdx * 3;
      // Lerp from resting toward pulse colour by k.
      arr[idx] = arr[idx] * (1 - k) + targetCol.r * k * 1.3;
      arr[idx + 1] = arr[idx + 1] * (1 - k) + targetCol.g * k * 1.3;
      arr[idx + 2] = arr[idx + 2] * (1 - k) + targetCol.b * k * 1.3;
      // Compact still-alive pulses into the front of the array.
      pulses[writeIdx++] = pulse;
    }
    pulses.length = writeIdx;

    colorAttr.needsUpdate = true;
  });

  return (
    <points ref={pointsRef} geometry={geometry}>
      <pointsMaterial
        vertexColors
        size={0.05}
        sizeAttenuation
        transparent
        opacity={0.95}
        depthWrite={false}
        blending={THREE.AdditiveBlending}
      />
    </points>
  );
}

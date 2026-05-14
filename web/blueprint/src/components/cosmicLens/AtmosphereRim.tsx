/**
 * AtmosphereRim — a transparent shell rendered around a planet that produces
 * a fresnel-based limb glow. It's the visual signature of "this planet has
 * an atmosphere and you can see it from space" — a Mass Effect / Interstellar
 * staple.
 *
 * Implementation:
 *   • Slightly-larger sphere (1.06× by default), BackSide rendering so we
 *     see the FAR side from the camera. The far side has its normals pointing
 *     toward us at the limb — that's how the fresnel term reads "edge".
 *   • Fragment shader: alpha = pow(1 - dot(normal, viewDir), power)
 *     × intensity — opaque only at grazing angles, transparent in the middle
 *     so we still see the planet body underneath.
 *   • Additive blending so the rim "lights up" against the dark backdrop
 *     without darkening the planet behind it.
 *
 * Wrap a planet by placing this in the same parent group and giving it the
 * same world transform.
 */
import { useMemo } from "react";
import * as THREE from "three";

const VERT = /* glsl */ `
  varying vec3 vNormal;
  varying vec3 vViewDir;
  void main() {
    vec4 worldPos = modelMatrix * vec4(position, 1.0);
    vNormal = normalize(mat3(modelMatrix) * normal);
    vViewDir = normalize(cameraPosition - worldPos.xyz);
    gl_Position = projectionMatrix * viewMatrix * worldPos;
  }
`;

const FRAG = /* glsl */ `
  uniform vec3 uColor;
  uniform float uIntensity;
  uniform float uPower;
  varying vec3 vNormal;
  varying vec3 vViewDir;
  void main() {
    // BackSide rendering means our normals face inward; flip so the fresnel
    // term reads "1 at the limb, 0 in the middle" the way we want.
    vec3 n = -normalize(vNormal);
    float facing = max(0.0, dot(n, vViewDir));
    float rim = pow(1.0 - facing, uPower);
    gl_FragColor = vec4(uColor * uIntensity, rim);
  }
`;

interface AtmosphereRimProps {
  radius: number;
  color: string;
  /** Multiplier on the planet radius — 1.06 is a tight halo, 1.15 is hazy. */
  scale?: number;
  /** How quickly opacity falls off from limb to centre. Higher = thinner band. */
  power?: number;
  intensity?: number;
}

export function AtmosphereRim({
  radius,
  color,
  scale = 1.08,
  power = 2.4,
  intensity = 1.2,
}: AtmosphereRimProps) {
  const material = useMemo(
    () =>
      new THREE.ShaderMaterial({
        vertexShader: VERT,
        fragmentShader: FRAG,
        uniforms: {
          uColor: { value: new THREE.Color(color) },
          uIntensity: { value: intensity },
          uPower: { value: power },
        },
        side: THREE.BackSide,
        transparent: true,
        blending: THREE.AdditiveBlending,
        depthWrite: false,
      }),
    [color, intensity, power],
  );
  return (
    <mesh scale={scale}>
      <sphereGeometry args={[radius, 32, 32]} />
      <primitive object={material} attach="material" />
    </mesh>
  );
}

/**
 * AnamorphicFlare — a horizontal cinematic light streak that always faces
 * the camera. Wraps a transparent additive billboard with a custom shader
 * that produces:
 *
 *   • a bright central core
 *   • a long horizontal streak (the "anamorphic" lens artifact you see in
 *     Mass Effect / Star Trek / J.J. Abrams films)
 *   • a faint vertical secondary streak so the cross-hair has presence
 *
 * No postprocessing pass — pure billboard quad with a fragment shader.
 * Runs in the regular scene, plays nicely with bloom (it's already
 * additive, so bloom just feathers the streak's edges further).
 *
 * Designed to be DEPLOYED SPARINGLY — only on the brightest 1-2 objects in
 * the scene at a time. Overusing it kills the calm cinematic mood and
 * tips the look into Bay-style action movie. The intensity prop should
 * generally cap at 0.7.
 */
import { useMemo, useRef } from "react";
import * as THREE from "three";
import { useFrame } from "@react-three/fiber";

const VERT = /* glsl */ `
  varying vec2 vUv;
  void main() {
    vUv = uv;
    gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0);
  }
`;

const FRAG = /* glsl */ `
  uniform vec3 uColor;
  uniform float uIntensity;
  varying vec2 vUv;
  void main() {
    // Centre quad in [-0.5, 0.5] × [-0.5, 0.5]
    vec2 p = vUv - 0.5;

    // Bright central core — small radial falloff
    float core = exp(-180.0 * dot(p, p));

    // Horizontal streak — long, thin. Decays fast on Y, slowly on X.
    float streakX = exp(-180.0 * p.y * p.y) * exp(-3.0 * p.x * p.x);

    // Vertical secondary streak — shorter, even thinner. Adds the
    // 'cross-hair' silhouette without dominating.
    float streakY = exp(-220.0 * p.x * p.x) * exp(-22.0 * p.y * p.y);

    // Subtle hexagonal lens-element ghosts at fixed positions across the
    // streak — three small dots that read as 'real lens optics'.
    float ghosts = 0.0;
    for (int i = 0; i < 3; i++) {
      float u = float(i) * 0.16 - 0.24;  // -0.24, -0.08, 0.08
      vec2 g = p - vec2(u, 0.0);
      ghosts += exp(-1200.0 * dot(g, g)) * 0.55;
    }

    float a = core * 1.6 + streakX * 0.55 + streakY * 0.18 + ghosts * 0.7;
    a *= uIntensity;
    gl_FragColor = vec4(uColor, a);
  }
`;

interface AnamorphicFlareProps {
  /** World-space position to anchor the flare to. */
  position?: [number, number, number];
  color?: string;
  /** 0..1, capped soft at ~0.7 to stay cinematic. */
  intensity?: number;
  /** Quad size in world units. */
  size?: number;
}

export function AnamorphicFlare({
  position = [0, 0, 0],
  color = "#9bd0ff",
  intensity = 0.5,
  size = 4.0,
}: AnamorphicFlareProps) {
  const meshRef = useRef<THREE.Mesh>(null);

  const material = useMemo(
    () =>
      new THREE.ShaderMaterial({
        vertexShader: VERT,
        fragmentShader: FRAG,
        uniforms: {
          uColor: { value: new THREE.Color(color) },
          uIntensity: { value: intensity },
        },
        transparent: true,
        depthWrite: false,
        depthTest: false,
        blending: THREE.AdditiveBlending,
      }),
    [color],
  );

  // Always face the camera. Cheaper than wrapping in <Billboard> from drei.
  useFrame((state) => {
    if (!meshRef.current) return;
    meshRef.current.quaternion.copy(state.camera.quaternion);
  });

  // Update intensity each render in case the prop changes (busy planet
  // glowing more than an idle one). Material is shared, so we mutate the
  // uniform directly rather than re-creating.
  if (material.uniforms.uIntensity.value !== intensity) {
    material.uniforms.uIntensity.value = intensity;
  }

  return (
    <mesh
      ref={meshRef}
      position={position}
      renderOrder={5}
    >
      <planeGeometry args={[size, size * 0.4]} />
      <primitive object={material} attach="material" />
    </mesh>
  );
}

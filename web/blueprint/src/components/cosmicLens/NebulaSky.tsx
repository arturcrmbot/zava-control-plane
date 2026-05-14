/**
 * NebulaSky — replaces the bare-black void with a layered Mass Effect /
 * Interstellar style cosmic backdrop.
 *
 * Composition (front-to-back):
 *   1. Foreground stars (drei <Stars>) — the existing twinkly near-field
 *   2. NEW far-field star layer (Points)              — denser, dimmer, bigger radius
 *   3. NEW nebula sphere (inverted-normals ShaderMaterial)
 *      Procedural multi-octave noise → cloudy gas. Deep navy at the edges,
 *      indigo / violet mid-tones, a warm pink-orange "galactic core" tilted
 *      slightly off-axis. Subtle dust band along the equator.
 *
 * All static geometry — no per-frame work beyond the existing star twinkle —
 * so it costs ~zero frames to add. The shader is GPU-only and runs in the
 * fragment stage on a single sphere mesh.
 */
import { useMemo } from "react";
import * as THREE from "three";
import { Stars } from "@react-three/drei";

const NEBULA_VERT = /* glsl */ `
  varying vec3 vDir;
  void main() {
    // World-space direction from origin to vertex — the skybox sphere is
    // centered on origin, so this doubles as the "ray direction" we sample
    // the noise field along.
    vDir = normalize(position);
    gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0);
  }
`;

// fBm noise — classic 4-octave hash-based 3D noise. Cheap on GPU, gives the
// soft cloudy gas we want. Not perlin/simplex because we don't need
// derivatives and a hash is one less import surface.
const NEBULA_FRAG = /* glsl */ `
  varying vec3 vDir;

  // Hash + value noise (Inigo Quilez style)
  float hash(vec3 p) {
    p = fract(p * 0.3183099 + 0.1);
    p *= 17.0;
    return fract(p.x * p.y * p.z * (p.x + p.y + p.z));
  }
  float noise(vec3 x) {
    vec3 p = floor(x);
    vec3 f = fract(x);
    f = f * f * (3.0 - 2.0 * f);
    return mix(mix(mix(hash(p + vec3(0,0,0)), hash(p + vec3(1,0,0)), f.x),
                   mix(hash(p + vec3(0,1,0)), hash(p + vec3(1,1,0)), f.x), f.y),
               mix(mix(hash(p + vec3(0,0,1)), hash(p + vec3(1,0,1)), f.x),
                   mix(hash(p + vec3(0,1,1)), hash(p + vec3(1,1,1)), f.x), f.y), f.z);
  }
  float fbm(vec3 p) {
    float v = 0.0;
    float a = 0.5;
    for (int i = 0; i < 5; i++) {
      v += a * noise(p);
      p *= 2.02;
      a *= 0.5;
    }
    return v;
  }

  void main() {
    // Stretch the noise field so the nebula has a long-axis grain — gives the
    // sky a sense of "this scene has direction" rather than uniform fuzz.
    vec3 p = vDir * 2.4;
    p.x *= 1.4;
    p.z *= 0.85;

    float n = fbm(p);
    float n2 = fbm(p * 2.7 + vec3(7.3, 1.1, 4.9));

    // Galactic band: a soft horizontal streak slightly off-axis. Tilt the
    // band by mixing y and z so it doesn't look like a perfect ring.
    float bandY = vDir.y * 0.85 + vDir.z * 0.15;
    float band = exp(-12.0 * bandY * bandY);

    // Galactic core: a single warm hotspot a bit off-center. We compute
    // distance from a fixed direction (toward +X +Z) so the bright pink-
    // orange smear sits to one side and doesn't dominate.
    vec3 coreDir = normalize(vec3(0.6, 0.05, 0.8));
    float coreFalloff = pow(max(0.0, dot(vDir, coreDir)), 14.0);

    // Density is a combination of fbm + the band — clamps so we don't get
    // any super-bright artifacts.
    float density = clamp(0.35 * n + 0.25 * n2 + 0.55 * band * (0.4 + 0.6 * n2), 0.0, 1.0);

    // Palette — deep indigo void → cooler blue → cyan highlights → warm core.
    vec3 voidColour    = vec3(0.012, 0.018, 0.058);   // deep navy
    vec3 indigoColour  = vec3(0.05, 0.05, 0.16);      // dusty indigo
    vec3 violetColour  = vec3(0.16, 0.10, 0.32);      // soft violet
    vec3 cyanColour    = vec3(0.10, 0.30, 0.55);      // cool cyan haze
    vec3 coreColour    = vec3(0.78, 0.36, 0.42);      // warm rose/orange
    vec3 hotCore       = vec3(0.95, 0.62, 0.45);      // warm peach

    vec3 col = voidColour;
    col = mix(col, indigoColour, smoothstep(0.20, 0.55, density));
    col = mix(col, violetColour, smoothstep(0.45, 0.80, density));
    col = mix(col, cyanColour,   smoothstep(0.65, 0.95, density) * 0.55);
    col = mix(col, coreColour,   coreFalloff * 0.7);
    col = mix(col, hotCore,      coreFalloff * pow(density, 1.4) * 1.4);

    // High-frequency sparkle — a few hot pinpricks scattered through the
    // densest regions so the gas has 'star-forming' texture.
    float sparkle = pow(noise(p * 32.0), 18.0) * smoothstep(0.5, 0.9, density);
    col += vec3(0.7, 0.85, 1.0) * sparkle * 0.6;

    // Tone the whole sky down a touch so foreground objects (planets,
    // rockets) still pop after bloom.
    col *= 0.85;

    gl_FragColor = vec4(col, 1.0);
  }
`;

export function NebulaSky() {
  const material = useMemo(() => {
    return new THREE.ShaderMaterial({
      vertexShader: NEBULA_VERT,
      fragmentShader: NEBULA_FRAG,
      side: THREE.BackSide,
      depthWrite: false,
      depthTest: false,
    });
  }, []);

  // Far-field stars: denser + bigger radius than the main starfield so we
  // get parallax — closer stars drift visibly when the camera orbits, the
  // far ones barely move.
  const farStarPoints = useMemo(() => {
    const count = 1800;
    const positions = new Float32Array(count * 3);
    const colours = new Float32Array(count * 3);
    for (let i = 0; i < count; i++) {
      // Place uniformly on a sphere of radius ~140 (well beyond the
      // nebula sphere at 80) so they read as 'distant universe'.
      const u = Math.random() * 2 - 1;
      const t = Math.random() * Math.PI * 2;
      const r = Math.sqrt(1 - u * u);
      const radius = 140 + Math.random() * 30;
      positions[i * 3 + 0] = r * Math.cos(t) * radius;
      positions[i * 3 + 1] = u * radius;
      positions[i * 3 + 2] = r * Math.sin(t) * radius;
      // Slight tint variation so the field doesn't read as uniform white.
      const tint = 0.55 + Math.random() * 0.45;
      const cool = 0.85 + Math.random() * 0.15;
      colours[i * 3 + 0] = tint * cool;
      colours[i * 3 + 1] = tint;
      colours[i * 3 + 2] = tint * (cool + 0.05);
    }
    const geom = new THREE.BufferGeometry();
    geom.setAttribute("position", new THREE.BufferAttribute(positions, 3));
    geom.setAttribute("color", new THREE.BufferAttribute(colours, 3));
    return geom;
  }, []);

  return (
    <group>
      {/* Nebula skybox — must render first so everything else paints over it.
          We push it explicitly to renderOrder = -2 and disable depth so the
          BackSide sphere doesn't fight other geometry's depth tests. */}
      <mesh renderOrder={-2}>
        <sphereGeometry args={[80, 32, 32]} />
        <primitive object={material} attach="material" />
      </mesh>

      {/* Far-field stars — between the nebula and the existing near stars.
          Uses additive vertex-coloured Points so dense regions don't blow out. */}
      <points geometry={farStarPoints} renderOrder={-1}>
        <pointsMaterial
          size={0.85}
          sizeAttenuation={false}
          vertexColors
          transparent
          opacity={0.65}
          depthWrite={false}
          blending={THREE.AdditiveBlending}
        />
      </points>

      {/* Existing twinkly near-field stars on top. Slightly fewer than before
          (was 2500) since we now have a second layer behind, and with
          saturation up so they pick up the nebula tint. */}
      <Stars
        radius={70}
        depth={45}
        count={1800}
        factor={3.5}
        saturation={0.85}
        fade
        speed={0.35}
      />
    </group>
  );
}

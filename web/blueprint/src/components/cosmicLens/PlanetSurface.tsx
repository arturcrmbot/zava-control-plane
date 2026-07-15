/**
 * PlanetSurface — replaces the flat-shaded glowing-ball planet with a
 * procedurally-textured 'real planet' surface shader.
 *
 * What the shader does (fragment):
 *   • fBm noise on the world-space normal direction → continent mask
 *   • Two-band palette: ocean (cool, slightly emissive) vs land (warm,
 *     slightly varied per altitude band)
 *   • Day/night terminator: `lit = dot(N, lightDir)` with a soft band
 *     near zero so the line between day and night feathers, and the
 *     night side keeps a faint emissive city-glow rather than going
 *     pure black
 *   • Sub-band fine noise for surface texture (small-scale detail
 *     visible only when zoomed in)
 *   • Per-planet noise seed via uniform so every planet is unique while
 *     sharing the same shader code
 *
 * What it intentionally does NOT do:
 *   • No real PBR — these are stylised 'demo' planets, lit by a single
 *     fixed sci-fi 'system star' direction in shader space, not by the
 *     scene's lights. Keeps frame cost flat regardless of how many
 *     directional lights are in the scene.
 *   • No water specular — would give Earth-too-realistic vibe; we want
 *     a stylised cinematic look that doesn't try to be NASA.
 *
 * Sister component: AtmosphereRim is rendered around this on a 1.10×
 * outer sphere to provide the bright limb glow.
 */
import { useMemo } from "react";
import * as THREE from "three";
import { useFrame } from "@react-three/fiber";

const VERT = /* glsl */ `
  varying vec3 vNormal;
  varying vec3 vWorldPos;
  void main() {
    vNormal = normalize(normalMatrix * normal);
    vWorldPos = (modelMatrix * vec4(position, 1.0)).xyz;
    gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0);
  }
`;

export const FRAG = /* glsl */ `
  uniform vec3  uOcean;
  uniform vec3  uLand;
  uniform vec3  uHighland;
  uniform vec3  uNightGlow;
  uniform float uSeed;
  uniform float uTime;

  varying vec3 vNormal;
  varying vec3 vWorldPos;

  // Hash + value noise (Inigo Quilez)
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
      p *= 2.05;
      a *= 0.5;
    }
    return v;
  }

  void main() {
    // Sample noise on the *normal* direction (sphere surface) so the
    // pattern wraps cleanly around the planet without UV seams. Add a
    // per-planet seed so every planet looks distinct.
    vec3 noisePoint = normalize(vNormal) * 2.4 + vec3(uSeed * 13.7);
    float continent = fbm(noisePoint);
    float detail    = fbm(noisePoint * 6.0);

    // Continents are where high-density noise lives. Smooth band so
    // shorelines feather rather than jaggy.
    float landMask  = smoothstep(0.46, 0.58, continent);

    // Two-tone surface — ocean colour where mask is low, land where high,
    // and a third 'highland' tint at the densest peaks for variety.
    vec3 surface = uOcean;
    surface = mix(surface, uLand,     landMask);
    surface = mix(surface, uHighland, smoothstep(0.62, 0.78, continent));

    // Sub-band noise modulates land brightness — gives 'terrain' feel
    // without turning into a fractal canvas.
    surface *= (0.85 + 0.30 * detail);

    // Day / night lighting from a fixed sci-fi 'system star' direction.
    // Smoothstep for a feathered terminator instead of a hard line.
    vec3 lightDir = normalize(vec3(0.7, 0.45, 0.55));
    float lit = dot(normalize(vNormal), lightDir);
    float day = smoothstep(-0.15, 0.35, lit);

    // Night side gets a faint warm city-glow tinted to the planet's own
    // colour palette — reads as an inhabited world rather than a barren
    // rock. Only visible where the surface IS land (not ocean).
    vec3 nightSide = uNightGlow * landMask * 0.5;
    vec3 finalColour = mix(nightSide, surface, day);

    gl_FragColor = vec4(finalColour, 1.0);
  }
`;

interface Props {
  radius: number;
  /** Function/domain colour — drives the surface palette so each planet
   *  reads as an extension of its function's identity. */
  color: string;
  /** Stable per-planet seed so each planet looks unique. Hash of the
   *  function key is plenty. */
  seed: number;
  /** Slow Y rotation (rad/s). Per-planet so they desync. */
  rotationSpeed?: number;
}

export function PlanetSurface({ radius, color, seed, rotationSpeed = 0.08 }: Props) {
  const meshRef = useMemo(() => ({ current: null as THREE.Mesh | null }), []);

  // Build palette from the function colour: ocean is a darker variant,
  // land sits at the colour, highland is brighter, night-glow is warm.
  const material = useMemo(() => {
    const base = new THREE.Color(color);
    const ocean = base.clone().multiplyScalar(0.35);
    const land = base.clone().multiplyScalar(0.95);
    const highland = base.clone().lerp(new THREE.Color("#ffffff"), 0.35);
    // Night glow: warm tint (city lights) tinted SLIGHTLY by the planet
    // colour so it doesn't clash with the day side.
    const nightGlow = base.clone().lerp(new THREE.Color("#ffb86b"), 0.45).multiplyScalar(0.7);

    return new THREE.ShaderMaterial({
      vertexShader: VERT,
      fragmentShader: FRAG,
      uniforms: {
        uOcean: { value: ocean },
        uLand: { value: land },
        uHighland: { value: highland },
        uNightGlow: { value: nightGlow },
        uSeed: { value: seed * 0.001 },
        uTime: { value: 0 },
      },
    });
  }, [color, seed]);

  useFrame((state) => {
    if (meshRef.current) {
      meshRef.current.rotation.y = state.clock.elapsedTime * rotationSpeed;
    }
    if (material.uniforms.uTime) {
      material.uniforms.uTime.value = state.clock.elapsedTime;
    }
  });

  return (
    <mesh
      ref={(m) => {
        meshRef.current = m;
      }}
      castShadow
    >
      <sphereGeometry args={[radius, 48, 32]} />
      <primitive object={material} attach="material" />
    </mesh>
  );
}

/**
 * CloudLayer — a thin transparent shell rendered slightly above the
 * planet surface (1.02× radius) with a separate fbm noise pattern that
 * rotates a touch faster than the planet body. Cloud strength threshold
 * via smoothstep so we get cloud BANDS rather than a uniform fog.
 */
export const CLOUD_FRAG = /* glsl */ `
  uniform float uSeed;
  uniform float uTime;
  varying vec3 vNormal;

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
    for (int i = 0; i < 4; i++) {
      v += a * noise(p);
      p *= 2.05;
      a *= 0.5;
    }
    return v;
  }

  void main() {
    vec3 noisePoint = normalize(vNormal) * 3.2 + vec3(uSeed * 7.3);
    float c = fbm(noisePoint);
    float cloudMask = smoothstep(0.55, 0.78, c);
    vec3 lightDir = normalize(vec3(0.7, 0.45, 0.55));
    float lit = max(0.0, dot(normalize(vNormal), lightDir));
    float day = smoothstep(0.0, 0.35, lit);
    gl_FragColor = vec4(vec3(1.0, 0.97, 0.94), cloudMask * 0.55 * day);
  }
`;

const CLOUD_VERT = VERT;

export function PlanetClouds({ radius, seed, rotationSpeed = 0.018 }: { radius: number; seed: number; rotationSpeed?: number }) {
  const meshRef = useMemo(() => ({ current: null as THREE.Mesh | null }), []);
  const material = useMemo(
    () =>
      new THREE.ShaderMaterial({
        vertexShader: CLOUD_VERT,
        fragmentShader: CLOUD_FRAG,
        uniforms: {
          uSeed: { value: seed * 0.0017 + 0.31 },
          uTime: { value: 0 },
        },
        transparent: true,
        depthWrite: false,
      }),
    [seed],
  );

  useFrame((state) => {
    if (meshRef.current) {
      // Clouds drift faster than surface — gives a sense of weather.
      meshRef.current.rotation.y = state.clock.elapsedTime * rotationSpeed * 4.5;
    }
    if (material.uniforms.uTime) material.uniforms.uTime.value = state.clock.elapsedTime;
  });

  return (
    <mesh
      ref={(m) => {
        meshRef.current = m;
      }}
      scale={1.025}
    >
      <sphereGeometry args={[radius, 36, 24]} />
      <primitive object={material} attach="material" />
    </mesh>
  );
}

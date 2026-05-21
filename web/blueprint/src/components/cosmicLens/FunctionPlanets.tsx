import { Html } from "@react-three/drei";
import { useFrame } from "@react-three/fiber";
import { useMemo, useRef } from "react";
import * as THREE from "three";
import type { FunctionMeta } from "./lib/types";
import { colorForFunction } from "./lib/colors";
import { usePersonaHues, type HueMap } from "./usePersonaHues";
import { AtmosphereRim } from "./AtmosphereRim";
import { AnamorphicFlare } from "./AnamorphicFlare";
import { PlanetSurface, PlanetClouds } from "./PlanetSurface";
import { useLiveMemory, type FunctionMemorySummary } from "../../lib/useLiveMemory";
import {
  LessonSatellites,
  DreamPulse,
  WorkingMemoryParticles,
} from "./DreamPassViz";

interface FunctionPlanetsProps {
  functions: FunctionMeta[];
  /** workflow_id-prefix → function key counts (for sizing planets by load). */
  loadByFunction?: Map<string, number>;
  onFunctionClick?: (key: string, label: string) => void;
}

const ORBIT_RADIUS = 14;
const PLANET_RADIUS = 0.7;

/** Backend functions endpoint uses `name`. Some surfaces use `key`. */
function fnKey(fn: FunctionMeta): string {
  return fn.name ?? fn.key ?? "";
}

/** Resolve a planet hue from the persona-colors palette when available,
 *  falling back to the existing function-family color so personas without
 *  a registered display_color (or an empty palette / failed fetch) keep
 *  the prior visual identity. The senior persona for the function is the
 *  root of `personaHierarchy` returned by `/api/functions`. */
function planetColor(fn: FunctionMeta, hues: HueMap): string {
  const role = fn.personaHierarchy?.role;
  if (role && hues[role]) return hues[role];
  return colorForFunction(fnKey(fn));
}

/** A single planet with slow rotation + atmosphere rim. Split out from
 *  FunctionPlanets so each planet can hold its own rotation ref without
 *  triggering parent re-renders. The rotation rate is seeded from the
 *  function key so planets don't all spin in sync, and the seed lives in
 *  useMemo so it's stable across renders. */
function Planet({
  fnK,
  color,
  load,
  idle,
  onClick,
  memory,
}: {
  fnK: string;
  color: string;
  load: number;
  idle: boolean;
  onClick: () => void;
  memory?: FunctionMemorySummary;
}) {
  const planetScale = idle ? 0.7 : 1.0;
  const haloOpacity = idle ? 0.04 : 0.08 + Math.min(0.25, load / 50);
  const lessonCount = memory?.lessons ?? 0;
  const dreaming = !!memory?.dreaming;

  // Per-planet seed for the surface shader (continent layout) and rotation
  // rate. Hashing the function key gives stable distinct planets across
  // refreshes — Tech always looks like Tech, Finance like Finance.
  const { surfaceSpeed, seedNum } = useMemo(() => {
    let h = 0;
    for (let i = 0; i < fnK.length; i++) h = (h * 31 + fnK.charCodeAt(i)) | 0;
    const seed = (h >>> 0) / 0xffffffff;
    return {
      // Slow surface rotation so you can SEE land masses move past — this
      // is the signature 'living planet' cue. Range 0.04 .. 0.12 rad/s.
      surfaceSpeed: 0.04 + seed * 0.08,
      seedNum: h >>> 0,
    };
  }, [fnK]);

  return (
    <>
      {/* Real planet body — procedural surface shader produces continents,
          oceans, day/night terminator, and a faint city-glow on the
          night side. Replaces the previous flat-shaded glowing sphere
          (which read as 'gas blob' rather than 'real planet'). */}
      <group
        scale={planetScale}
        onClick={(e) => {
          e.stopPropagation();
          onClick();
        }}
        onPointerOver={(e) => {
          e.stopPropagation();
          document.body.style.cursor = "pointer";
        }}
        onPointerOut={() => {
          document.body.style.cursor = "default";
        }}
      >
        <PlanetSurface
          radius={PLANET_RADIUS}
          color={color}
          seed={seedNum}
          rotationSpeed={surfaceSpeed}
        />
        {/* Cloud layer — thin transparent shell rotating slightly faster
            than the planet body so weather drifts across the surface. */}
        <PlanetClouds radius={PLANET_RADIUS} seed={seedNum} />
      </group>
      {/* Atmosphere rim — fresnel halo that reads as "this planet has
          atmosphere when seen from space". Slightly stronger on busy
          planets so they pop visually as the place where work happens. */}
      <group scale={planetScale}>
        <AtmosphereRim
          radius={PLANET_RADIUS}
          color={color}
          scale={1.10}
          power={2.6}
          intensity={idle ? 0.6 : 1.1 + Math.min(0.6, load / 80)}
        />
      </group>
      {/* Soft inner halo (kept from the previous design) — fills the gap
          between the planet body and the atmosphere rim with a touch of
          colour. */}
      <mesh scale={planetScale}>
        <sphereGeometry args={[PLANET_RADIUS * 1.5, 16, 16]} />
        <meshBasicMaterial color={color} transparent opacity={haloOpacity} />
      </mesh>
      {/* Anamorphic lens flare — ONLY on active planets, intensity capped
          so the cinematic mood doesn't tip into Bay-style overload. The
          horizontal streak is the cinematic 'lens artifact' you see on
          bright spacecraft / planets in J.J. Abrams Star Trek and Mass
          Effect. Skipped entirely on idle so the dim planets stay calm. */}
      {!idle && (
        <AnamorphicFlare
          color={color}
          intensity={Math.min(0.55, 0.18 + load / 80)}
          size={3.4 + Math.min(1.6, load / 30)}
        />
      )}
      {/* Dream-pass viz — orbits a small ring of lesson satellites
          around the planet (one dot per distilled lesson, capped),
          pulses a halo while a dream pass is in flight, and streams
          working-memory particles inward during the pass. Renders
          nothing when there's no memory data. */}
      <LessonSatellites count={lessonCount} color={color} radius={PLANET_RADIUS} />
      <DreamPulse active={dreaming} color={color} radius={PLANET_RADIUS} />
      <WorkingMemoryParticles
        active={dreaming}
        count={memory?.working ?? 0}
        color={color}
        radius={PLANET_RADIUS}
      />
    </>
  );
}

/**
 * One sphere per function, positioned in even orbital slots around the hub.
 * Each planet rotates slowly on its own axis at a per-key speed/phase, with
 * an additive fresnel atmosphere rim that lights up at the limb. Each
 * planet ALSO wobbles in a small circular orbit around its base position
 * — gives the system a 'drifting' feel without changing the API-known
 * positions used for rocket aim and moon resolution.
 */
export function FunctionPlanets({ functions, loadByFunction, onFunctionClick }: FunctionPlanetsProps) {
  const visible = functions.filter((f) => fnKey(f));
  // v1.2 Spec §9 polish (e): tint each planet with its senior persona's hue
  // (Finance blue, HR rose, Procurement gold, Tech teal, Creative violet,
  // Legal emerald, CEO warm gold) so the constellation matches the
  // DecisionTicker / drawer chip palette. Hook returns an empty map until
  // the palette fetch resolves, in which case planetColor falls back to
  // the existing function-family hue — no flash on first paint.
  const personaHues = usePersonaHues();
  // Dream-pass live overlay: lessons/working memory per function + a
  // per-function `dreaming` flag set while a pass is in flight. Polls
  // /api/memory/per-persona every 5s and subscribes to
  // /api/blueprint/stream for dream.pass.* events.
  const { byFunction: memoryByFunction } = useLiveMemory();
  if (!visible.length) return null;

  return (
    <group>
      {visible.map((fn, i) => {
        const k = fnKey(fn);
        const angle = (i * 2 * Math.PI) / visible.length;
        const x = Math.cos(angle) * ORBIT_RADIUS;
        const z = Math.sin(angle) * ORBIT_RADIUS;
        const color = planetColor(fn, personaHues);
        const load = loadByFunction?.get(k) ?? 0;
        const idle = load === 0;
        const planetScale = idle ? 0.7 : 1.0;
        const labelText = (fn.display ?? fn.label ?? k).toUpperCase();
        return (
          <OrbitingPlanetGroup key={k} basePos={[x, 1.5, z]} fnK={k}>
            <Planet
              fnK={k}
              color={color}
              load={load}
              idle={idle}
              onClick={() => onFunctionClick?.(k, fn.display ?? fn.label ?? k)}
              memory={memoryByFunction.get(k)}
            />
            {/* Orbital guide ring — subtle hint of where moons orbit */}
            <mesh rotation={[Math.PI / 2, 0, 0]}>
              <ringGeometry args={[1.55, 1.65, 64]} />
              <meshBasicMaterial
                color={color}
                transparent
                opacity={idle ? 0.04 : 0.12}
                side={2}
              />
            </mesh>
            {/* Function name label */}
            <Html
              position={[0, PLANET_RADIUS * planetScale + 0.6, 0]}
              center
              style={{
                pointerEvents: "none",
                color: color,
                fontSize: 9,
                fontFamily: "ui-sans-serif, system-ui",
                fontWeight: 700,
                letterSpacing: 1.2,
                textShadow: "0 0 6px rgba(0,0,0,0.9)",
                whiteSpace: "nowrap",
                opacity: idle ? 0.45 : 0.9,
              }}
            >
              {labelText}
              {load > 0 && (
                <span style={{ color: "#94a3b8", fontWeight: 400, marginLeft: 6 }}>
                  · {load}
                </span>
              )}
              {idle && (
                <span
                  style={{
                    color: "#475569",
                    fontWeight: 400,
                    marginLeft: 6,
                    fontStyle: "italic",
                  }}
                >
                  · idle
                </span>
              )}
              {/* Dream-pass overlay — lesson count + dreaming pill so the
                  loop is visible on the constellation without opening a
                  drawer. */}
              {(() => {
                const mem = memoryByFunction.get(k);
                if (!mem) return null;
                return (
                  <>
                    {mem.lessons > 0 && (
                      <span
                        data-testid={`fn-${k}-lessons`}
                        style={{
                          color: color,
                          fontWeight: 600,
                          marginLeft: 8,
                          opacity: 0.85,
                          fontSize: 8,
                        }}
                      >
                        · {mem.lessons}✦
                      </span>
                    )}
                    {mem.dreaming && (
                      <span
                        data-testid={`fn-${k}-dreaming`}
                        style={{
                          color: "#fde68a",
                          fontWeight: 700,
                          marginLeft: 8,
                          fontSize: 8,
                          letterSpacing: 1.5,
                          textShadow: `0 0 6px ${color}`,
                        }}
                      >
                        · DREAMING
                      </span>
                    )}
                  </>
                );
              })()}
            </Html>
          </OrbitingPlanetGroup>
        );
      })}
    </group>
  );
}

/** Wraps a planet group with a tiny orbital wobble around its base
 *  position. Each planet drifts in a small circle (~0.4 unit radius,
 *  ~30s period at the slowest) at a per-key speed and phase, so the
 *  planet ring looks like it's slowly orbiting / drifting rather than
 *  frozen.
 *
 *  IMPORTANT: this only affects the VISUAL position. planetBasePosition
 *  still returns the fixed slot, so rocket aim and moon resolution
 *  continue to work without per-frame recomputation. The wobble radius
 *  is small enough that arriving rockets visually park 'close enough'
 *  to the planet.
 */
function OrbitingPlanetGroup({
  basePos,
  fnK,
  children,
}: {
  basePos: [number, number, number];
  fnK: string;
  children: React.ReactNode;
}) {
  const groupRef = useRef<THREE.Group>(null);
  const { speed, phase, ampX, ampZ } = useMemo(() => {
    let h = 0;
    for (let i = 0; i < fnK.length; i++) h = (h * 31 + fnK.charCodeAt(i)) | 0;
    const seed = (h >>> 0) / 0xffffffff;
    return {
      // ~25-50s per orbital period — slow enough to feel like 'drifting',
      // fast enough that the demo viewer notices motion within 30s.
      speed: 0.13 + seed * 0.12,
      phase: seed * Math.PI * 2,
      ampX: 0.32 + (seed * 0.18),
      ampZ: 0.32 + ((1 - seed) * 0.18),
    };
  }, [fnK]);

  useFrame((state) => {
    if (!groupRef.current) return;
    const t = state.clock.elapsedTime * speed + phase;
    groupRef.current.position.x = basePos[0] + Math.cos(t) * ampX;
    groupRef.current.position.y = basePos[1] + Math.sin(t * 0.7) * 0.12;
    groupRef.current.position.z = basePos[2] + Math.sin(t) * ampZ;
  });

  return <group ref={groupRef} position={basePos}>{children}</group>;
}

/** Resolve a function planet's world position. Used by moons + rockets. */
export function planetPosition(
  fn: string | undefined,
  functions: FunctionMeta[],
  /** Pass world-time so moons see the same precession.
   *  (No precession is applied any more — see planetBasePosition.) */
  _time: number,
): [number, number, number] {
  return planetBasePosition(fn, functions);
}

/** Time-independent base position of a planet (no precession). Used by
 *  camera focus so the target doesn't depend on a hard-to-sync wall clock. */
export function planetBasePosition(
  fn: string | undefined,
  functions: FunctionMeta[],
): [number, number, number] {
  if (!functions.length || !fn) return [0, 1.5, 0];
  const visible = functions.filter((f) => fnKey(f));
  const idx = visible.findIndex((f) => fnKey(f) === fn);
  if (idx < 0) return [0, 1.5, 0];
  const baseAngle = (idx * 2 * Math.PI) / visible.length;
  return [Math.cos(baseAngle) * ORBIT_RADIUS, 1.5, Math.sin(baseAngle) * ORBIT_RADIUS];
}

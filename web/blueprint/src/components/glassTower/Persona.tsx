/**
 * Persona — small abstract avatar at a desk.
 *
 * State-driven posture:
 *   - idle: dim, static
 *   - working: warm glow, gentle bob
 *   - thinking (transient flash): pulsing gold, thought-bubble overhead
 *   - decided (transient flash): green/red flash
 */
import { Text } from "@react-three/drei";
import { useFrame } from "@react-three/fiber";
import { useRef } from "react";
import * as THREE from "three";

import type { FlashSet, PersonaRow } from "../../lib/useLiveOrg";

interface Props {
  role: string;
  position: [number, number, number];
  state: PersonaRow["state"];
  flashesRef: React.MutableRefObject<FlashSet>;
  tint: string;
  showLabel?: boolean;
}

export function Persona({ role, position, state, flashesRef, tint, showLabel = false }: Props) {
  const headRef = useRef<THREE.Mesh>(null);
  const bodyRef = useRef<THREE.Mesh>(null);
  const haloRef = useRef<THREE.Mesh>(null);
  const bubbleRef = useRef<THREE.Mesh>(null);
  const timeRef = useRef<number>(Math.random() * 1000);

  useFrame((_, dt) => {
    timeRef.current += dt;
    const t = timeRef.current;

    const flash = flashesRef.current.personaFlash.get(role);
    const now = performance.now();
    let activity = state === "working" ? 0.7 : state === "recently_decided" ? 0.45 : 0.18;
    let flashColor: THREE.ColorRepresentation = tint;
    let bubbleScale = 0;

    if (flash && flash.until > now) {
      switch (flash.kind) {
        case "thinking":
          activity = 0.85 + 0.15 * Math.sin(t * 6);
          flashColor = "#ffd76a";
          bubbleScale = 0.13 + 0.04 * Math.sin(t * 6);
          break;
        case "verdict_approve":
          activity = 1.0;
          flashColor = "#5fd49d";
          bubbleScale = 0.15;
          break;
        case "verdict_reject":
          activity = 1.0;
          flashColor = "#e87a5d";
          bubbleScale = 0.15;
          break;
        case "decided":
          activity = 0.9;
          flashColor = tint;
          bubbleScale = 0.12;
          break;
      }
    } else if (flash) {
      flashesRef.current.personaFlash.delete(role);
    }

    // Body bob
    if (bodyRef.current) {
      bodyRef.current.position.y = position[1] + 0.16 + 0.012 * Math.sin(t * 1.4);
    }
    if (headRef.current) {
      headRef.current.position.y = position[1] + 0.32 + 0.012 * Math.sin(t * 1.4);
      const m = headRef.current.material as THREE.MeshStandardMaterial;
      m.emissiveIntensity += (activity - m.emissiveIntensity) * 0.18;
      const c = new THREE.Color(flashColor);
      m.emissive.lerp(c, 0.18);
    }
    if (haloRef.current) {
      const m = haloRef.current.material as THREE.MeshBasicMaterial;
      m.opacity = activity * 0.7;
      const c = new THREE.Color(flashColor);
      m.color.lerp(c, 0.18);
    }
    if (bubbleRef.current) {
      bubbleRef.current.scale.setScalar(bubbleScale);
      const m = bubbleRef.current.material as THREE.MeshBasicMaterial;
      m.opacity = bubbleScale > 0 ? 0.85 : 0;
    }
  });

  return (
    <group position={[position[0], 0, position[2]]}>
      {/* Desk surface — small dark slab. */}
      <mesh position={[0, position[1] + 0.02, 0]}>
        <boxGeometry args={[0.32, 0.04, 0.32]} />
        <meshStandardMaterial color="#16181c" metalness={0.6} roughness={0.4} />
      </mesh>

      {/* Body — capsule. */}
      <mesh ref={bodyRef} position={[0, position[1] + 0.18, 0]}>
        <capsuleGeometry args={[0.075, 0.14, 4, 8]} />
        <meshStandardMaterial color="#23272f" emissive={tint} emissiveIntensity={0.3} />
      </mesh>

      {/* Head — small sphere with strong emissive that drives the avatar's perceived state. */}
      <mesh ref={headRef} position={[0, position[1] + 0.36, 0]}>
        <sphereGeometry args={[0.075, 16, 16]} />
        <meshStandardMaterial color="#33373f" emissive={tint} emissiveIntensity={0.7} toneMapped={false} />
      </mesh>

      {/* Halo — radial glow around the head, opacity = activity. */}
      <mesh ref={haloRef} position={[0, position[1] + 0.36, 0]}>
        <ringGeometry args={[0.085, 0.20, 24]} />
        <meshBasicMaterial color={tint} transparent opacity={0.5} side={THREE.DoubleSide} toneMapped={false} />
      </mesh>

      {/* Thought bubble overhead — pulses on thinking flash. */}
      <mesh ref={bubbleRef} position={[0, position[1] + 0.56, 0]} scale={0}>
        <sphereGeometry args={[1, 12, 12]} />
        <meshBasicMaterial color="#ffd76a" transparent opacity={0} toneMapped={false} />
      </mesh>

      {showLabel && (
        <Text
          position={[0, position[1] + 0.62, 0]}
          fontSize={0.07}
          color="#cfd2d6"
          anchorX="center"
          anchorY="middle"
        >
          {role}
        </Text>
      )}
    </group>
  );
}

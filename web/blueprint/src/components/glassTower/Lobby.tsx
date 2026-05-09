/**
 * Lobby — wider base of the glass tower.
 *
 * Holds the count of in-flight workflows on a glowing pillar; the
 * decision pool is rendered separately by DecisionPool.
 */
import { Text } from "@react-three/drei";
import * as THREE from "three";

import type { RecentDecision } from "../../lib/useLiveOrg";

const LOBBY_WIDTH = 7.2;
const LOBBY_HEIGHT = 0.9;
const LOBBY_DEPTH = 4.0;

interface Props {
  y: number;
  inFlightCount: number;
  recentDecisions: RecentDecision[];
}

export function Lobby({ y, inFlightCount, recentDecisions }: Props) {
  return (
    <group position={[0, y, 0]}>
      {/* Wide base slab. */}
      <mesh>
        <boxGeometry args={[LOBBY_WIDTH, LOBBY_HEIGHT, LOBBY_DEPTH]} />
        <meshStandardMaterial
          color="#0c0e14"
          emissive="#1a1d28"
          emissiveIntensity={0.45}
          transparent
          opacity={0.92}
          metalness={0.4}
          roughness={0.5}
        />
      </mesh>

      {/* Base halo ring — thin glowing band around the lobby's perimeter
          at floor level. Brightens with overall org activity (in-flight
          count). Visual anchor + sense of grounding. */}
      <mesh rotation={[-Math.PI / 2, 0, 0]} position={[0, -LOBBY_HEIGHT / 2 + 0.005, 0]}>
        <ringGeometry args={[3.8, 4.2, 64]} />
        <meshBasicMaterial
          color={inFlightCount > 50 ? "#5fd49d" : "#06b6d4"}
          transparent
          opacity={Math.min(0.8, 0.25 + inFlightCount * 0.005)}
          toneMapped={false}
          side={2 as unknown as THREE.Side}
        />
      </mesh>

      {/* Lobby front-edge glow strip — the "ticker" base. */}
      <mesh position={[0, -LOBBY_HEIGHT * 0.45, LOBBY_DEPTH / 2 + 0.01]}>
        <planeGeometry args={[LOBBY_WIDTH * 0.96, 0.06]} />
        <meshBasicMaterial color="#5fd49d" transparent opacity={0.55} toneMapped={false} />
      </mesh>

      {/* In-flight pillar — left side of the lobby. */}
      <mesh position={[-LOBBY_WIDTH / 2 + 0.7, LOBBY_HEIGHT / 2 + 0.4, LOBBY_DEPTH / 2 - 0.4]}>
        <cylinderGeometry args={[0.15, 0.15, 0.8, 16]} />
        <meshStandardMaterial color="#1a1d28" emissive="#7faed4" emissiveIntensity={0.85} toneMapped={false} />
      </mesh>
      <Text
        position={[-LOBBY_WIDTH / 2 + 0.7, LOBBY_HEIGHT / 2 + 0.95, LOBBY_DEPTH / 2 - 0.4]}
        fontSize={0.16}
        color="#7faed4"
        anchorX="center"
        anchorY="middle"
        outlineWidth={0.005}
        outlineColor="#000"
      >
        {inFlightCount}
      </Text>
      <Text
        position={[-LOBBY_WIDTH / 2 + 0.7, LOBBY_HEIGHT / 2 - 0.1, LOBBY_DEPTH / 2 - 0.4]}
        fontSize={0.05}
        color="#9aa0a6"
        anchorX="center"
        anchorY="middle"
      >
        IN FLIGHT
      </Text>

      {/* Decisions pillar — right side. Count = recent decisions in last 60s. */}
      <mesh position={[LOBBY_WIDTH / 2 - 0.7, LOBBY_HEIGHT / 2 + 0.4, LOBBY_DEPTH / 2 - 0.4]}>
        <cylinderGeometry args={[0.15, 0.15, 0.8, 16]} />
        <meshStandardMaterial color="#1a1d28" emissive="#a78bfa" emissiveIntensity={0.85} toneMapped={false} />
      </mesh>
      <Text
        position={[LOBBY_WIDTH / 2 - 0.7, LOBBY_HEIGHT / 2 + 0.95, LOBBY_DEPTH / 2 - 0.4]}
        fontSize={0.16}
        color="#a78bfa"
        anchorX="center"
        anchorY="middle"
        outlineWidth={0.005}
        outlineColor="#000"
      >
        {recentDecisions.length}
      </Text>
      <Text
        position={[LOBBY_WIDTH / 2 - 0.7, LOBBY_HEIGHT / 2 - 0.1, LOBBY_DEPTH / 2 - 0.4]}
        fontSize={0.05}
        color="#9aa0a6"
        anchorX="center"
        anchorY="middle"
      >
        DECIDED · 60s
      </Text>

      {/* Center label — the org name / "lobby" caption. */}
      <Text
        position={[0, LOBBY_HEIGHT / 2 + 0.15, LOBBY_DEPTH / 2 + 0.02]}
        fontSize={0.13}
        color="#f5f5f7"
        anchorX="center"
        anchorY="middle"
        outlineWidth={0.005}
        outlineColor="#000"
      >
        ZAVA · the agentic org
      </Text>
    </group>
  );
}

import { useRef } from "react";
import * as THREE from "three";
import { useFrame } from "@react-three/fiber";
import type { CityMeta, FunctionMeta, WorkflowMoonData } from "./lib/types";
import type { RocketRegistry } from "./lib/registries";
import { cityPosition } from "./Cities";

interface DirectionalBeamsProps {
  rocketRegistry: RocketRegistry;
  cities: CityMeta[];
  visible: boolean;
}

const MAX_BEAMS = 60;
const BEAM_RADIUS = 0.06;
const BEAM_HEIGHT = 0.55; // distance between hovering rocket and city surface

const matrix = new THREE.Matrix4();
const position = new THREE.Vector3();
const scale = new THREE.Vector3();
const quaternion = new THREE.Quaternion();
const tmpColor = new THREE.Color();

/**
 * Directional beams between parked rockets and their docked cities.
 *
 * Encodes data flow direction:
 *   - read  → beam goes UP from city to rocket (cyan, particles drift up)
 *   - write → beam goes DOWN from rocket to city (warm orange, particles drift down)
 *
 * Visible only in Entities mode.
 *
 * Implementation: InstancedMesh of cylinders. For each parked rocket
 * with is_read or is_write flag, render a cylinder between city and
 * the hovering rocket position. Colored by direction.
 */
export function DirectionalBeams({ rocketRegistry, cities, visible }: DirectionalBeamsProps) {
  const meshRef = useRef<THREE.InstancedMesh>(null);

  // Pre-compute city positions
  const cityPos = (cityId: string): [number, number, number] => {
    return cityPosition(cityId);
  };

  useFrame((state) => {
    if (!meshRef.current) return;
    const mesh = meshRef.current;
    if (!visible) {
      // Hide all instances
      for (let i = 0; i < MAX_BEAMS; i++) {
        position.set(0, -100, 0);
        scale.set(1, 0.001, 1);
        matrix.compose(position, quaternion, scale);
        mesh.setMatrixAt(i, matrix);
      }
      mesh.instanceMatrix.needsUpdate = true;
      mesh.count = 0;
      return;
    }

    let i = 0;
    const t = state.clock.getElapsedTime();
    rocketRegistry.values().forEach((r) => {
      if (i >= MAX_BEAMS) return;
      if (r.phase !== "parked") return;
      if (!r.is_read && !r.is_write) return;
      const cp = cityPos(r.city_id);
      const cityX = cp[0];
      const cityZ = cp[2];
      const cityY = cp[1];
      const rocketY = cityY + BEAM_HEIGHT + Math.sin(t * 3 + r.dispatched_at * 0.001) * 0.05;

      // Beam center between city and rocket
      const beamCenterY = (cityY + rocketY) / 2;
      const beamHeight = rocketY - cityY;

      position.set(cityX, beamCenterY, cityZ);
      scale.set(1, beamHeight / 1.0, 1); // cylinder default height = 1
      matrix.compose(position, quaternion, scale);
      mesh.setMatrixAt(i, matrix);

      // Color by direction
      if (r.is_write) {
        tmpColor.set("#fb923c"); // warm — write
      } else {
        tmpColor.set("#67e8f9"); // cool — read
      }
      mesh.setColorAt(i, tmpColor);
      i++;
    });
    // Park unused
    for (let j = i; j < MAX_BEAMS; j++) {
      position.set(0, -100, 0);
      scale.set(1, 0.001, 1);
      matrix.compose(position, quaternion, scale);
      mesh.setMatrixAt(j, matrix);
    }
    mesh.instanceMatrix.needsUpdate = true;
    if (mesh.instanceColor) mesh.instanceColor.needsUpdate = true;
    mesh.count = MAX_BEAMS;
  });

  return (
    <instancedMesh ref={meshRef} args={[undefined, undefined, MAX_BEAMS]}>
      <cylinderGeometry args={[BEAM_RADIUS, BEAM_RADIUS, 1, 8, 1, true]} />
      <meshBasicMaterial vertexColors transparent opacity={0.55} />
    </instancedMesh>
  );
}

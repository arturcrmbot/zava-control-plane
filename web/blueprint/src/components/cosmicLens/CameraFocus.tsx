import { useEffect, useRef } from "react";
import * as THREE from "three";
import { useFrame, useThree } from "@react-three/fiber";

export interface FocusTarget {
  target: [number, number, number];
  /** Distance from target the camera should sit at when focused. */
  distance: number;
}

interface CameraFocusProps {
  focus: FocusTarget | null;
  /** Default overview camera position to return to when focus clears. */
  overviewPosition: [number, number, number];
  overviewTarget: [number, number, number];
  /** Tied to OrbitControls so we can mutate target + force update each frame. */
  controlsRef: React.MutableRefObject<{ target: THREE.Vector3; update: () => void } | null>;
}

const SLERP = 0.08; // 8% toward target per frame ≈ snappy but smooth at 60fps
const tmpTargetVec = new THREE.Vector3();
const tmpCamPos = new THREE.Vector3();
const dirVec = new THREE.Vector3();

/**
 * Camera focus animator. When `focus` is non-null, smoothly lerps the
 * OrbitControls target to focus.target and the camera position to a point
 * `focus.distance` away from the target along the current view direction.
 *
 * When focus clears, lerps back to the overview position/target so we
 * return to the wide cosmic view.
 *
 * Lives inside <Canvas> so useFrame + useThree work.
 */
export function CameraFocus({
  focus,
  overviewPosition,
  overviewTarget,
  controlsRef,
}: CameraFocusProps) {
  const { camera } = useThree();
  // Snapshot the current focus so the lerp reads the same value across frames
  // without forcing a re-render storm.
  const focusRef = useRef<FocusTarget | null>(focus);
  useEffect(() => {
    focusRef.current = focus;
  }, [focus]);

  useFrame(() => {
    const target = focusRef.current
      ? new THREE.Vector3(...focusRef.current.target)
      : new THREE.Vector3(...overviewTarget);

    // Determine where the camera SHOULD be: a fixed distance from the target
    // along the current camera→target ray. Preserves user-rotated angle.
    const ctrls = controlsRef.current;
    const currentTarget = ctrls?.target ?? new THREE.Vector3(...overviewTarget);
    dirVec.copy(camera.position).sub(currentTarget).normalize();
    if (dirVec.lengthSq() < 0.001) dirVec.set(0, 0.5, 1).normalize();

    const desiredDistance = focusRef.current
      ? focusRef.current.distance
      : new THREE.Vector3(...overviewPosition).distanceTo(new THREE.Vector3(...overviewTarget));

    tmpCamPos.copy(target).add(dirVec.multiplyScalar(desiredDistance));

    // Lerp camera + target
    camera.position.lerp(tmpCamPos, SLERP);
    if (ctrls) {
      tmpTargetVec.copy(target);
      ctrls.target.lerp(tmpTargetVec, SLERP);
      ctrls.update();
    }
  });

  return null;
}

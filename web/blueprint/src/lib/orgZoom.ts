/**
 * The Org Building zoom-state machine (IP2, TASK-007).
 *
 * Four zoom levels:
 *   0 — org view (the whole campus). Stub in chunk 1; falls back to org-level.
 *   1 — wing view (a function's wing). Stub.
 *   2 — department view. Stub.
 *   3 — building view (the 10-floor skyscraper). The only level fully
 *       implemented in chunk 1.
 *
 * Chunks 2-4 of the Org Building rollout will fill in the lower-zoom
 * camera framings + transitions; for now ``zoomTo`` clamps to level 3
 * because that's the only level with art behind it.
 */
import { useCallback, useState } from "react";

export type ZoomLevel = 0 | 1 | 2 | 3;
export type ZoomKind = "org" | "wing" | "department" | "workflow";

export interface ZoomTarget {
  kind: ZoomKind;
  /** Function name, department slug, or workflow id depending on `kind`. */
  id?: string;
}

export interface CameraFraming {
  position: [number, number, number];
  lookAt: [number, number, number];
  fov: number;
}

/**
 * Default framings per zoom level. Only LEVEL_FRAMINGS[3] is shipped art
 * in this chunk — the others are sensible placeholders that all reduce
 * to the same org-level framing so a stray ``zoomTo({kind:'wing'})``
 * doesn't strand the camera.
 */
export const LEVEL_FRAMINGS: Record<ZoomLevel, CameraFraming> = {
  0: { position: [0, 8, 26], lookAt: [0, 4, 0], fov: 45 },
  1: { position: [0, 8, 26], lookAt: [0, 4, 0], fov: 45 },
  2: { position: [0, 8, 26], lookAt: [0, 4, 0], fov: 45 },
  3: { position: [0, 8, 26], lookAt: [0, 4, 0], fov: 45 },
};

export interface OrgZoomState {
  level: ZoomLevel;
  target: ZoomTarget;
  framing: CameraFraming;
  zoomTo: (target: ZoomTarget) => void;
  zoomOut: () => void;
  zoomIn: () => void;
}

function levelForKind(kind: ZoomKind): ZoomLevel {
  switch (kind) {
    case "org":
      return 0;
    case "wing":
      return 1;
    case "department":
      return 2;
    case "workflow":
      return 3;
  }
}

export function useOrgZoom(): OrgZoomState {
  // Chunk 1 ships zoom-3 only; the spec wants ESC at zoom-3 to be a
  // no-op when the cosmic lens is off. The page-level handler enforces
  // that — the hook itself just decrements the level, clamping at 3.
  const [level, setLevel] = useState<ZoomLevel>(3);
  const [target, setTarget] = useState<ZoomTarget>({ kind: "workflow" });

  const zoomTo = useCallback((next: ZoomTarget) => {
    setTarget(next);
    setLevel(levelForKind(next.kind));
  }, []);

  const zoomOut = useCallback(() => {
    setLevel((cur) => {
      // Clamp at 3 in chunk 1: lower zoom levels have no scene yet, so
      // bouncing the camera there would just leave a blank screen.
      if (cur >= 3) return 3;
      return (cur + 1) as ZoomLevel;
    });
  }, []);

  const zoomIn = useCallback(() => {
    setLevel((cur) => (cur <= 0 ? 0 : ((cur - 1) as ZoomLevel)));
  }, []);

  return {
    level,
    target,
    framing: LEVEL_FRAMINGS[level],
    zoomTo,
    zoomOut,
    zoomIn,
  };
}

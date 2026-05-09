/**
 * The Org Building zoom-state machine.
 *
 * Adopts the spec's level numbering (`PAT-002`):
 *
 *   3 — org view (default; whole 10-floor building, slow auto-orbit)
 *   2 — wing view (a related-function group of 1-3 floors)
 *   1 — department view (one function floor; interior cutaway)
 *   0 — workflow view (one workflow's lifecycle)
 *
 * `zoomOut` increases level (camera pulls back), clamped at 3.
 * `zoomIn`  decreases level (camera dives further in), clamped at 0.
 *
 * Wing framing is computed from the spec floor layout — `floorY()` from
 * `floorLayout.ts` gives Y for each floor; the camera is parked off-axis
 * to that wing's centroid Y at a fixed standoff so the framing is
 * deterministic.
 *
 * Programmatic zoom: a `org-building:zoom-to` window CustomEvent
 * triggers `zoomTo()` from anywhere in the app (EventFeed deep-links,
 * tests, etc.). Detail shape: `{kind, id?}` — same as `ZoomTarget`.
 */
import { useCallback, useEffect, useState } from "react";
import { floorY } from "./floorLayout";
import { WINGS } from "./orgWings";
import type { WingKey } from "./orgWings";

export type ZoomLevel = 0 | 1 | 2 | 3;
export type ZoomKind = "org" | "wing" | "department" | "workflow";

export interface ZoomTarget {
  kind: ZoomKind;
  id?: string;
}

export interface CameraFraming {
  position: [number, number, number];
  lookAt: [number, number, number];
  fov: number;
}

export const ORG_FRAMING: CameraFraming = {
  position: [0, 8, 26],
  lookAt: [0, 5, 0],
  fov: 45,
};

export function wingFraming(wing: string): CameraFraming {
  const floors = (WINGS as Record<string, string[]>)[wing] ?? [];
  if (floors.length === 0) return ORG_FRAMING;
  const ys: number[] = [];
  for (const fn of floors) {
    const y = floorY(fn);
    if (y != null) ys.push(y);
  }
  if (ys.length === 0) return ORG_FRAMING;
  const meanY = ys.reduce((a, b) => a + b, 0) / ys.length;
  return {
    position: [4, meanY + 1.6, 14],
    lookAt: [0, meanY, 0],
    fov: 38,
  };
}

export const DEPARTMENT_FRAMING: CameraFraming = {
  position: [0, 6, 8],
  lookAt: [0, 5, 0],
  fov: 32,
};

export const WORKFLOW_FRAMING: CameraFraming = {
  position: [0, 5, 5],
  lookAt: [0, 5, 0],
  fov: 28,
};

export interface OrgZoomState {
  level: ZoomLevel;
  target: ZoomTarget;
  framing: CameraFraming;
  zoomTo: (target: ZoomTarget) => void;
  zoomOut: () => void;
  zoomIn: () => void;
}

export function levelForKind(kind: ZoomKind): ZoomLevel {
  switch (kind) {
    case "org":
      return 3;
    case "wing":
      return 2;
    case "department":
      return 1;
    case "workflow":
      return 0;
  }
}

export function framingFor(target: ZoomTarget): CameraFraming {
  switch (target.kind) {
    case "org":
      return ORG_FRAMING;
    case "wing":
      return wingFraming(target.id ?? "");
    case "department":
      return DEPARTMENT_FRAMING;
    case "workflow":
      return WORKFLOW_FRAMING;
  }
}

function floorToWingKey(fn: string): WingKey | null {
  for (const [wing, floors] of Object.entries(WINGS) as [WingKey, string[]][]) {
    if (floors.includes(fn)) return wing;
  }
  return null;
}

export function useOrgZoom(): OrgZoomState {
  const [target, setTarget] = useState<ZoomTarget>({ kind: "org" });

  const zoomTo = useCallback((next: ZoomTarget) => {
    setTarget(next);
  }, []);

  const zoomOut = useCallback(() => {
    setTarget((cur) => {
      switch (cur.kind) {
        case "workflow":
          return { kind: "org" };
        case "department": {
          const wing = cur.id ? floorToWingKey(cur.id) : null;
          return wing ? { kind: "wing", id: wing } : { kind: "org" };
        }
        case "wing":
          return { kind: "org" };
        case "org":
          return cur;
      }
    });
  }, []);

  const zoomIn = useCallback(() => {
    // Drilling without a chosen child is ambiguous; click-to-drill from
    // the scene supplies a concrete next target.
    setTarget((cur) => cur);
  }, []);

  useEffect(() => {
    function handler(e: Event) {
      const detail = (e as CustomEvent<ZoomTarget>).detail;
      if (!detail || !detail.kind) return;
      setTarget(detail);
    }
    window.addEventListener("org-building:zoom-to", handler as EventListener);
    return () =>
      window.removeEventListener(
        "org-building:zoom-to",
        handler as EventListener,
      );
  }, []);

  const level = levelForKind(target.kind);
  return {
    level,
    target,
    framing: framingFor(target),
    zoomTo,
    zoomOut,
    zoomIn,
  };
}

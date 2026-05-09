/**
 * The Org Building (IP4, TASK-026) — layer-toggle state.
 *
 * Persisted to localStorage under "org-building.layers". Defaults to
 * everything ON. Used by both the bottom-strip toggle UI and the
 * AnimationLayer to gate which kinds of overlays render.
 */
import { useCallback, useEffect, useState } from "react";

export interface LayerFlags {
  activityHeat: boolean;
  entityFlows: boolean;
  decisionSparks: boolean;
  ambientFlashes: boolean;
  cadencePulses: boolean;
  crossFunctionBeams: boolean;
}

export const DEFAULT_LAYERS: LayerFlags = {
  activityHeat: true,
  entityFlows: true,
  decisionSparks: true,
  ambientFlashes: true,
  cadencePulses: true,
  crossFunctionBeams: true,
};

const STORAGE_KEY = "org-building.layers";

export function loadLayers(): LayerFlags {
  try {
    const raw = window.localStorage.getItem(STORAGE_KEY);
    if (!raw) return DEFAULT_LAYERS;
    const parsed = JSON.parse(raw) as Partial<LayerFlags>;
    return { ...DEFAULT_LAYERS, ...parsed };
  } catch {
    return DEFAULT_LAYERS;
  }
}

export function saveLayers(flags: LayerFlags): void {
  try {
    window.localStorage.setItem(STORAGE_KEY, JSON.stringify(flags));
  } catch {
    // Ignore — quota / private mode.
  }
}

export function useLayerToggles(): {
  layers: LayerFlags;
  setLayer: (k: keyof LayerFlags, v: boolean) => void;
} {
  const [layers, setLayers] = useState<LayerFlags>(() => {
    if (typeof window === "undefined") return DEFAULT_LAYERS;
    return loadLayers();
  });

  useEffect(() => {
    saveLayers(layers);
  }, [layers]);

  const setLayer = useCallback((k: keyof LayerFlags, v: boolean) => {
    setLayers((cur) => ({ ...cur, [k]: v }));
  }, []);

  return { layers, setLayer };
}

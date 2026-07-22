import { useEffect, useState } from "react";

import type { WorldSceneContract } from "@client/components/world/SpatialWorld";


export interface WorldSceneState {
  scene: WorldSceneContract | null;
  loading: boolean;
  error: string | null;
}


export function useWorldScene(active: boolean): WorldSceneState {
  const [state, setState] = useState<WorldSceneState>({
    scene: null,
    loading: active,
    error: null,
  });

  useEffect(() => {
    if (!active) {
      setState({ scene: null, loading: false, error: null });
      return;
    }
    const controller = new AbortController();
    setState((current) => ({ ...current, loading: true, error: null }));

    async function load() {
      try {
        const response = await fetch("/api/world/scene", {
          signal: controller.signal,
        });
        if (!response.ok) {
          throw new Error(`world scene HTTP ${response.status}`);
        }
        const payload = await response.json() as WorldSceneContract | { enabled: false };
        if (payload.enabled !== true) {
          setState({ scene: null, loading: false, error: null });
          return;
        }
        setState({ scene: payload, loading: false, error: null });
      } catch (error) {
        if (controller.signal.aborted) return;
        setState({
          scene: null,
          loading: false,
          error: error instanceof Error ? error.message : "world scene unavailable",
        });
      }
    }

    void load();
    return () => controller.abort();
  }, [active]);

  return state;
}


import { useEffect, useState } from "react";
import type { RuntimeManifest } from "@shared/runtime";

export interface RuntimeManifestState {
  manifest: RuntimeManifest | null;
  loading: boolean;
  error: string | null;
}

export function useRuntimeManifest(): RuntimeManifestState {
  const [state, setState] = useState<RuntimeManifestState>({
    manifest: null,
    loading: true,
    error: null,
  });

  useEffect(() => {
    const controller = new AbortController();

    async function load() {
      try {
        const response = await fetch("/api/runtime", {
          signal: controller.signal,
        });
        if (!response.ok) {
          throw new Error(`runtime manifest HTTP ${response.status}`);
        }
        const manifest = await response.json() as RuntimeManifest;
        setState({ manifest, loading: false, error: null });
      } catch (error) {
        if (controller.signal.aborted) return;
        const message = error instanceof Error
          ? error.message
          : "runtime manifest request failed";
        setState({ manifest: null, loading: false, error: message });
      }
    }

    void load();
    return () => controller.abort();
  }, []);

  return state;
}

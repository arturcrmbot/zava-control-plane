import { useCallback, useEffect, useState } from "react";

/**
 * Source detection fails closed: an unavailable probe is not a live runtime.
 * The page shares this result with every HUD instead of probing independently.
 */
export type ReplayModeInfo =
  | { mode: "loading" }
  | { mode: "live" }
  | { mode: "replay"; recordedAt?: string }
  | { mode: "unavailable"; error: string };

export function useReplayMode(): { source: ReplayModeInfo; retry: () => void } {
  const [source, setSource] = useState<ReplayModeInfo>({ mode: "loading" });
  const [attempt, setAttempt] = useState(0);
  const retry = useCallback(() => {
    setSource({ mode: "loading" });
    setAttempt((value) => value + 1);
  }, []);
  useEffect(() => {
    let cancelled = false;
    async function probe() {
      try {
        const response = await fetch("/api/replay/meta");
        if (!response.ok) {
          throw new Error(`Could not determine source mode (${response.status})`);
        }
        const meta: unknown = await response.json();
        if (typeof meta !== "object" || meta === null || !("mode" in meta)) {
          throw new Error("Source metadata has no recognised mode");
        }
        let next: ReplayModeInfo;
        if (meta.mode === "replay") {
          const recordedAt = "recorded_at" in meta ? meta.recorded_at : undefined;
          if (
            recordedAt !== undefined && recordedAt !== null &&
            (typeof recordedAt !== "string" || Number.isNaN(Date.parse(recordedAt)))
          ) {
            throw new Error("Source metadata has an invalid recording date");
          }
          next = {
            mode: "replay",
            recordedAt: typeof recordedAt === "string" ? recordedAt : undefined,
          };
        } else if (meta.mode === "live") {
          next = { mode: "live" };
        } else {
          throw new Error("Source metadata has no recognised mode");
        }
        if (!cancelled) setSource(next);
      } catch (error) {
        if (!cancelled) {
          setSource({
            mode: "unavailable",
            error: error instanceof Error ? error.message : "Could not determine source mode",
          });
        }
      }
    }
    void probe();
    return () => { cancelled = true; };
  }, [attempt]);
  return { source, retry };
}

import { useEffect, useState } from "react";

export type ReplayMetaLive = { mode: "live" };
export type ReplayMetaReplay = {
  mode: "replay";
  tape_id?: string;
  recorded_at?: string;
  duration_s?: number;
  current_t?: number;
  selected_vertical?: string;
  active_vertical?: string;
  pack_matches_tape?: boolean | null;
};
export type ReplayMeta = ReplayMetaLive | ReplayMetaReplay;

const POLL_INTERVAL_MS = 30_000;

export function useReplayMeta(): ReplayMeta | null {
  const [meta, setMeta] = useState<ReplayMeta | null>(null);

  useEffect(() => {
    let cancelled = false;

    async function tick() {
      try {
        const response = await fetch("/api/replay/meta");
        if (!response.ok) return;
        const body = await response.json() as ReplayMeta;
        if (!cancelled) setMeta(body);
      } catch {
        // Leave the previous value in place.
      }
    }

    void tick();
    const id = setInterval(() => { void tick(); }, POLL_INTERVAL_MS);

    return () => {
      cancelled = true;
      clearInterval(id);
    };
  }, []);

  return meta;
}

import { useEffect, useState } from "react";

/**
 * Probes `/api/replay/meta` once at mount to detect whether the API
 * process is serving a recorded tape (replay) or live state.
 *
 * The HUD uses this to:
 *  - hide mutating affordances (e.g. ⚡ Spawn 8 cases) that the read-only
 *    middleware will 403 anyway, and
 *  - swap the "Live" status pill for a "Replay" indicator so operators
 *    aren't fooled into thinking they're watching real-time activity.
 */
export interface ReplayModeInfo {
  isReplay: boolean;
  recordedAt?: string;
}

export function useReplayMode(): ReplayModeInfo {
  const [info, setInfo] = useState<ReplayModeInfo>({ isReplay: false });
  useEffect(() => {
    let cancelled = false;
    fetch("/api/replay/meta")
      .then((r) => (r.ok ? r.json() : null))
      .then((meta) => {
        if (cancelled || !meta) return;
        if (meta.mode === "replay") {
          setInfo({ isReplay: true, recordedAt: meta.recorded_at });
        }
      })
      .catch(() => { /* assume live on probe failure */ });
    return () => { cancelled = true; };
  }, []);
  return info;
}

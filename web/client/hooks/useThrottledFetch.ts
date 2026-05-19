// web/client/hooks/useThrottledFetch.ts
//
// Returns a throttled `refresh` that coalesces bursts of trigger calls into
// at most one in-flight request, with a trailing call so the UI still
// converges on the latest server state even when events arrive faster than
// `minIntervalMs`.
//
// Why this exists: the data hooks (useWorkflows, useExceptions) used to call
// refresh() on every SSE message. With Azure Functions firing dozens of
// orchestration events per second under real load, the browser exhausted its
// HTTP connection pool inside ~30s (net::ERR_INSUFFICIENT_RESOURCES) and the
// feed froze. Coalescing fixes the storm at the source without losing data.
import { useCallback, useEffect, useRef } from "react";

export function useThrottledFetch<T>(
  url: string,
  setData: (next: T) => void,
  minIntervalMs = 750,
): () => void {
  const lastFireRef = useRef<number>(0);
  const pendingRef = useRef<boolean>(false);
  const inFlightRef = useRef<boolean>(false);
  const aliveRef = useRef<boolean>(true);
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => {
    aliveRef.current = true;
    return () => {
      aliveRef.current = false;
      if (timerRef.current) clearTimeout(timerRef.current);
    };
  }, []);

  const doFetch = useCallback(async () => {
    if (!aliveRef.current) return;
    inFlightRef.current = true;
    lastFireRef.current = Date.now();
    try {
      const r = await fetch(url);
      if (!r.ok) return;
      const data = (await r.json()) as T;
      if (aliveRef.current) setData(data);
    } catch {
      // network blip — leave previous data alone; next trigger will retry.
    } finally {
      inFlightRef.current = false;
      // If a trigger arrived while we were in flight, fire the trailing call.
      if (pendingRef.current && aliveRef.current) {
        pendingRef.current = false;
        const wait = Math.max(0, minIntervalMs - (Date.now() - lastFireRef.current));
        timerRef.current = setTimeout(() => void doFetch(), wait);
      }
    }
  }, [url, setData, minIntervalMs]);

  const trigger = useCallback(() => {
    if (!aliveRef.current) return;
    if (inFlightRef.current) {
      pendingRef.current = true;
      return;
    }
    const since = Date.now() - lastFireRef.current;
    if (since < minIntervalMs) {
      if (!timerRef.current) {
        timerRef.current = setTimeout(() => {
          timerRef.current = null;
          void doFetch();
        }, minIntervalMs - since);
      }
      return;
    }
    void doFetch();
  }, [doFetch, minIntervalMs]);

  return trigger;
}

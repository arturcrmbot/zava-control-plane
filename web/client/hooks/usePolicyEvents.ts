// web/client/hooks/usePolicyEvents.ts
//
// Polls /api/policy/ on a fixed interval. On each poll, diffs against the
// previous snapshot keyed by (id, gitSha) and appends a PolicySnapshot for
// every changed or new row. Cap kept at 50 most-recent events.
import { useEffect, useRef, useState } from "react";
import type { PolicySnapshot } from "@shared/feedItems";

const MAX_EVENTS = 50;

export function usePolicyEvents(intervalMs = 30_000): PolicySnapshot[] {
  const [events, setEvents] = useState<PolicySnapshot[]>([]);
  const lastByKey = useRef<Map<string, string>>(new Map());
  const baselineLoaded = useRef(false);

  useEffect(() => {
    let cancelled = false;

    async function poll(): Promise<void> {
      try {
        const r = await fetch("/api/policy/");
        if (!r.ok) return;
        const rows = (await r.json()) as Array<{
          id: string;
          description: string;
          currentValue: number | string | boolean;
          gitSha?: string;
          author?: string;
          updatedAt?: number;
        }>;
        if (cancelled) return;
        const newEvents: PolicySnapshot[] = [];
        for (const row of rows) {
          const key = `${row.id}|${row.gitSha ?? "_"}`;
          if (!lastByKey.current.has(key)) {
            if (baselineLoaded.current) newEvents.push(row);
            lastByKey.current.set(key, key);
          }
        }
        baselineLoaded.current = true;
        if (newEvents.length > 0) {
          setEvents((prev) => [...newEvents, ...prev].slice(0, MAX_EVENTS));
        }
      } catch {
        /* network blip — try again next tick */
      }
    }

    void poll();
    const t = setInterval(() => void poll(), intervalMs);
    return () => {
      cancelled = true;
      clearInterval(t);
    };
  }, [intervalMs]);

  return events;
}

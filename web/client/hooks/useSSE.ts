// src/client/hooks/useSSE.ts
//
// Multiplexes SSE so multiple callers subscribing to the same URL share a
// SINGLE EventSource connection. Chrome's HTTP/1.1 per-domain limit is 6;
// the feed naturally subscribes to /api/stream/fleet from multiple hooks
// (useWorkflows + useExceptions) and StrictMode dev-mode double-invokes
// the mount cycle, so unmultiplexed EventSources can saturate the pool
// and leave new subscribers stuck in CONNECTING (readyState=0) forever.
//
// One EventSource per path, ref-counted; closes when the last subscriber
// unmounts.
import { useEffect } from "react";

type Listener = (parsed: unknown) => void;

interface Shared {
  es: EventSource;
  listeners: Set<Listener>;
}

const SHARED: Map<string, Shared> = (() => {
  const g = globalThis as { __sseShared?: Map<string, Shared> };
  if (!g.__sseShared) g.__sseShared = new Map();
  return g.__sseShared;
})();

function subscribe(path: string, listener: Listener): () => void {
  let shared = SHARED.get(path);
  if (!shared) {
    const es = new EventSource(path);
    const listeners = new Set<Listener>();
    es.onmessage = (ev) => {
      let parsed: unknown;
      try {
        parsed = JSON.parse(ev.data);
      } catch {
        return;
      }
      // Snapshot to avoid mutation during iteration.
      [...listeners].forEach((fn) => {
        try { fn(parsed); } catch { /* listener errors must not break the bus */ }
      });
    };
    shared = { es, listeners };
    SHARED.set(path, shared);
  }
  shared.listeners.add(listener);
  return () => {
    const cur = SHARED.get(path);
    if (!cur) return;
    cur.listeners.delete(listener);
    if (cur.listeners.size === 0) {
      cur.es.close();
      SHARED.delete(path);
    }
  };
}

export function useSSE<T>(path: string, onMessage: (data: T) => void): void {
  useEffect(() => {
    const listener: Listener = (data) => onMessage(data as T);
    return subscribe(path, listener);
  }, [path, onMessage]);
}

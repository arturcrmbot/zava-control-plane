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
//
// Status tracking: each shared connection records its lifecycle state
// (connecting / open / error). `useSSEStatus()` returns the aggregate state
// across every active connection so the UI can show a single "live | degraded
// | offline" indicator in the header.
import { useEffect, useState } from "react";

type Listener = (parsed: unknown) => void;
type StatusListener = () => void;
export type SSEStatus = "connecting" | "open" | "error";

interface Shared {
  es: EventSource;
  listeners: Set<Listener>;
  status: SSEStatus;
}

const SHARED: Map<string, Shared> = (() => {
  const g = globalThis as { __sseShared?: Map<string, Shared> };
  if (!g.__sseShared) g.__sseShared = new Map();
  return g.__sseShared;
})();

const STATUS_LISTENERS: Set<StatusListener> = (() => {
  const g = globalThis as { __sseStatusListeners?: Set<StatusListener> };
  if (!g.__sseStatusListeners) g.__sseStatusListeners = new Set();
  return g.__sseStatusListeners;
})();

function notifyStatus(): void {
  [...STATUS_LISTENERS].forEach((fn) => {
    try { fn(); } catch { /* ignore */ }
  });
}

function subscribe(path: string, listener: Listener): () => void {
  let shared = SHARED.get(path);
  if (!shared) {
    const es = new EventSource(path);
    const listeners = new Set<Listener>();
    const ref: Shared = { es, listeners, status: "connecting" };
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
    es.onopen = () => {
      if (ref.status !== "open") {
        ref.status = "open";
        notifyStatus();
      }
    };
    es.onerror = () => {
      // EventSource auto-reconnects; once it does, onopen fires again. We
      // report "error" while in the dropped/reconnecting state.
      const next: SSEStatus = ref.es.readyState === EventSource.CLOSED ? "error" : "connecting";
      if (ref.status !== next) {
        ref.status = next;
        notifyStatus();
      }
    };
    shared = ref;
    SHARED.set(path, shared);
    notifyStatus();
  }
  shared.listeners.add(listener);
  return () => {
    const cur = SHARED.get(path);
    if (!cur) return;
    cur.listeners.delete(listener);
    if (cur.listeners.size === 0) {
      cur.es.close();
      SHARED.delete(path);
      notifyStatus();
    }
  };
}

export function useSSE<T>(path: string, onMessage: (data: T) => void): void {
  useEffect(() => {
    const listener: Listener = (data) => onMessage(data as T);
    return subscribe(path, listener);
  }, [path, onMessage]);
}

function aggregate(): SSEStatus {
  // No streams = treat as connecting (page hasn't subscribed yet).
  if (SHARED.size === 0) return "connecting";
  let anyOpen = false;
  let anyConnecting = false;
  for (const s of SHARED.values()) {
    if (s.status === "error") return "error";
    if (s.status === "open") anyOpen = true;
    if (s.status === "connecting") anyConnecting = true;
  }
  if (anyConnecting) return "connecting";
  return anyOpen ? "open" : "connecting";
}

/** Returns the aggregate live/degraded/offline state of all SSE streams. */
export function useSSEStatus(): SSEStatus {
  const [status, setStatus] = useState<SSEStatus>(() => aggregate());
  useEffect(() => {
    const fn = () => setStatus(aggregate());
    STATUS_LISTENERS.add(fn);
    // Sync immediately in case state changed before subscribe.
    fn();
    return () => { STATUS_LISTENERS.delete(fn); };
  }, []);
  return status;
}

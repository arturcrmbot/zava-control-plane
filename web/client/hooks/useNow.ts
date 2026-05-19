// web/client/hooks/useNow.ts
//
// Single shared "current time" ticker. Components subscribe to a periodic
// re-render so that anything derived from `Date.now()` (clocks, relative
// timestamps like "4s ago", live "today" chips) stays current without
// needing data to change.
//
// Implementation: one module-level setInterval shared across all callers.
// Each subscriber is a React setState; the interval bumps every one of them
// once per tick. Default cadence is 1s, which is the granularity we want
// for the header clock and "Xs ago" timestamps inside the first minute.
import { useEffect, useState } from "react";

const SUBSCRIBERS = new Set<() => void>();
let timerId: ReturnType<typeof setInterval> | null = null;

function ensureTicker(intervalMs: number) {
  if (timerId != null) return;
  timerId = setInterval(() => {
    for (const sub of SUBSCRIBERS) sub();
  }, intervalMs);
}

function teardownIfIdle() {
  if (SUBSCRIBERS.size === 0 && timerId != null) {
    clearInterval(timerId);
    timerId = null;
  }
}

/** Returns the current Date.now() value, re-rendering every `intervalMs` ms. */
export function useNow(intervalMs: number = 1000): number {
  const [now, setNow] = useState<number>(() => Date.now());

  useEffect(() => {
    const sub = () => setNow(Date.now());
    SUBSCRIBERS.add(sub);
    ensureTicker(intervalMs);
    return () => {
      SUBSCRIBERS.delete(sub);
      teardownIfIdle();
    };
  }, [intervalMs]);

  return now;
}

/** Formats an absolute epoch-seconds timestamp as "Xs ago" / "Xm ago" / etc. */
export function formatRelative(tsSec: number, nowMs: number = Date.now()): string {
  const diff = Math.max(0, nowMs / 1000 - tsSec);
  if (diff < 60) return `${Math.round(diff)}s ago`;
  if (diff < 3600) return `${Math.round(diff / 60)}m ago`;
  if (diff < 86400) return `${(diff / 3600).toFixed(1)}h ago`;
  return `${Math.round(diff / 86400)}d ago`;
}

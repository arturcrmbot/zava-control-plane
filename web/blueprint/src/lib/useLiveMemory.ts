/**
 * useLiveMemory — joins `/api/memory/per-persona` (polled) with the
 * dream-pass lifecycle events streamed by `/api/blueprint/stream`.
 *
 * Returns:
 *   - byFunction: Map<function_key, { lessons, working, dreaming }>
 *     for each function/persona planet to consult when rendering.
 *   - activeDream: { domain, startedAt } | null — set when a
 *     `dream.pass.started` event arrives, cleared by `finished` (or
 *     a 6s timeout in case the finished event is missed).
 *
 * The hook is intentionally tolerant of missing data: a function with
 * no entries shows nothing extra; the constellation degrades gracefully
 * when the backend isn't wired.
 */
import { useEffect, useRef, useState } from "react";
import type { ObservatoryEvent } from "./types";

export interface PerPersonaItem {
  domain: string;
  persona_role: string;
  function_key: string;
  lessons: number;
  working: number;
  recent_lesson: string | null;
}

export interface FunctionMemorySummary {
  lessons: number;
  working: number;
  /** Recent lesson text (first one we saw) for tooltip / drawer. */
  recent_lesson: string | null;
  /** True while a dream pass for any domain owned by this function is
   *  in flight. */
  dreaming: boolean;
  /** Domains contributing to this function's count. */
  domains: string[];
}

interface UseLiveMemoryOptions {
  /** Polling interval in ms for /api/memory/per-persona. */
  pollMs?: number;
  /** When true, ignore the SSE event channel (for tests). */
  noStream?: boolean;
}

export function useLiveMemory(opts: UseLiveMemoryOptions = {}) {
  const pollMs = opts.pollMs ?? 5000;
  const [byFunction, setByFunction] = useState<Map<string, FunctionMemorySummary>>(new Map());
  const [activeDream, setActiveDream] = useState<{ domain: string; startedAt: number } | null>(null);
  /** Map persona_role -> function_key so dream events (which carry only
   *  `domain`) can be routed to the right planet via any persona that
   *  ever wrote a memory for that domain. */
  const domainToFunction = useRef<Map<string, string>>(new Map());

  // Polling loop.
  useEffect(() => {
    let cancelled = false;
    let timer: number | undefined;

    async function tick() {
      try {
        const r = await fetch("/api/memory/per-persona");
        if (!r.ok) return;
        const data = (await r.json()) as { items: PerPersonaItem[] };
        if (cancelled) return;
        const next = new Map<string, FunctionMemorySummary>();
        const d2f = new Map<string, string>();
        for (const it of data.items ?? []) {
          const key = it.function_key || "_unattributed";
          const prev = next.get(key) ?? {
            lessons: 0,
            working: 0,
            recent_lesson: null,
            dreaming: false,
            domains: [],
          };
          prev.lessons += it.lessons;
          prev.working += it.working;
          if (!prev.recent_lesson && it.recent_lesson) {
            prev.recent_lesson = it.recent_lesson;
          }
          if (it.domain && !prev.domains.includes(it.domain)) {
            prev.domains.push(it.domain);
          }
          next.set(key, prev);
          if (it.function_key && it.domain) {
            d2f.set(it.domain, it.function_key);
          }
        }
        domainToFunction.current = d2f;
        setByFunction(next);
      } catch {
        // ignore — degrade gracefully.
      }
    }
    tick();
    timer = window.setInterval(tick, pollMs);
    return () => {
      cancelled = true;
      if (timer != null) window.clearInterval(timer);
    };
  }, [pollMs]);

  // SSE subscription for dream.pass.* events. We open our own connection
  // (separate from useObservatory so the constellation can keep using
  // its existing one without coupling). Reconnects on transport error.
  useEffect(() => {
    if (opts.noStream) return;
    let cancelled = false;
    let es: EventSource | null = null;
    let reconnectTimer: number | undefined;
    let clearTimer: number | undefined;
    // Track when each domain went dreaming so a fast finished event
    // doesn't blow the pulse away before React paints it.
    const dreamingStartedAt = new Map<string, number>();
    const MIN_VISIBLE_MS = 1500;

    function _setDomainDreaming(dom: string, on: boolean) {
      setByFunction((prev) => {
        const next = new Map(prev);
        const fk = domainToFunction.current.get(dom);
        if (fk) {
          const cur = next.get(fk) ?? {
            lessons: 0,
            working: 0,
            recent_lesson: null,
            dreaming: false,
            domains: [dom],
          };
          next.set(fk, { ...cur, dreaming: on });
        }
        return next;
      });
    }

    function handle(e: ObservatoryEvent) {
      if (!e.type.startsWith("dream.")) return;
      const dom = e.domain;
      if (e.type === "dream.pass.started" && dom) {
        dreamingStartedAt.set(dom, Date.now());
        setActiveDream({ domain: dom, startedAt: Date.now() });
        _setDomainDreaming(dom, true);
        // Safety timeout — if `finished` never arrives within 12s, clear.
        if (clearTimer) window.clearTimeout(clearTimer);
        clearTimer = window.setTimeout(() => {
          setActiveDream((cur) => (cur && cur.domain === dom ? null : cur));
          _setDomainDreaming(dom, false);
          dreamingStartedAt.delete(dom);
        }, 12000);
      } else if (e.type === "dream.pass.finished" && dom) {
        const startedAt = dreamingStartedAt.get(dom);
        const elapsed = startedAt ? Date.now() - startedAt : MIN_VISIBLE_MS;
        const remaining = Math.max(0, MIN_VISIBLE_MS - elapsed);
        if (clearTimer) {
          window.clearTimeout(clearTimer);
          clearTimer = undefined;
        }
        if (remaining > 0) {
          // Hold the dreaming flag long enough for React to paint it.
          window.setTimeout(() => {
            setActiveDream((cur) => (cur && cur.domain === dom ? null : cur));
            _setDomainDreaming(dom, false);
            dreamingStartedAt.delete(dom);
            // Refresh the polled summary so the new lesson count is
            // reflected immediately rather than waiting up to pollMs.
            fetch("/api/memory/per-persona")
              .then(r => r.json())
              .then((data: { items: PerPersonaItem[] }) => {
                if (cancelled) return;
                const next = new Map<string, FunctionMemorySummary>();
                const d2f = new Map<string, string>();
                for (const it of data.items ?? []) {
                  const key = it.function_key || "_unattributed";
                  const prev = next.get(key) ?? {
                    lessons: 0, working: 0, recent_lesson: null,
                    dreaming: false, domains: [],
                  };
                  prev.lessons += it.lessons;
                  prev.working += it.working;
                  if (!prev.recent_lesson && it.recent_lesson) {
                    prev.recent_lesson = it.recent_lesson;
                  }
                  if (it.domain && !prev.domains.includes(it.domain)) {
                    prev.domains.push(it.domain);
                  }
                  next.set(key, prev);
                  if (it.function_key && it.domain) {
                    d2f.set(it.domain, it.function_key);
                  }
                }
                domainToFunction.current = d2f;
                setByFunction(next);
              })
              .catch(() => {});
          }, remaining);
        } else {
          setActiveDream((cur) => (cur && cur.domain === dom ? null : cur));
          _setDomainDreaming(dom, false);
          dreamingStartedAt.delete(dom);
        }
      }
    }

    function connect() {
      if (cancelled) return;
      es = new EventSource("/api/blueprint/stream");
      es.addEventListener("event", (ev) => {
        try {
          const data = JSON.parse((ev as MessageEvent).data) as ObservatoryEvent;
          handle(data);
        } catch {
          // ignore malformed events
        }
      });
      es.onerror = () => {
        if (cancelled) return;
        if (es) {
          es.close();
          es = null;
        }
        reconnectTimer = window.setTimeout(connect, 2000);
      };
    }
    connect();
    return () => {
      cancelled = true;
      if (es) es.close();
      if (reconnectTimer != null) window.clearTimeout(reconnectTimer);
      if (clearTimer != null) window.clearTimeout(clearTimer);
    };
  }, [opts.noStream]);

  return { byFunction, activeDream };
}

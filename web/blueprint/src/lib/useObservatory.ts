import { useEffect, useRef, useState } from "react";
import type { ObservatoryEvent } from "./types";

export type ObservatoryStatus = "connecting" | "watching" | "offline";

interface UseObservatoryOptions {
  /** Maximum number of events to keep in the rolling feed. */
  bufferSize?: number;
  /** Optional callback invoked for every incoming event. Use for ephemeral
   * pulse animations that don't need to be re-rendered as state changes. */
  onEvent?: (e: ObservatoryEvent) => void;
}

/**
 * Subscribe to /api/blueprint/stream over EventSource. Returns:
 *   - events: a rolling list of recent events
 *   - counters: aggregate rolling counts
 *   - status: "connecting" | "watching" | "offline"
 *
 * Reconnects on transport error after a short delay.
 */
export function useObservatory(opts: UseObservatoryOptions = {}) {
  const bufferSize = opts.bufferSize ?? 80;
  const [events, setEvents] = useState<ObservatoryEvent[]>([]);
  const [status, setStatus] = useState<ObservatoryStatus>("connecting");
  const [counters, setCounters] = useState({
    workflowsStarted: 0,
    skillsInvoked: 0,
    toolCalls: 0,
    validatorsBlocked: 0,
    workflowsCompleted: 0,
  });
  // Track which workflow_ids we've seen start/complete events for so we can
  // count each at most once even if the orchestrator emits both the legacy
  // and the canonical event names for the same workflow.
  const seenStartedRef = useRef<Set<string>>(new Set());
  const seenCompletedRef = useRef<Set<string>>(new Set());
  const onEventRef = useRef(opts.onEvent);
  onEventRef.current = opts.onEvent;

  useEffect(() => {
    let es: EventSource | null = null;
    let reconnectTimer: number | undefined;
    let cancelled = false;

    function connect() {
      if (cancelled) return;
      setStatus("connecting");
      es = new EventSource("/api/blueprint/stream");
      es.addEventListener("hello", () => {
        if (!cancelled) setStatus("watching");
      });
      es.addEventListener("event", (raw) => {
        const data = JSON.parse((raw as MessageEvent).data) as ObservatoryEvent;
        if (cancelled) return;
        setEvents((prev) => {
          const next = [data, ...prev];
          if (next.length > bufferSize) next.length = bufferSize;
          return next;
        });
        setCounters((c) => {
          const next = { ...c };
          const wid = data.workflow_id ?? "?";

          // Workflow lifecycle: count a workflow as 'started' the first
          // time we see ANY event referencing its workflow_id. The page
          // mounts mid-trickle and missing the actual workflow.started
          // emit shouldn't make 'workflows started' read 0 while skills
          // and tool calls are clearly firing.
          if (wid !== "?" && !seenStartedRef.current.has(wid)) {
            seenStartedRef.current.add(wid);
            next.workflowsStarted += 1;
          }

          switch (data.type) {
            case "durable.executor.invoked": {
              // Only count on `start` so we don't double-count start+complete.
              if (data.stage && data.stage !== "start") break;
              const et = data.executor_type ?? "";
              if (et === "agent") {
                // A skill run is an agent-executor invocation.
                next.skillsInvoked += 1;
              } else if (et === "tool" || data.tool) {
                next.toolCalls += 1;
              }
              // Deterministic + validator executors are infrastructure noise
              // for these counters; don't roll them up.
              break;
            }
            case "durable.validator.blocked":
              next.validatorsBlocked += 1;
              break;
            case "durable.workflow.completed":
            case "workflow.resolved": {
              if (!seenCompletedRef.current.has(wid)) {
                seenCompletedRef.current.add(wid);
                next.workflowsCompleted += 1;
              }
              break;
            }
          }
          return next;
        });
        onEventRef.current?.(data);
      });
      es.addEventListener("heartbeat", () => {
        if (!cancelled) setStatus("watching");
      });
      es.onerror = () => {
        if (cancelled) return;
        setStatus("offline");
        es?.close();
        reconnectTimer = window.setTimeout(connect, 4000);
      };
    }

    connect();
    return () => {
      cancelled = true;
      if (reconnectTimer) window.clearTimeout(reconnectTimer);
      es?.close();
    };
  }, [bufferSize]);

  return { events, counters, status };
}

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
    agentInvocations: 0,
    toolCalls: 0,
    validatorsBlocked: 0,
    workflowsCompleted: 0,
  });
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
          switch (data.type) {
            case "workflow.started":
            case "durable.workflow.started":
              next.workflowsStarted += 1;
              break;
            case "durable.step.started":
            case "agent.completed":
            case "durable.executor.invoked":
              next.agentInvocations += 1;
              if (data.tool) next.toolCalls += 1;
              break;
            case "durable.validator.blocked":
              next.validatorsBlocked += 1;
              break;
            case "durable.workflow.completed":
            case "workflow.resolved":
              next.workflowsCompleted += 1;
              break;
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

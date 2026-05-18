// src/client/hooks/useOrchestrationStream.ts
import { useCallback, useRef, useState } from "react";
import { useSSE } from "./useSSE";

export interface OrchestrationEvent {
  kind: string;        // workflow.started | step.started | step.completed | executor.invoked
                       // | validator.blocked | suspended | resumed | workflow.completed | step.failed
  workflow_id: string;
  payload: {
    name?: string;
    type?: string;     // deterministic | agent | validator
    stage?: string;    // start | complete | error
    step?: string;
    reason?: string;
    duration_ms?: number;
    error?: string;
    [k: string]: unknown;
  };
  receivedAt: number;  // ms since epoch, stamped on SSE receipt; deterministic across renders
}

export function useOrchestrationStream(max = 100) {
  const [events, setEvents] = useState<OrchestrationEvent[]>([]);
  const ref = useRef<OrchestrationEvent[]>([]);
  useSSE<Omit<OrchestrationEvent, "receivedAt">>("/api/stream/orchestration", useCallback((e) => {
    const stamped: OrchestrationEvent = { ...e, receivedAt: Date.now() };
    ref.current = [stamped, ...ref.current].slice(0, max);
    setEvents(ref.current.slice());
  }, [max]));
  return events;
}

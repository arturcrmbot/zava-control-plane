import { useEffect, useRef, useState } from "react";
import type { ObservatoryEvent } from "./types";
import { RECORDINGS } from "./recordings.fixture";
import type { ObservatoryStatus } from "./useObservatory";

// How many ms between recording start times. Lower → more overlap. The
// MindMap is designed as a "wall of recent activity" so overlapping
// workflows make the page feel alive without firehosing the viewer.
const RECORDING_START_INTERVAL_MS = 7000;
// After all recordings have finished, wait this long before looping back.
const LOOP_GAP_MS = 4000;
// Rolling event buffer size — matches old useObservatory default.
const BUFFER_SIZE = 80;

interface Counters {
  workflowsStarted: number;
  skillsInvoked: number;
  toolCalls: number;
  validatorsBlocked: number;
  workflowsCompleted: number;
}

const ZERO_COUNTERS: Counters = {
  workflowsStarted: 0,
  skillsInvoked: 0,
  toolCalls: 0,
  validatorsBlocked: 0,
  workflowsCompleted: 0,
};

/**
 * Static-deploy replacement for useObservatory. Replays the bundled
 * recordings in an overlapping loop so the MindMap renders a
 * continuously-evolving picture without needing a backend.
 */
export function useReplayObservatory(): {
  events: ObservatoryEvent[];
  counters: Counters;
  status: ObservatoryStatus;
} {
  const [events, setEvents] = useState<ObservatoryEvent[]>([]);
  const [counters, setCounters] = useState<Counters>(ZERO_COUNTERS);
  const seenStarted = useRef<Set<string>>(new Set());
  const seenCompleted = useRef<Set<string>>(new Set());

  useEffect(() => {
    const timers: number[] = [];
    let cancelled = false;

    function dispatch(ev: ObservatoryEvent) {
      if (cancelled) return;
      setEvents((prev) => {
        const next = [{ ...ev, ts: Date.now() / 1000 }, ...prev];
        if (next.length > BUFFER_SIZE) next.length = BUFFER_SIZE;
        return next;
      });
      setCounters((prev) => {
        const wid = ev.workflow_id ?? null;
        const next = { ...prev };
        if (
          (ev.type === "workflow.started" ||
            ev.type === "durable.workflow.started") &&
          wid &&
          !seenStarted.current.has(wid)
        ) {
          seenStarted.current.add(wid);
          next.workflowsStarted += 1;
        }
        if (
          ev.type === "durable.step.started" ||
          ev.type === "durable.step.completed" ||
          ev.type === "durable.executor.invoked" ||
          ev.type === "agent.completed"
        ) {
          if (ev.tool) next.toolCalls += 1;
          else if (ev.skill) next.skillsInvoked += 1;
        }
        if (ev.type === "durable.validator.blocked") next.validatorsBlocked += 1;
        if (
          (ev.type === "durable.workflow.completed" ||
            ev.type === "workflow.resolved") &&
          wid &&
          !seenCompleted.current.has(wid)
        ) {
          seenCompleted.current.add(wid);
          next.workflowsCompleted += 1;
        }
        return next;
      });
    }

    function scheduleRecording(rec: (typeof RECORDINGS)[number], baseDelayMs: number) {
      for (const { offsetMs, event } of rec.events) {
        const t = window.setTimeout(
          () => dispatch(event),
          baseDelayMs + offsetMs,
        );
        timers.push(t);
      }
    }

    function startCycle() {
      if (cancelled) return;
      // Fresh counters on each cycle so the dashboard pulses rather than
      // accumulating to absurd numbers over a long page view.
      seenStarted.current = new Set();
      seenCompleted.current = new Set();
      setCounters(ZERO_COUNTERS);

      let nextStart = 0;
      let lastEnd = 0;
      for (const rec of RECORDINGS) {
        scheduleRecording(rec, nextStart);
        const recDuration =
          rec.events.length > 0
            ? rec.events[rec.events.length - 1].offsetMs
            : 0;
        const recEnd = nextStart + recDuration;
        if (recEnd > lastEnd) lastEnd = recEnd;
        nextStart += RECORDING_START_INTERVAL_MS;
      }
      const loopDelay = Math.max(nextStart, lastEnd) + LOOP_GAP_MS;
      const loop = window.setTimeout(startCycle, loopDelay);
      timers.push(loop);
    }

    startCycle();

    return () => {
      cancelled = true;
      for (const t of timers) clearTimeout(t);
    };
  }, []);

  return { events, counters, status: "watching" };
}

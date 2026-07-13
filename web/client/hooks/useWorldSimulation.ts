// web/client/hooks/useWorldSimulation.ts
//
// Single polling hook for the /world route. It reads the live actor world:
//
//   - GET /api/world/state          — actor snapshot, every 1000ms
//   - GET /api/world/events?after=  — causal journal tail, every 300ms
//   - POST /api/world/inject/demand_surge — the one write surface
//
// The events cursor advances to the response's latest_seq; events are merged
// by seq into a bounded ring (newest 300, ascending). No SSE, no context, no
// reducer framework — just fetch + intervals + refs, mirroring usePolicyEvents.
import { useCallback, useEffect, useRef, useState } from "react";

const STATE_POLL_MS = 1000;
const EVENTS_POLL_MS = 300;
const EVENT_RING_MAX = 300;
const SURGE_MULTIPLIER = 4;
const SURGE_DURATION_MINUTES = 90;

// -- wire types: mirror api/server/routes/world.py + world/packs/support.py ---

export type TicketStatus = "queued" | "in_service" | "resolved" | "abandoned";

export interface WorldTicket {
  id: string;
  customer_id: string;
  severity: "low" | "medium" | "high";
  required_skill: string;
  status: TicketStatus;
  assigned_worker_id: string | null;
  queued_at: number;
  sla_deadline: number;
  sla_breached: boolean;
  // Present on the real snapshot; used to order terminal lanes.
  assigned_at?: number | null;
  resolved_at?: number | null;
  abandoned_at?: number | null;
  last_event_id?: string | null;
}

export interface WorldWorker {
  id: string;
  team_id: string;
  skills: string[];
  status: string;
  current_ticket_id: string | null;
}

// -- telco wire types: mirror world/packs/telco.py render_state() -----------

export type SessionStatus = "active" | "degraded" | "dropped" | "rerouted";

export interface WorldSite {
  id: string;
  region: string;
  status: string;
  capacity_mbps: number;
  traffic_mbps: number;
  utilization: number;
  packet_loss_pct: number;
  latency_ms: number;
  session_count: number;
  neighbor_ids: string[];
}

export interface WorldSession {
  id: string;
  subscriber_id: string;
  site_id: string;
  origin_site_id: string;
  kind: "voice" | "data" | "video";
  demand_mbps: number;
  status: SessionStatus;
}

export interface WorldSubscriber {
  id: string;
  home_site_id: string;
  tier: string;
  session_count: number;
}

export interface WorldState {
  enabled: boolean;
  scenario?: string;
  seed?: number;
  status?: string;
  sim_time?: number;
  speed?: number;
  latest_seq?: number;
  customers?: Array<{ id: string }>;
  tickets?: WorldTicket[];
  workers?: WorldWorker[];
  // telco scenario fields
  sites?: WorldSite[];
  sessions?: WorldSession[];
  subscribers?: WorldSubscriber[];
}

export interface WorldEvent {
  seq: number;
  event_id: string;
  sim_time: number;
  type: string;
  actor_id: string | null;
  target_id: string | null;
  cause_event_id: string | null;
  trace_id: string;
  payload: Record<string, unknown>;
}

interface WorldEventsResponse {
  enabled: boolean;
  latest_seq: number;
  events: WorldEvent[];
}

export interface UseWorldSimulationResult {
  state: WorldState | null;
  events: WorldEvent[];
  loading: boolean;
  error: string | null;
  injectSurge: () => Promise<void>;
  injectSiteFailure: () => Promise<void>;
}

function isAbort(err: unknown): boolean {
  return err instanceof DOMException ? err.name === "AbortError" : (err as Error)?.name === "AbortError";
}

/** Merge incoming events into the ring: dedupe by seq, sort ascending, keep newest 300. */
function mergeEvents(prev: WorldEvent[], incoming: WorldEvent[]): WorldEvent[] {
  if (incoming.length === 0) return prev;
  const bySeq = new Map<number, WorldEvent>();
  for (const e of prev) bySeq.set(e.seq, e);
  for (const e of incoming) bySeq.set(e.seq, e);
  const merged = Array.from(bySeq.values()).sort((a, b) => a.seq - b.seq);
  return merged.length > EVENT_RING_MAX ? merged.slice(merged.length - EVENT_RING_MAX) : merged;
}

export function useWorldSimulation(): UseWorldSimulationResult {
  const [state, setState] = useState<WorldState | null>(null);
  const [events, setEvents] = useState<WorldEvent[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const cursorRef = useRef(0);
  const abortRef = useRef<AbortController | null>(null);
  const stateInFlight = useRef(false);
  const eventsInFlight = useRef(false);

  const fetchState = useCallback(async (): Promise<void> => {
    if (stateInFlight.current) return;
    stateInFlight.current = true;
    try {
      const r = await fetch("/api/world/state", { signal: abortRef.current?.signal });
      if (!r.ok) throw new Error(`world state HTTP ${r.status}`);
      const body = (await r.json()) as WorldState;
      setState(body);
      setError(null);
    } catch (err) {
      if (isAbort(err)) return;
      setError((err as Error).message || "failed to load world state");
    } finally {
      stateInFlight.current = false;
      setLoading(false);
    }
  }, []);

  const fetchEvents = useCallback(async (): Promise<void> => {
    if (eventsInFlight.current) return;
    eventsInFlight.current = true;
    try {
      const r = await fetch(`/api/world/events?after=${cursorRef.current}`, {
        signal: abortRef.current?.signal,
      });
      if (!r.ok) throw new Error(`world events HTTP ${r.status}`);
      const body = (await r.json()) as WorldEventsResponse;
      if (typeof body.latest_seq === "number") {
        cursorRef.current = Math.max(cursorRef.current, body.latest_seq);
      }
      if (body.events && body.events.length > 0) {
        setEvents((prev) => mergeEvents(prev, body.events));
      }
    } catch (err) {
      if (isAbort(err)) return;
      // Transient events failure: keep the last journal, let the next tick retry.
    } finally {
      eventsInFlight.current = false;
    }
  }, []);

  const injectSurge = useCallback(async (): Promise<void> => {
    try {
      const r = await fetch("/api/world/inject/demand_surge", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          multiplier: SURGE_MULTIPLIER,
          duration_minutes: SURGE_DURATION_MINUTES,
        }),
        signal: abortRef.current?.signal,
      });
      if (!r.ok) throw new Error(`inject surge HTTP ${r.status}`);
    } catch (err) {
      if (isAbort(err)) return;
      setError((err as Error).message || "failed to inject demand surge");
      return;
    }
    await Promise.all([fetchState(), fetchEvents()]);
  }, [fetchState, fetchEvents]);

  const injectSiteFailure = useCallback(async (): Promise<void> => {
    try {
      const r = await fetch("/api/world/inject/site_failure", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({}),
        signal: abortRef.current?.signal,
      });
      if (!r.ok) throw new Error(`inject site failure HTTP ${r.status}`);
    } catch (err) {
      if (isAbort(err)) return;
      setError((err as Error).message || "failed to inject site failure");
      return;
    }
    await Promise.all([fetchState(), fetchEvents()]);
  }, [fetchState, fetchEvents]);

  useEffect(() => {
    const ctrl = new AbortController();
    abortRef.current = ctrl;
    void fetchState();
    void fetchEvents();
    const stateTimer = setInterval(() => void fetchState(), STATE_POLL_MS);
    const eventsTimer = setInterval(() => void fetchEvents(), EVENTS_POLL_MS);
    return () => {
      clearInterval(stateTimer);
      clearInterval(eventsTimer);
      ctrl.abort();
    };
  }, [fetchState, fetchEvents]);

  return { state, events, loading, error, injectSurge, injectSiteFailure };
}

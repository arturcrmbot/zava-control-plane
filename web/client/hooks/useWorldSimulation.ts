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

export interface WorldAccount {
  id: string;
  subscriber_id: string;
  segment: string;
  vulnerable: boolean;
  approval_required: boolean;
  total_credits: number;
  notification_ids: string[];
  credit_ids: string[];
}

export interface WorldSubscription {
  id: string;
  account_id: string;
  subscriber_id: string;
  site_id: string;
  product: string;
  status: string;
}

export interface WorldOrder {
  id: string;
  account_id: string;
  product: string;
  requested_site_id: string;
  status: string;
  reason?: string | null;
}

export interface WorldNotification {
  id: string;
  account_id: string;
  channel: string;
  message: string;
  trace_id: string;
}

export interface WorldCredit {
  id: string;
  account_id: string;
  amount: number;
  trace_id: string;
  authority_approved: boolean;
}

export interface WorldNetworkAsset {
  id: string;
  site_id: string;
  kind: string;
  health: number;
  temperature_c: number;
  load: number;
  failure_probability: number;
  status: string;
  risk_band: string;
}

export interface WorldWorkOrder {
  id: string;
  site_id: string;
  asset_id: string;
  kind: string;
  priority: number;
  required_skill: string;
  required_spare: string;
  due_at: number;
  status: string;
  technician_id: string | null;
}

export interface WorldTechnician {
  id: string;
  region: string;
  skills: string[];
  status: string;
  assigned_work_order_id: string | null;
}

export interface WorldSpareStock {
  id: string;
  region: string;
  part_kind: string;
  quantity: number;
  reorder_point: number;
}

export interface WorldCareTicket {
  id: string;
  account_id: string;
  subscription_id: string;
  incident_trace_id: string;
  category: string;
  severity: string;
  status: string;
  root_cause: string | null;
}

export interface WorldExperienceEpisode {
  id: string;
  account_id: string;
  source_trace_id: string;
  kind: string;
  impact_score: number;
  occurred_at: number;
}

export interface WorldRetentionOffer {
  id: string;
  account_id: string;
  reason: string;
  value_gbp: number;
  offer_kind: string;
  status: string;
}

export interface TelcoProcessSummary {
  source_id: string;
  workflow_type: string;
  display_name: string;
  function: string;
  maturity: "hero" | "standard";
  engine: string;
  skills: string[];
  mcp_packs: string[];
}

export interface TelcoProcessCase {
  id: string;
  workflow_type: string;
  subject_ids: string[];
  status: string;
  facts: Record<string, unknown>;
  allowed_actions: string[];
  recommended_action?: string;
  outcome: Record<string, unknown> | null;
}

// -- objective/command lifecycle: mirror world/model.py + objectives.py ------

export interface WorldObjective {
  id: string;
  type: string;
  trace_id: string;
  owner_function: string;
  priority: number;
  status: string;
  created_at: number;
  deadline: number | null;
  evidence_event_ids: string[];
  allowed_command_types: string[];
  claimed_by: string | null;
}

export interface WorldEvaluation {
  id: string;
  objective_id: string;
  trace_id: string;
  command_id: string;
  started_at: number;
  baseline: Record<string, number>;
  status: string;
}

export interface WorldState {
  [key: string]: unknown;
  enabled: boolean;
  scenario?: string;
  seed?: number;
  status?: string;
  sim_time?: number;
  speed?: number;
  latest_seq?: number;
  customers?: Array<{ id: string; [key: string]: unknown }>;
  tickets?: WorldTicket[];
  workers?: WorldWorker[];
  // telco scenario fields
  sites?: WorldSite[];
  sessions?: WorldSession[];
  subscribers?: WorldSubscriber[];
  accounts?: WorldAccount[];
  subscriptions?: WorldSubscription[];
  orders?: WorldOrder[];
  notifications?: WorldNotification[];
  credits?: WorldCredit[];
  assets?: WorldNetworkAsset[];
  work_orders?: WorldWorkOrder[];
  technicians?: WorldTechnician[];
  spare_stocks?: WorldSpareStock[];
  care_tickets?: WorldCareTicket[];
  experience_episodes?: WorldExperienceEpisode[];
  retention_offers?: WorldRetentionOffer[];
  process_library?: TelcoProcessSummary[];
  process_cases?: TelcoProcessCase[];
  customer_impact?: {
    affected_account_count: number;
    notified_account_count: number;
    credited_account_count: number;
    account_ids: string[];
  };
  // objective/command lifecycle (both worlds)
  objectives?: WorldObjective[];
  evaluations?: WorldEvaluation[];
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
  runScenario: (name: TelcoScenarioName) => Promise<void>;
  runReferenceProcess: (workflowType: string) => Promise<void>;
  resetWorld: () => Promise<void>;
}

export type TelcoScenarioName =
  | "storm-cascade"
  | "maintenance-save"
  | "capacity-revenue"
  | "vulnerable-retention";

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
  const generationRef = useRef(0);
  const abortRef = useRef<AbortController | null>(null);
  const stateInFlight = useRef(false);
  const eventsInFlight = useRef(false);

  const fetchState = useCallback(async (): Promise<void> => {
    if (stateInFlight.current) return;
    stateInFlight.current = true;
    const generation = generationRef.current;
    try {
      const r = await fetch("/api/world/state", { signal: abortRef.current?.signal });
      if (!r.ok) throw new Error(`world state HTTP ${r.status}`);
      const body = (await r.json()) as WorldState;
      if (generation !== generationRef.current) return;
      setState(body);
      setError(null);
    } catch (err) {
      if (isAbort(err)) return;
      if (generation !== generationRef.current) return;
      setError((err as Error).message || "failed to load world state");
    } finally {
      stateInFlight.current = false;
      setLoading(false);
    }
  }, []);

  const fetchEvents = useCallback(async (): Promise<void> => {
    if (eventsInFlight.current) return;
    eventsInFlight.current = true;
    const generation = generationRef.current;
    try {
      const requestedCursor = cursorRef.current;
      let r = await fetch(`/api/world/events?after=${requestedCursor}`, {
        signal: abortRef.current?.signal,
      });
      if (!r.ok) throw new Error(`world events HTTP ${r.status}`);
      let body = (await r.json()) as WorldEventsResponse;
      if (generation !== generationRef.current) return;
      if (
        typeof body.latest_seq === "number"
        && body.latest_seq < requestedCursor
      ) {
        cursorRef.current = 0;
        setEvents([]);
        r = await fetch("/api/world/events?after=0", {
          signal: abortRef.current?.signal,
        });
        if (!r.ok) throw new Error(`world events HTTP ${r.status}`);
        body = (await r.json()) as WorldEventsResponse;
        if (generation !== generationRef.current) return;
      }
      if (typeof body.latest_seq === "number") {
        cursorRef.current = body.latest_seq;
      }
      if (body.events && body.events.length > 0) {
        setEvents((prev) => mergeEvents(prev, body.events));
      }
    } catch (err) {
      if (isAbort(err)) return;
      if (generation !== generationRef.current) return;
      // Transient events failure: keep the last journal, let the next tick retry.
    } finally {
      eventsInFlight.current = false;
    }
  }, []);

  const postInjection = useCallback(
    async (
      path: string,
      body: unknown,
      errorLabel: string,
      fallbackMessage = `failed to ${errorLabel}`,
    ): Promise<void> => {
      try {
        const r = await fetch(`/api/world/inject/${path}`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(body),
          signal: abortRef.current?.signal,
        });
        if (!r.ok) throw new Error(`${errorLabel} HTTP ${r.status}`);
      } catch (err) {
        if (isAbort(err)) return;
        setError((err as Error).message || fallbackMessage);
        return;
      }
      await Promise.all([fetchState(), fetchEvents()]);
    },
    [fetchState, fetchEvents],
  );

  const injectSurge = useCallback(
    (): Promise<void> =>
      postInjection(
        "demand_surge",
        { multiplier: SURGE_MULTIPLIER, duration_minutes: SURGE_DURATION_MINUTES },
        "inject surge",
        "failed to inject demand surge",
      ),
    [postInjection],
  );

  const injectSiteFailure = useCallback(
    (): Promise<void> => postInjection("site_failure", {}, "inject site failure"),
    [postInjection],
  );

  const runScenario = useCallback(
    async (name: TelcoScenarioName): Promise<void> => {
      try {
        const response = await fetch(`/api/world/scenarios/${name}`, {
          method: "POST",
          signal: abortRef.current?.signal,
        });
        if (!response.ok) throw new Error(`run scenario HTTP ${response.status}`);
        const result = await response.json() as { ok?: boolean; error?: string };
        if (!result.ok) throw new Error(result.error || "scenario rejected");
      } catch (err) {
        if (isAbort(err)) return;
        setError((err as Error).message || "failed to run scenario");
        return;
      }
      await Promise.all([fetchState(), fetchEvents()]);
    },
    [fetchState, fetchEvents],
  );

  const runReferenceProcess = useCallback(
    async (workflowType: string): Promise<void> => {
      try {
        const response = await fetch(
          `/api/world/processes/${encodeURIComponent(workflowType)}/run`,
          {
            method: "POST",
            signal: abortRef.current?.signal,
          },
        );

        if (!response.ok) {
          throw new Error(`run process HTTP ${response.status}`);
        }
        const result = await response.json() as { ok?: boolean; error?: string };
        if (!result.ok) throw new Error(result.error || "process rejected");
      } catch (err) {
        if (isAbort(err)) return;
        setError((err as Error).message || "failed to run process");
        return;
      }
      await Promise.all([fetchState(), fetchEvents()]);
    },
    [fetchState, fetchEvents],
  );

  const resetWorld = useCallback(
    async (): Promise<void> => {
      try {
        const response = await fetch("/api/world/reset", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({}),
          signal: abortRef.current?.signal,
        });
        if (!response.ok) throw new Error(`reset world HTTP ${response.status}`);
        const result = await response.json() as { ok?: boolean; error?: string };
        if (!result.ok) throw new Error(result.error || "world reset rejected");
        generationRef.current += 1;
        cursorRef.current = 0;
        setEvents([]);
      } catch (err) {
        if (isAbort(err)) return;
        setError((err as Error).message || "failed to reset world");
        return;
      }
      await Promise.all([fetchState(), fetchEvents()]);
    },
    [fetchState, fetchEvents],
  );

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

  return {
    state,
    events,
    loading,
    error,
    injectSurge,
    injectSiteFailure,
    runScenario,
    runReferenceProcess,
    resetWorld,
  };
}

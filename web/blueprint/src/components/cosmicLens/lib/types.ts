/**
 * Cosmic Lens v2 — Shared types.
 */

export type CosmicMode = "capabilities" | "entities";

export interface FunctionMeta {
  key: string; // "vendor-kyc"
  label: string; // "Vendor KYC"
  family?: string; // "finance"
  /** Some endpoints expose `domains` instead of a single key. */
  domains?: string[];
}

export interface CityMeta {
  id: string;
  kind: string; // mcp | skill | python | validator | persona | entity_type
  label: string;
  category?: string; // optional grouping label
}

export interface PersonaState {
  role: string;
  state: "idle" | "thinking" | "awaiting" | "decided";
  pending_count: number;
  last_decision?: { workflow_id: string; verdict: string; at: number } | null;
}

export interface WorkflowMoonData {
  id: string; // "VKY-0042"
  workflow_type: string; // "vendor-kyc"
  function: string; // "finance" | "vendor-kyc"
  status: string;
  phase?: string;
  created_at?: number;
  age_s?: number;
  active_exception_id?: string | null;
  last_actor?: { kind: string; name: string; at: number };
}

/** A flash event surfaced by useLiveCosmic.flashesRef for animation primitives. */
export interface CosmicFlash {
  type: string; // SSE event type
  ts: number;
  workflow_id?: string;
  caller_workflow_id?: string;
  persona?: string;
  agent_name?: string;
  tool_name?: string;
  entity_kind?: string;
  entity_id?: string;
  verb?: string;
  reason?: string;
  phase_name?: string;
  decision_id?: string;
  function?: string;
  // Used by rocketRegistry to compute target city
  target_city_id?: string;
}

/** A rocket as managed by rocketRegistry. */
export interface Rocket {
  id: string; // unique
  workflow_id: string;
  city_id: string;
  label: string;
  /** Source moon position [x,y,z] or function key (resolved each frame). */
  origin_workflow_id: string;
  /** State machine */
  phase: "outbound" | "parked" | "returning" | "done";
  dispatched_at: number; // ms
  parked_at?: number; // ms
  completed_at?: number; // ms
  returned_at?: number; // ms
  /** For Entities mode beam */
  is_write?: boolean;
  is_read?: boolean;
  is_exception?: boolean;
}

/** A trail sample emitted on rocket completion. */
export interface TrailSample {
  from: [number, number, number];
  to: [number, number, number];
  emitted_at: number; // ms
  color: string;
}

/** Endpoints we hit. */
export const ENDPOINTS = {
  inFlight: "/api/workflows/index/inflight".replace("inflight", "in-flight"),
  personas: "/api/personas/index/state",
  functions: "/api/functions",
  cities: "/api/cities",
  citiesAffinity: "/api/cities/affinity",
  workflowTimeline: (id: string) => `/api/workflows/index/timeline/${id}`,
  injectBurst: (n: number) => `/api/simulator/inject-burst?n=${n}`,
  seedKpis: "/api/simulator/seed-kpis",
  observatorySse: "/api/blueprint/observatory/stream",
} as const;

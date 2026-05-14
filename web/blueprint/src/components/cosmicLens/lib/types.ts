/**
 * Cosmic Lens v2 — Shared types.
 */

export type CosmicMode = "capabilities" | "entities";

export interface PersonaHierarchyNode {
  role: string;
  manages: PersonaHierarchyNode[];
}

export interface FunctionMeta {
  /** Backend uses `name` field. Alias `key` for compat across components. */
  name?: string;
  key?: string; // alias - some surfaces use `key`
  label?: string;
  display?: string; // backend display name
  family?: string;
  /** Backend exposes `ownsDomains` listing workflow_type strings owned by this function. */
  ownsDomains?: string[];
  domains?: string[];
  /** Backend (`/api/functions`) returns the function's persona-leadership tree.
   *  The root node's role identifies the senior persona for the function and is
   *  used by FunctionPlanets to pick a per-persona planet hue. */
  personaHierarchy?: PersonaHierarchyNode;
}

export interface CityMeta {
  id: string;
  kind: string; // mcp | skill | python | validator | persona | entity_type
  label: string;
  category?: string; // optional grouping label
  count?: number;
  recent_activity_per_min?: number;
  active?: boolean;
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

export interface EntityRow {
  id: string;
  kind?: string;
  source_workflows?: string[];
  last_seen_at?: string | number | null;
  first_seen_at?: string | number | null;
  decided_at?: string | number | null;
  [key: string]: unknown;
}

export interface EntityLink {
  rel: string;
  partner_kind?: string;
  count?: number;
  node?: EntityRow;
}

export interface AffinityResponse {
  kind?: string;
  rels?: Array<{ rel: string; partner_kind: string; count: number }>;
}

export interface PulseSnapshot {
  total: number;
  growth_60s: number;
  decisions_per_min: number;
  links_per_min: number;
  cross_domain_top: Array<{
    id: string;
    kind: string;
    workflow_count: number;
    workflow_types_count: number;
  }>;
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
  // Fields carried by `durable.executor.invoked` events. Required so
  // Rockets can dispatch on stage=start and pick the right capability city.
  stage?: string; // "start" | "complete"
  skill?: string;
  tool?: string;
  executor_type?: string; // "tool" | "skill" | "validator" | "agent" | "deterministic"
  // Used by rocketRegistry to compute target city
  target_city_id?: string;
}

/** A rocket as managed by rocketRegistry — one per in-flight workflow. */
export interface Rocket {
  /** Equal to workflow_id (one rocket per workflow). */
  id: string;
  workflow_id: string;
  origin_workflow_id: string;
  /** Rocket lifecycle phase. */
  phase: "spawning" | "travelling" | "idle" | "returning" | "burst" | "done";
  /** Body color (hex string), set on spawn from function family. */
  color: string;
  /** Last city the rocket parked at (or null until first travel). */
  current_city_id: string | null;
  /** Travel destination while phase === "travelling". */
  target_city_id: string | null;
  /** Most recent rocket position used as the start point of the next leg. */
  current_pos: [number, number, number];
  /** Travel start position captured when "travelling" begins. */
  travel_from: [number, number, number] | null;
  /** Travel target position captured when "travelling" begins. */
  travel_to: [number, number, number] | null;
  /** Wallclock ms when the current phase started. */
  phase_started_at: number;
  /** Wallclock ms when the workflow first spawned. */
  spawned_at: number;
  /** Set when the workflow has an active_exception_id (drives wounded tint). */
  is_wounded: boolean;
  /** Most recent flash type that drove a travel — used for label. */
  last_event_type?: string;
  /** Last short label (e.g. tool/skill/persona) — used for hover affordance. */
  last_label?: string;
  /** For Entities mode visual cues on the trail. */
  is_write?: boolean;
  is_read?: boolean;
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
  inFlight: "/api/workflows/index/in-flight",
  personas: "/api/personas/index/state",
  functions: "/api/functions",
  cities: "/api/cities",
  citiesAffinity: "/api/cities/affinity",
  workflowTimeline: (id: string) => `/api/workflows/index/timeline/${id}`,
  injectBurst: (n: number) => `/api/simulator/inject-burst?n=${n}`,
  seedKpis: "/api/simulator/seed-kpis",
  observatorySse: "/api/blueprint/stream",
} as const;

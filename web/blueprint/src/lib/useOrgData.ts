/**
 * The Org Building (IP3, TASK-012; IP4, TASK-018+TASK-025) — steady-state
 * data poller + animation queue + cross-function beam tracker.
 *
 * Polls the three REST surfaces the static backbone needs every 5s:
 *   GET /api/functions          — function registry + KPI declarations
 *   GET /api/entities/_stats    — per-kind entity counts (Person, Org, …)
 *   GET /api/cadences           — cadence schedules + next_run_at
 *
 * Returns the latest snapshot alongside a coarse status flag so the
 * page-level status pill can degrade gracefully when the backend goes
 * away mid-session.
 *
 * In addition (chunk 2): exposes `useOrgAnimations` which subscribes to
 * the SSE stream, dispatches translated entries into a useReducer-managed
 * queue, and polls /api/entities/_stats every 15s to keep cross-function
 * beams alive.
 */
import { useEffect, useMemo, useReducer, useRef, useState } from "react";
import type { Dispatch } from "react";

import {
  animReducer,
  initialAnimState,
} from "./animationQueue";
import type { AnimEntry } from "./animationQueue";
import { COLORS, PREFIX_TO_WORKFLOW_TYPE, translateEvent } from "./orgEvents";
import type { LayerFlags } from "./layerToggles";
import { useObservatory } from "./useObservatory";
import type { ObservatoryEvent } from "./types";

export interface OrgFunction {
  name: string;
  display: string;
  operatorSurface: string;
  ownsDomains: string[];
  ambientAgents: string[];
  kpis: string[];
  personaHierarchy: { role: string; manages: unknown[] };
}

export interface EntityStats {
  counts: Record<string, number>;
  hot?: HotEntity[];
  recentLinks?: unknown[];
}

/** Hot-entity summary returned by /api/entities/_stats.hot. */
export interface HotEntity {
  entity_id: string;
  kind: string;
  source_workflows: string[]; // workflow_type values
  upserts?: number;
  updated_at?: number;
}

export interface Cadence {
  name: string;
  schedule: string;
  fires_ambient_agent: string | null;
  next_run_at: string | null;
}

export type OrgDataStatus = "loading" | "ready" | "error";

export interface OrgDataSnapshot {
  functions: OrgFunction[];
  entityCounts: Record<string, number>;
  cadences: Cadence[];
  status: OrgDataStatus;
  /** Hot entities (last poll) — used for cross-function beam computation. */
  hotEntities: HotEntity[];
  /** workflow_type → function key (e.g. "vendor_kyc" → "finance"). */
  functionByWorkflowType: Map<string, string>;
  /** function name → OrgFunction (memoised for handlers). */
  functionByName: Map<string, OrgFunction>;
}

const POLL_MS = 5000;

async function fetchJson<T>(url: string): Promise<T> {
  const r = await fetch(url, { headers: { Accept: "application/json" } });
  if (!r.ok) throw new Error(`${url} -> ${r.status}`);
  return (await r.json()) as T;
}

export function useOrgData(): OrgDataSnapshot {
  const [raw, setRaw] = useState<{
    functions: OrgFunction[];
    entityCounts: Record<string, number>;
    cadences: Cadence[];
    status: OrgDataStatus;
    hotEntities: HotEntity[];
  }>({
    functions: [],
    entityCounts: {},
    cadences: [],
    status: "loading",
    hotEntities: [],
  });

  useEffect(() => {
    let cancelled = false;
    let timer: number | undefined;

    async function tick() {
      try {
        const [functions, stats, cadences] = await Promise.all([
          fetchJson<OrgFunction[]>("/api/functions"),
          fetchJson<EntityStats>("/api/entities/_stats").catch(
            // The entity plane is gated behind ENTITY_PLANE_ENABLED; when
            // disabled the route 404s. Treat that as "no entities yet"
            // rather than tipping the whole snapshot into an error state.
            () => ({ counts: {} }) as EntityStats,
          ),
          fetchJson<Cadence[]>("/api/cadences").catch(() => [] as Cadence[]),
        ]);
        if (cancelled) return;
        // Normalise hot entities: the Kuzu node label lives at
        // `_label`, while the `kind` attribute is a free-form vendor /
        // employee / etc. discriminator. The frontend's vault + beam
        // logic key on the schema kind, so prefer `_label` when present.
        const rawHot = (stats.hot ?? []) as Array<HotEntity & { _label?: string }>;
        const normalisedHot: HotEntity[] = rawHot.map((e) => ({
          ...e,
          kind: e._label ?? e.kind,
        }));
        setRaw({
          functions,
          entityCounts: stats.counts ?? {},
          cadences,
          status: "ready",
          hotEntities: normalisedHot,
        });
      } catch {
        if (!cancelled) {
          setRaw((cur) => ({ ...cur, status: "error" }));
        }
      } finally {
        if (!cancelled) {
          timer = window.setTimeout(tick, POLL_MS);
        }
      }
    }

    tick();
    return () => {
      cancelled = true;
      if (timer) window.clearTimeout(timer);
    };
  }, []);

  // Memoised lookup maps. Built once per functions[] change so animation
  // handlers don't pay the cost on every event tick.
  const functionByWorkflowType = useMemo(
    () => buildWorkflowTypeIndex(raw.functions),
    [raw.functions],
  );
  const functionByName = useMemo(
    () => new Map(raw.functions.map((f) => [f.name, f])),
    [raw.functions],
  );

  return {
    ...raw,
    functionByWorkflowType,
    functionByName,
  };
}

/** Build the workflow_type → function lookup from functions[].owns_domains[].
 *  owns_domains entries may be either domain names or workflow_type
 *  slugs depending on the upstream registry; we index on the raw
 *  string and let resolveFunction() try multiple fallbacks. */
export function buildWorkflowTypeIndex(
  functions: OrgFunction[],
): Map<string, string> {
  const m = new Map<string, string>();
  for (const fn of functions) {
    for (const wt of fn.ownsDomains) {
      if (!m.has(wt)) m.set(wt, fn.name);
    }
  }
  return m;
}

/**
 * Per-function KPI snapshot poller. Backed by /api/functions/{name}/kpis-latest
 * (added in IP1, TASK-003). One hook instance per floor; each polls
 * independently every 5s.
 */
export interface KpiLatest {
  metrics: Record<string, { value: number; period: string; captured_at: number }>;
  since: number | null;
}

export function useFunctionKpis(name: string): KpiLatest {
  const [data, setData] = useState<KpiLatest>({ metrics: {}, since: null });

  useEffect(() => {
    let cancelled = false;
    let timer: number | undefined;

    async function tick() {
      try {
        const r = await fetchJson<KpiLatest>(
          `/api/functions/${encodeURIComponent(name)}/kpis-latest`,
        );
        if (!cancelled) setData(r);
      } catch {
        // Leave the previous snapshot in place; the floor will keep
        // showing the last-known values until the next successful poll.
      } finally {
        if (!cancelled) timer = window.setTimeout(tick, POLL_MS);
      }
    }

    tick();
    return () => {
      cancelled = true;
      if (timer) window.clearTimeout(timer);
    };
  }, [name]);

  return data;
}

/**
 * Cross-function beam description (TASK-025).
 *
 * Computed by joining hot entities' source_workflows with the
 * functionByWorkflowType lookup. Two-or-more distinct functions
 * touching a single entity create a beam between every pair.
 *
 * The beam fades after `staleAfterMs` of no fresh upserts (default 30s).
 */
export interface CrossFunctionBeam {
  fromFn: string;
  toFn: string;
  /** Number of cross-cutting hot entities driving this beam. */
  weight: number;
  /** Last upsert timestamp seen for any of the contributing entities. */
  lastSeen: number;
}

export function computeCrossFunctionBeams(
  hot: HotEntity[],
  functionByWorkflowType: Map<string, string>,
  now = Date.now(),
  staleAfterMs = 30_000,
): CrossFunctionBeam[] {
  const pairs = new Map<string, CrossFunctionBeam>();
  for (const ent of hot) {
    const fns = new Set<string>();
    for (const wid of ent.source_workflows ?? []) {
      // source_workflows holds workflow_IDs (e.g. "VKY-0001"). Map the
      // prefix to a workflow_type then to a function. Falls back to the
      // raw value in case future projections store workflow_type strings.
      let fn = functionByWorkflowType.get(wid);
      if (!fn) {
        const m = wid.match(/^([A-Z]+)-/);
        const wt = m ? PREFIX_TO_WORKFLOW_TYPE[m[1]] : null;
        if (wt) fn = functionByWorkflowType.get(wt) ?? undefined;
      }
      if (fn) fns.add(fn);
    }
    if (fns.size < 2) continue;
    const ts = (ent.updated_at ?? 0) * 1000;
    if (ts && now - ts > staleAfterMs) continue;
    const sorted = [...fns].sort();
    for (let i = 0; i < sorted.length; i += 1) {
      for (let j = i + 1; j < sorted.length; j += 1) {
        const key = `${sorted[i]}::${sorted[j]}`;
        const cur = pairs.get(key);
        if (cur) {
          cur.weight += 1;
          cur.lastSeen = Math.max(cur.lastSeen, ts || cur.lastSeen);
        } else {
          pairs.set(key, {
            fromFn: sorted[i],
            toFn: sorted[j],
            weight: 1,
            lastSeen: ts || now,
          });
        }
      }
    }
  }
  return [...pairs.values()];
}

/**
 * Animation orchestration hook (TASK-018..-024).
 *
 * Owns the AnimEntry queue. Subscribes to the shared SSE stream via
 * useObservatory, translates each event into an AnimEntry, and
 * dispatches it into the reducer.
 *
 * The visual layer ticks the queue forward every frame (consumer holds
 * a ref to the dispatch + state via the returned tuple).
 */
export function useOrgAnimations(
  snap: OrgDataSnapshot,
  layers: LayerFlags,
): {
  entries: AnimEntry[];
  dispatch: Dispatch<{ type: "tick"; dt: number }>;
  beams: CrossFunctionBeam[];
} {
  const [state, dispatch] = useReducer(animReducer, initialAnimState);
  const layersRef = useRef(layers);
  layersRef.current = layers;
  const ctxRef = useRef({
    functionByWorkflowType: snap.functionByWorkflowType,
    functionByName: snap.functionByName,
  });
  ctxRef.current = {
    functionByWorkflowType: snap.functionByWorkflowType,
    functionByName: snap.functionByName,
  };

  // SSE handler. Translation is layer-aware so a disabled layer never
  // accumulates queue entries that get dropped at render time.
  useObservatory({
    bufferSize: 1,
    onEvent: (event: ObservatoryEvent) => {
      const entry = translateEvent(event, {
        ...ctxRef.current,
        layers: layersRef.current,
      });
      if (entry) dispatch({ type: "enqueue", entry } as never);
    },
  });

  // Cross-function beams: derive from the latest poll. Re-emitted when
  // hot entities or the function index change. Conceptually persistent
  // (no time advancement needed) so we surface them as a separate list
  // rather than dropping them through the AnimEntry pool.
  const beams = useMemo(() => {
    if (!layers.crossFunctionBeams) return [];
    return computeCrossFunctionBeams(snap.hotEntities, snap.functionByWorkflowType);
  }, [snap.hotEntities, snap.functionByWorkflowType, layers.crossFunctionBeams]);

  return {
    entries: state.entries,
    dispatch: dispatch as Dispatch<{ type: "tick"; dt: number }>,
    beams,
  };
}

// Re-export so consumers can grab palette without a second import.
export { COLORS as ANIM_COLORS };

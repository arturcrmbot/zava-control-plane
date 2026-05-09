/**
 * The Org Building (IP3, TASK-012) — steady-state data poller.
 *
 * Polls the three REST surfaces the static backbone needs every 5s:
 *   GET /api/functions          — function registry + KPI declarations
 *   GET /api/entities/_stats    — per-kind entity counts (Person, Org, …)
 *   GET /api/cadences           — cadence schedules + next_run_at
 *
 * Returns the latest snapshot alongside a coarse status flag so the
 * page-level status pill can degrade gracefully when the backend goes
 * away mid-session.
 */
import { useEffect, useState } from "react";

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
  hot?: unknown[];
  recentLinks?: unknown[];
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
}

const POLL_MS = 5000;

async function fetchJson<T>(url: string): Promise<T> {
  const r = await fetch(url, { headers: { Accept: "application/json" } });
  if (!r.ok) throw new Error(`${url} -> ${r.status}`);
  return (await r.json()) as T;
}

export function useOrgData(): OrgDataSnapshot {
  const [snap, setSnap] = useState<OrgDataSnapshot>({
    functions: [],
    entityCounts: {},
    cadences: [],
    status: "loading",
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
        setSnap({
          functions,
          entityCounts: stats.counts ?? {},
          cadences,
          status: "ready",
        });
      } catch {
        if (!cancelled) {
          setSnap((cur) => ({ ...cur, status: "error" }));
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

  return snap;
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

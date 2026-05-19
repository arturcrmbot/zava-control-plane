// web/client/hooks/usePersonaDecisions.ts
//
// Pull persona-emitted Decision nodes out of the entity graph. Backed by
// `GET /api/entities?kind=Decision&limit=...`, which returns Kuzu rows.
//
// "Recent decisions" on the Dashboard merges these into the same surface
// as operator clicks (`useResolutionStore`) so the UI shows the full
// decision stream — both human and persona — without favouring either.
//
// Polled (no SSE for Decision nodes today). Default refresh every 20s,
// only keeps the most recent `limit` rows. Generic across workflow types
// — no hiring-specific filtering.
import { useEffect, useState } from "react";

export interface PersonaDecision {
  id: string;
  workflowId: string;
  phase: string;
  personaRole: string;
  verdict: string;
  reason: string;
  decidedAtSec: number;
}

interface DecisionRow {
  id?: string;
  workflow_id?: string;
  phase?: string;
  persona_role?: string;
  verdict?: string;
  reason?: string;
  decided_at?: string;
}

function parseTimestamp(raw: string | undefined): number {
  if (!raw) return 0;
  const t = Date.parse(raw);
  if (Number.isFinite(t)) return t / 1000;
  return 0;
}

function normalize(row: DecisionRow): PersonaDecision | null {
  if (!row.id) return null;
  return {
    id: String(row.id),
    workflowId: String(row.workflow_id ?? ""),
    phase: String(row.phase ?? ""),
    personaRole: String(row.persona_role ?? ""),
    verdict: String(row.verdict ?? ""),
    reason: String(row.reason ?? ""),
    decidedAtSec: parseTimestamp(row.decided_at),
  };
}

export function usePersonaDecisions(opts?: { limit?: number; refreshMs?: number }) {
  const limit = opts?.limit ?? 200;
  const refreshMs = opts?.refreshMs ?? 20_000;
  const [items, setItems] = useState<PersonaDecision[]>([]);

  useEffect(() => {
    if (typeof fetch !== "function") return;
    let cancelled = false;
    async function run() {
      try {
        const r = await fetch(`/api/entities?kind=Decision&order=recent&limit=${limit}`);
        if (!r.ok) return;
        const body = (await r.json()) as DecisionRow[];
        if (cancelled) return;
        const parsed = body
          .map(normalize)
          .filter((x): x is PersonaDecision => x !== null)
          .sort((a, b) => b.decidedAtSec - a.decidedAtSec);
        setItems(parsed);
      } catch {
        /* swallow — Dashboard tolerates an empty list */
      }
    }
    run();
    const iv = window.setInterval(run, refreshMs);
    return () => {
      cancelled = true;
      window.clearInterval(iv);
    };
  }, [limit, refreshMs]);

  return items;
}

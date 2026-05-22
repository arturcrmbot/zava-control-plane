// web/client/hooks/useMemoryQueries.ts
//
// React hooks that back the Fleet UI Memory page (/memory).
//
// Most hooks:
//   1. Poll the relevant /api/memory endpoint via useThrottledFetch.
//   2. Subscribe to /api/stream/fleet via useSSE; refresh on dream.* events.
//
// Mirrors useWorkflows / useExceptions: same throttled-fetch + SSE pattern,
// same connection pool discipline.
import { useCallback, useEffect, useState } from "react";
import { useSSE } from "./useSSE";
import { useThrottledFetch } from "./useThrottledFetch";

export interface ActiveLesson {
  id: string;
  body: string;
  domain: string | null;
  persona_role: string | null;
  promoted_at: string | null;
  rubric_score_delta: number | null;
  experiment_n: number | null;
  proposed_by: string | null;
  status: string | null;
}

export interface DreamPassRow {
  id: string;
  domain: string;
  skill_version: string | null;
  started_at: string | null;
  completed_at: string | null;
  status: string | null;
  candidates_proposed: number | null;
  candidates_promoted: number | null;
}

export interface WorkingNote {
  id: string;
  workflow_id: string | null;
  agent_skill: string | null;
  kind: string | null;
  body: string | null;
  captured_at: string | null;
  consumed_by_dream_pass: string | null;
}

export interface MemoryRecord {
  id?: string;
  memory: string;
  metadata?: {
    agent_skill?: string;
  };
}

interface Envelope<T> { items: T[] }

interface MemoriesEnvelope {
  memories: MemoryRecord[];
  count: number;
}

function useMemoryEndpoint<T>(url: string, refreshOnTypes: readonly string[]): T[] {
  const [items, setItems] = useState<T[]>([]);
  const refresh = useThrottledFetch<Envelope<T>>(
    url,
    (body) => setItems(body?.items ?? []),
    750,
  );
  useEffect(() => { refresh(); }, [refresh]);
  // Comma-join the refresh-on types for a stable useCallback dep — array
  // identity changes on every render even when contents don't.
  const refreshOnKey = refreshOnTypes.join(",");
  useSSE<{ type: string }>(
    "/api/stream/fleet",
    useCallback((e) => {
      if (refreshOnTypes.includes(e.type)) refresh();
      // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [refresh, refreshOnKey]),
  );
  return items;
}


export function useActiveLessons(domain?: string): ActiveLesson[] {
  const url = domain
    ? `/api/memory/lessons/active?domain=${encodeURIComponent(domain)}`
    : "/api/memory/lessons/active";
  return useMemoryEndpoint<ActiveLesson>(url, ["dream.lesson.promoted"]);
}

export function useMemories(domain: string): { memories: MemoryRecord[]; count: number; isLoading: boolean } {
  const [memories, setMemories] = useState<MemoryRecord[]>([]);
  const [count, setCount] = useState(0);
  const [isLoading, setIsLoading] = useState(true);
  const url = `/api/memory/v2/memories?domain=${encodeURIComponent(domain)}`;

  const refresh = useCallback(async () => {
    setIsLoading(true);
    try {
      const r = await fetch(url);
      if (!r.ok) {
        setMemories([]);
        setCount(0);
        return;
      }
      const body = (await r.json()) as Partial<MemoriesEnvelope>;
      setMemories(body.memories ?? []);
      setCount(body.count ?? body.memories?.length ?? 0);
    } catch {
      setMemories([]);
      setCount(0);
    } finally {
      setIsLoading(false);
    }
  }, [url]);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  useSSE<{ type: string }>(
    "/api/stream/fleet",
    useCallback((e) => {
      if (e.type === "dream.pass.finished" || e.type === "dream.lesson.promoted") {
        void refresh();
      }
    }, [refresh]),
  );

  return { memories, count, isLoading };
}

export function useDreamPassesRecent(limit = 20, domain?: string): DreamPassRow[] {
  const url = domain
    ? `/api/memory/dream-passes/recent?limit=${limit}&domain=${encodeURIComponent(domain)}`
    : `/api/memory/dream-passes/recent?limit=${limit}`;
  return useMemoryEndpoint<DreamPassRow>(
    url,
    ["dream.pass.started", "dream.pass.finished"],
  );
}

export function useWorkingNotes(limit = 50, agentSkill?: string): WorkingNote[] {
  const url = agentSkill
    ? `/api/memory/working-notes?agent_skill=${encodeURIComponent(agentSkill)}&limit=${limit}`
    : `/api/memory/working-notes?limit=${limit}`;
  // No explicit working-note event today; refresh on any pass-finished
  // so consumed_by_dream_pass markers update.
  return useMemoryEndpoint<WorkingNote>(url, ["dream.pass.finished"]);
}

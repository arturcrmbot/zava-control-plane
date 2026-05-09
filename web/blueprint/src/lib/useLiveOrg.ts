/**
 * useLiveOrg — single source of truth for the Glass Tower.
 *
 * Polls the three v2 ops endpoints every 3s + subscribes to the SSE stream.
 * Maintains:
 *
 *   - inFlight       : in-flight workflows (id, type, function, phase, age, actor)
 *   - personas       : per-persona state (idle/working/recently_decided)
 *   - functions      : function registry (name → owns_domains, kpis, persona hierarchy)
 *   - vital signs    : top-bar counts (in_flight, awaiting, decided_today, exceptions)
 *   - decisions      : recent (last 60s) decisions for the lobby pool
 *   - flashes        : transient per-persona / per-workflow flash signals from SSE
 *                      (consumed by the scene's useFrame loops; auto-decay)
 *
 * Single hook so the rest of the scene mounts as a pure render of `useLiveOrg`'s
 * snapshot. Animation primitives consume flashes via refs to avoid re-render
 * thrash.
 */
import { useEffect, useRef, useState } from "react";
import { useObservatory } from "./useObservatory";

const POLL_MS = 3000;

export interface InFlightWorkflow {
  id: string;
  workflow_type: string;
  function: string | null;
  status: "in_progress" | "awaiting_hitl";
  phase: string;
  created_at: number;
  age_s: number;
  sla_pct: number;
  active_exception_id?: string | null;
  last_actor?: { kind: string; name: string; at: number } | null;
}

export interface PersonaRow {
  role: string;
  state: "idle" | "working" | "recently_decided";
  auto_close: boolean;
  pending_count: number;
  pending: Array<{
    workflow_id: string;
    workflow_type: string;
    phase: string;
    age_s: number;
  }>;
  last_decision: {
    ts: number;
    workflow_id: string;
    verdict: string | null;
    phase: string | null;
    reason: string | null;
  } | null;
  last_decision_age_s: number | null;
}

export interface FunctionSpec {
  name: string;
  display: string;
  ownsDomains: string[];
  ambientAgents: string[];
  kpis: string[];
  personaHierarchy: { role: string; manages: unknown[] };
}

export interface VitalSigns {
  in_flight: number;
  awaiting: number;
  decided_today: number;
  exceptions: number;
  sla_breaching: number;
}

export interface RecentDecision {
  workflow_id: string;
  function: string | null;
  persona: string;
  verdict: string | null;
  phase: string | null;
  ts: number;
}

export interface LiveOrgSnapshot {
  status: "loading" | "ready" | "error";
  inFlight: InFlightWorkflow[];
  personas: PersonaRow[];
  functions: FunctionSpec[];
  functionByName: Map<string, FunctionSpec>;
  vital: VitalSigns;
  recentDecisions: RecentDecision[];
  flashesRef: React.MutableRefObject<FlashSet>;
}

export interface FlashSet {
  /** Per-persona role flash payload + decay deadline ms. */
  personaFlash: Map<string, { kind: "thinking" | "decided" | "verdict_approve" | "verdict_reject"; until: number }>;
  /** Per-workflow flash on a specific event class. */
  workflowFlash: Map<string, { kind: "started" | "completed" | "exception"; until: number }>;
  /** Lobby decision-pool fly-ins: pop and consume. */
  pendingDecisions: Array<{
    id: string;
    workflow_id: string;
    function: string | null;
    persona: string | null;
    verdict: string | null;
    ts: number;
  }>;
  /** Recently-fired tool calls per workflow_id, used as floating labels. */
  toolFlash: Map<string, { tool: string; until: number }>;
}

const PREFIX_TO_WORKFLOW_TYPE: Record<string, string> = {
  EXP: "expense-claim",
  HIRE: "hiring",
  TRV: "travel-preapproval",
  TRVL: "travel-preapproval",
  VKY: "vendor-kyc",
  ONB: "employee-onboarding",
  ITAR: "it-access-request",
  CRN: "contract-renewal",
  PRR: "perf-review",
  API: "ap-invoice",
  POW: "purchase-order",
  CRW: "contract-review",
  DPI: "privacy-dpia",
  TFX: "treasury-fx",
  CMP: "creative-campaign",
  H2P: "hire-to-productive",
  VRP: "vendor-risk-to-pay",
  L2C: "lead-to-cash",
  FYC: "fy-close",
  BRD: "board-prep",
};

function workflowIdToType(wid: string | null | undefined): string | null {
  if (!wid) return null;
  const m = wid.match(/^([A-Z]+)-/);
  if (!m) return null;
  return PREFIX_TO_WORKFLOW_TYPE[m[1]] ?? null;
}

function functionForWorkflowType(
  wt: string | null | undefined,
  index: Map<string, string>,
): string | null {
  if (!wt) return null;
  return index.get(wt) ?? null;
}

async function fetchJson<T>(url: string): Promise<T> {
  const r = await fetch(url, { headers: { Accept: "application/json" } });
  if (!r.ok) throw new Error(`${url} -> ${r.status}`);
  return (await r.json()) as T;
}

export function useLiveOrg(): LiveOrgSnapshot {
  const [snap, setSnap] = useState<{
    status: "loading" | "ready" | "error";
    inFlight: InFlightWorkflow[];
    personas: PersonaRow[];
    functions: FunctionSpec[];
    recentDecisions: RecentDecision[];
  }>({
    status: "loading",
    inFlight: [],
    personas: [],
    functions: [],
    recentDecisions: [],
  });

  const flashesRef = useRef<FlashSet>({
    personaFlash: new Map(),
    workflowFlash: new Map(),
    pendingDecisions: [],
    toolFlash: new Map(),
  });

  // Build workflow_type → function key map from functions[].owns_domains[].
  const functionByName = new Map(snap.functions.map((f) => [f.name, f]));
  const wtToFn = new Map<string, string>();
  for (const f of snap.functions) {
    for (const d of f.ownsDomains ?? []) wtToFn.set(d, f.name);
  }

  // ---- Polling ----------------------------------------------------------
  useEffect(() => {
    let cancelled = false;
    let timer: number | undefined;

    async function tick() {
      try {
        const [inFlight, personas, functions] = await Promise.all([
          fetchJson<InFlightWorkflow[]>("/api/workflows/index/in-flight").catch(() => [] as InFlightWorkflow[]),
          fetchJson<PersonaRow[]>("/api/personas/index/state").catch(() => [] as PersonaRow[]),
          fetchJson<FunctionSpec[]>("/api/functions").catch(() => [] as FunctionSpec[]),
        ]);
        if (cancelled) return;
        // Decisions in the last 60s, derived from personas.last_decision.
        const now = Date.now() / 1000;
        const recentDecisions: RecentDecision[] = [];
        for (const p of personas) {
          if (!p.last_decision) continue;
          if (!p.last_decision.ts) continue;
          if (now - p.last_decision.ts > 120) continue;
          recentDecisions.push({
            workflow_id: p.last_decision.workflow_id,
            function: functionForWorkflowType(workflowIdToType(p.last_decision.workflow_id), wtToFn),
            persona: p.role,
            verdict: p.last_decision.verdict,
            phase: p.last_decision.phase,
            ts: p.last_decision.ts,
          });
        }
        recentDecisions.sort((a, b) => b.ts - a.ts);
        setSnap({ status: "ready", inFlight, personas, functions, recentDecisions });
      } catch {
        if (!cancelled) setSnap((cur) => ({ ...cur, status: "error" }));
      } finally {
        if (!cancelled) timer = window.setTimeout(tick, POLL_MS);
      }
    }
    tick();
    return () => {
      cancelled = true;
      if (timer) window.clearTimeout(timer);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // ---- SSE → flashes ----------------------------------------------------
  useObservatory({
    bufferSize: 1,
    onEvent: (event) => {
      const flashes = flashesRef.current;
      const now = performance.now();
      switch (event.type) {
        case "persona.thinking": {
          const role = (event as unknown as { persona?: string }).persona;
          if (role) flashes.personaFlash.set(role, { kind: "thinking", until: now + 8000 });
          break;
        }
        case "persona.decided": {
          const role = (event as unknown as { persona?: string }).persona;
          const verdict = (event as unknown as { verdict?: string }).verdict;
          if (role) {
            flashes.personaFlash.set(role, {
              kind: verdict === "reject" || verdict === "deny" ? "verdict_reject" : "verdict_approve",
              until: now + 1500,
            });
          }
          if (event.workflow_id) {
            const fnKey = functionForWorkflowType(workflowIdToType(event.workflow_id), wtToFn);
            flashes.pendingDecisions.push({
              id: `${event.workflow_id}-${event.ts ?? Date.now()}-${Math.random().toString(36).slice(2, 6)}`,
              workflow_id: event.workflow_id,
              function: fnKey,
              persona: role ?? null,
              verdict: verdict ?? null,
              ts: event.ts ?? Date.now() / 1000,
            });
          }
          break;
        }
        case "workflow.started":
        case "durable.workflow.started":
          if (event.workflow_id) flashes.workflowFlash.set(event.workflow_id, { kind: "started", until: now + 2000 });
          break;
        case "durable.workflow.completed":
        case "workflow.resolved":
          if (event.workflow_id) flashes.workflowFlash.set(event.workflow_id, { kind: "completed", until: now + 2500 });
          break;
        case "workflow.exception.detected":
          if (event.workflow_id) flashes.workflowFlash.set(event.workflow_id, { kind: "exception", until: now + 4000 });
          break;
        case "tool.invoked":
        case "durable.executor.invoked": {
          const tool = event.tool ?? event.skill;
          if (event.workflow_id && tool) {
            flashes.toolFlash.set(event.workflow_id, { tool, until: now + 1800 });
          }
          break;
        }
      }
    },
  });

  // ---- Vital signs ------------------------------------------------------
  const vital: VitalSigns = {
    in_flight: snap.inFlight.length,
    awaiting: snap.inFlight.filter((w) => w.status === "awaiting_hitl").length,
    decided_today: snap.recentDecisions.length, // approximation from persona.last_decision recentness
    exceptions: snap.inFlight.filter((w) => !!w.active_exception_id).length,
    sla_breaching: snap.inFlight.filter((w) => w.sla_pct >= 0.9).length,
  };

  return {
    status: snap.status,
    inFlight: snap.inFlight,
    personas: snap.personas,
    functions: snap.functions,
    functionByName,
    vital,
    recentDecisions: snap.recentDecisions,
    flashesRef,
  };
}

/**
 * The Org Building (IP8, TASK-042..-048) — workflow detail overlay.
 *
 * Mounted at zoom-level 0. Reads:
 *   GET /api/workflows/{id}             — workflow shape, phases, mcpCalls
 *   GET /api/entities/touched-by/{id}   — entities the workflow touches
 *
 * No new backend endpoint is required for the audit tail (TASK-048) —
 * we filter the SSE event tail to events whose `workflow_id` matches.
 *
 * Renders a stack of panels:
 *   - Phase timeline (intake → classify → … with kind / state badges)
 *   - MCP calls (live, currently-firing tool calls)
 *   - HITL gate (when workflow.status === 'awaiting_hitl')
 *   - Entities touched (with cross-function badge)
 *   - Decisions so far (from workflow.payload.decisions)
 *   - Audit tail (chronological events for this workflow_id)
 *
 * Implementation: DOM overlay (matches DepartmentInterior). The 3D
 * scene continues to render behind for spatial continuity.
 */
import { useEffect, useMemo, useState } from "react";

import { useObservatory } from "../../lib/useObservatory";
import { COLORS } from "../../lib/orgEvents";
import { useOrgData } from "../../lib/useOrgData";
import type { ObservatoryEvent } from "../../lib/types";

interface PhaseRow {
  name: string;
  kind?: string;
  status?: string;
  startedAt?: number | null;
  endedAt?: number | null;
}

interface McpCallRow {
  toolCallId?: string;
  tool?: string;
  skill?: string;
  startedAt?: number;
  endedAt?: number | null;
}

interface DecisionRow {
  id?: string | null;
  persona_role?: string | null;
  verdict?: string | null;
  reason?: string | null;
  decided_at?: number | null;
}

interface WorkflowDetail {
  workflow: {
    id: string;
    type: string;
    status: string;
    current_phase?: string;
    payload?: { decisions?: DecisionRow[]; gates?: unknown[] } & Record<string, unknown>;
    active_exception_id?: string | null;
  };
  phases: PhaseRow[];
  mcpCalls?: McpCallRow[];
  activeException?: {
    id: string;
    persona?: string;
    auto_close_at?: number | null;
  } | null;
}

interface EntityRow {
  id?: string;
  entity_id?: string;
  kind?: string;
  source_workflows?: string[];
  [k: string]: unknown;
}

interface Props {
  id: string;
  onClose: () => void;
}

/** Cross-function check: does this entity also appear in workflows
 *  owned by other functions? Same logic chunk-2 used for beams. */
export function isCrossFunction(
  entity: EntityRow,
  thisWorkflowType: string | undefined,
  functionByWorkflowType: Map<string, string>,
): boolean {
  if (!thisWorkflowType) return false;
  const thisFn = functionByWorkflowType.get(thisWorkflowType);
  if (!thisFn) return false;
  for (const wt of entity.source_workflows ?? []) {
    const fn = functionByWorkflowType.get(wt);
    if (fn && fn !== thisFn) return true;
  }
  return false;
}

export function WorkflowZoom({ id, onClose }: Props) {
  const snap = useOrgData();
  const [detail, setDetail] = useState<WorkflowDetail | null>(null);
  const [entities, setEntities] = useState<EntityRow[]>([]);
  const [audit, setAudit] = useState<ObservatoryEvent[]>([]);
  const [liveMcp, setLiveMcp] = useState<Record<string, McpCallRow>>({});

  // Workflow detail poll
  useEffect(() => {
    let cancelled = false;
    let timer: number | undefined;
    async function tick() {
      try {
        const r = await fetch(`/api/workflows/${encodeURIComponent(id)}`);
        if (r.ok && !cancelled) setDetail(await r.json());
      } catch {
        /* keep last */
      } finally {
        if (!cancelled) timer = window.setTimeout(tick, 4000);
      }
    }
    tick();
    return () => {
      cancelled = true;
      if (timer) window.clearTimeout(timer);
    };
  }, [id]);

  // Entities-touched poll
  useEffect(() => {
    let cancelled = false;
    let timer: number | undefined;
    async function tick() {
      try {
        const r = await fetch(`/api/entities/touched-by/${encodeURIComponent(id)}`);
        if (r.ok && !cancelled) setEntities(await r.json());
      } catch {
        /* keep last */
      } finally {
        if (!cancelled) timer = window.setTimeout(tick, 6000);
      }
    }
    tick();
    return () => {
      cancelled = true;
      if (timer) window.clearTimeout(timer);
    };
  }, [id]);

  // SSE: audit tail filtered + live MCP call tracker
  useObservatory({
    bufferSize: 1,
    onEvent: (event) => {
      if (event.workflow_id !== id) return;
      setAudit((cur) => [event, ...cur].slice(0, 80));
      if (event.type === "tool.invoked") {
        const key = event.tool ?? `${event.skill ?? ""}:${event.ts}`;
        setLiveMcp((cur) => ({
          ...cur,
          [key]: {
            toolCallId: key,
            tool: event.tool ?? "(tool)",
            skill: event.skill ?? undefined,
            startedAt: event.ts,
            endedAt: null,
          },
        }));
      } else if (
        event.type === "tool.completed" ||
        event.type === "tool.errored"
      ) {
        const key = event.tool ?? `${event.skill ?? ""}:${event.ts}`;
        setLiveMcp((cur) => {
          if (!cur[key]) return cur;
          const next = { ...cur };
          delete next[key];
          return next;
        });
      }
    },
  });

  const workflow = detail?.workflow;
  const decisions = (workflow?.payload?.decisions as DecisionRow[] | undefined) ?? [];

  const decoratedEntities = useMemo(() => {
    return entities.map((e) => ({
      ...e,
      crossFn: isCrossFunction(e, workflow?.type, snap.functionByWorkflowType),
    }));
  }, [entities, workflow?.type, snap.functionByWorkflowType]);

  return (
    <div style={overlayStyle} role="dialog" aria-label={`workflow ${id}`}>
      <header style={headerStyle}>
        <div>
          <div style={{ fontSize: 11, color: "#9aa0a6", letterSpacing: "0.12em" }}>
            WORKFLOW · ZOOM 0
          </div>
          <h2 style={{ margin: "4px 0 0", fontSize: 20, color: "#f5f5f7" }}>
            {workflow?.type ?? "—"} <span style={{ color: "#6b7077", fontSize: 13 }}>{id}</span>
          </h2>
          <div style={{ fontSize: 11, color: "#9aa0a6" }}>
            status: <span style={{ color: "#f5f5f7" }}>{workflow?.status ?? "—"}</span>
            {workflow?.current_phase && (
              <>
                {" · phase: "}
                <span style={{ color: "#f5f5f7" }}>{workflow.current_phase}</span>
              </>
            )}
          </div>
        </div>
        <button type="button" onClick={onClose} style={closeStyle} aria-label="close">
          ✕
        </button>
      </header>

      <div style={layoutStyle}>
        <Panel title="Phase timeline">
          <PhaseTimeline phases={detail?.phases ?? []} currentPhase={workflow?.current_phase} />
        </Panel>

        <Panel title="MCP calls (live)">
          {Object.values(liveMcp).length === 0 ? (
            <Empty>no firing tool calls</Empty>
          ) : (
            Object.values(liveMcp).map((c) => (
              <div key={c.toolCallId} style={mcpRow}>
                <span style={{ color: "#5fb3a8" }}>● </span>
                {c.tool}
                {c.skill && (
                  <span style={{ color: "#9aa0a6" }}> ({c.skill})</span>
                )}
              </div>
            ))
          )}
        </Panel>

        {workflow?.status === "awaiting_hitl" && (
          <Panel title="HITL gate">
            <HitlPanel
              gate={(workflow.payload?.gates as unknown[]) ?? []}
              activeException={detail?.activeException ?? null}
            />
          </Panel>
        )}

        <Panel title={`Entities touched (${decoratedEntities.length})`}>
          {decoratedEntities.length === 0 ? (
            <Empty>none yet</Empty>
          ) : (
            <div style={{ display: "flex", flexWrap: "wrap", gap: 4 }}>
              {decoratedEntities.map((e) => {
                const eid = (e.id ?? e.entity_id ?? "?") as string;
                return (
                  <button
                    key={eid}
                    type="button"
                    onClick={() =>
                      window.dispatchEvent(
                        new CustomEvent("org-building:entity-selected", {
                          detail: { entityId: eid, source: "workflow" },
                        }),
                      )
                    }
                    style={{
                      ...entityChip,
                      borderColor: e.crossFn ? COLORS.beam : "rgba(207,210,214,0.2)",
                    }}
                    title={`${e.kind ?? "?"} · ${eid}`}
                  >
                    {e.kind ?? "?"}: {eid.slice(0, 10)}
                    {e.crossFn && (
                      <span style={{ color: COLORS.beam, marginLeft: 4 }}>↔</span>
                    )}
                  </button>
                );
              })}
            </div>
          )}
        </Panel>

        <Panel title={`Decisions so far (${decisions.length})`}>
          {decisions.length === 0 ? (
            <Empty>no decisions</Empty>
          ) : (
            decisions.map((d, i) => (
              <div key={i} style={decisionRow}>
                <span style={{ color: COLORS.decision }}>⚖ </span>
                {d.verdict ?? "?"}
                {d.persona_role && (
                  <span style={{ color: "#9aa0a6" }}> · {d.persona_role}</span>
                )}
                {d.reason && (
                  <div style={{ fontSize: 10, color: "#9aa0a6" }}>{d.reason}</div>
                )}
              </div>
            ))
          )}
        </Panel>

        <Panel title={`Audit tail (${audit.length})`}>
          {audit.length === 0 ? (
            <Empty>no events captured yet</Empty>
          ) : (
            <div style={{ maxHeight: 220, overflowY: "auto" }}>
              {audit.map((e, i) => (
                <div key={i} style={auditRow}>
                  <span style={{ color: "#9aa0a6", marginRight: 6 }}>
                    {new Date(e.ts * 1000).toLocaleTimeString()}
                  </span>
                  {e.type}
                </div>
              ))}
            </div>
          )}
        </Panel>
      </div>
    </div>
  );
}

/* ------------------------------------------------------------------ */

function PhaseTimeline({
  phases,
  currentPhase,
}: {
  phases: PhaseRow[];
  currentPhase?: string;
}) {
  if (phases.length === 0) {
    return <Empty>no phases yet</Empty>;
  }
  return (
    <div style={{ display: "flex", flexWrap: "wrap", gap: 4 }}>
      {phases.map((p) => {
        const active = p.name === currentPhase;
        const done = p.endedAt != null;
        const color = done ? "#5fd49d" : active ? "#ffd76a" : "#3a3f48";
        return (
          <div
            key={p.name}
            style={{
              padding: "4px 8px",
              border: `1px solid ${color}`,
              borderRadius: 4,
              fontSize: 10,
              color: "#cfd2d6",
              background: active ? "rgba(255,215,106,0.12)" : "transparent",
            }}
            title={`${p.kind ?? "?"} · ${p.status ?? "?"}`}
          >
            <div>{p.name}</div>
            <div style={{ fontSize: 8, color: "#9aa0a6" }}>
              {p.kind ?? "?"} · {p.status ?? (done ? "done" : active ? "running" : "queued")}
            </div>
          </div>
        );
      })}
    </div>
  );
}

function HitlPanel({
  gate,
  activeException,
}: {
  gate: unknown[];
  activeException: { id: string; persona?: string; auto_close_at?: number | null } | null;
}) {
  const first = (gate?.[0] as Record<string, unknown> | undefined) ?? {};
  const persona =
    (first.persona_role as string | undefined) ??
    activeException?.persona ??
    "(unknown)";
  const autoClose = activeException?.auto_close_at ?? null;
  return (
    <div style={{ fontSize: 11 }}>
      <div>persona: <strong style={{ color: COLORS.decision }}>{persona}</strong></div>
      {autoClose && (
        <div style={{ color: "#9aa0a6" }}>
          auto-close at {new Date(autoClose * 1000).toLocaleString()}
        </div>
      )}
      {gate.length > 0 && (
        <pre
          style={{
            marginTop: 6,
            background: "rgba(0,0,0,0.4)",
            padding: 6,
            borderRadius: 4,
            fontSize: 9,
            maxHeight: 100,
            overflow: "auto",
          }}
        >
          {JSON.stringify(gate[0], null, 2)}
        </pre>
      )}
    </div>
  );
}

function Panel({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <section
      style={{
        background: "rgba(15,17,22,0.78)",
        border: "1px solid rgba(207,210,214,0.18)",
        borderRadius: 8,
        padding: 10,
      }}
    >
      <div
        style={{
          fontSize: 9,
          color: "#9aa0a6",
          letterSpacing: "0.12em",
          textTransform: "uppercase",
          marginBottom: 6,
        }}
      >
        {title}
      </div>
      {children}
    </section>
  );
}

function Empty({ children }: { children: React.ReactNode }) {
  return <div style={{ fontSize: 11, color: "#6b7077" }}>{children}</div>;
}

const overlayStyle: React.CSSProperties = {
  position: "absolute",
  inset: 0,
  background: "rgba(6,7,10,0.92)",
  zIndex: 10,
  padding: 18,
  color: "#cfd2d6",
  fontFamily: "var(--mono-family, monospace)",
  overflow: "auto",
};

const headerStyle: React.CSSProperties = {
  display: "flex",
  justifyContent: "space-between",
  alignItems: "flex-start",
  marginBottom: 14,
};

const closeStyle: React.CSSProperties = {
  background: "rgba(20,22,28,0.7)",
  border: "1px solid rgba(207,210,214,0.3)",
  borderRadius: 999,
  color: "#cfd2d6",
  padding: "4px 10px",
  fontFamily: "inherit",
  cursor: "pointer",
};

const layoutStyle: React.CSSProperties = {
  display: "grid",
  gridTemplateColumns: "1fr 1fr",
  gap: 10,
  maxWidth: 1100,
  margin: "0 auto",
};

const mcpRow: React.CSSProperties = {
  fontSize: 11,
  padding: "2px 0",
};

const entityChip: React.CSSProperties = {
  background: "rgba(20,22,28,0.6)",
  border: "1px solid rgba(207,210,214,0.2)",
  borderRadius: 4,
  padding: "3px 6px",
  color: "#cfd2d6",
  fontFamily: "inherit",
  fontSize: 10,
  cursor: "pointer",
};

const decisionRow: React.CSSProperties = {
  fontSize: 11,
  padding: "3px 0",
  borderBottom: "1px solid rgba(207,210,214,0.1)",
};

const auditRow: React.CSSProperties = {
  fontSize: 10,
  padding: "1px 0",
  color: "#cfd2d6",
};

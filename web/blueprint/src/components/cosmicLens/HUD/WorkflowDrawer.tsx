import { Fragment, useEffect, useMemo, useState } from "react";
import { ENDPOINTS } from "../lib/types";
import type { EntityRow, AffinityResponse, CosmicFlash } from "../lib/types";
import { keyAttrFor, verdictColor, formatRelative, parseTimestamp, extractEntityIdRefs } from "../lib/entityRender";
import { colorForEntityType } from "../lib/colors";
import { humanizeTimeline, type HumanEvent } from "./humanizeTimeline";
import { humanWorkflowType, formatAge, humanRelationship, pluralize, kindToVerb, prettyActor } from "../../../../../shared/humanize";
import { labelForEntity, type RocketEvent } from "../lib/labels";
import { prettyAction, personaTitle, type LabelMaps } from "./plainLanguage";

export interface DrawerView {
  type: "function" | "workflow" | "city" | "entity" | null;
  /** function key, workflow id, city id, or entity id depending on type */
  id?: string;
  label?: string;
}

interface WorkflowDrawerProps {
  view: DrawerView;
  onClose: () => void;
  onOpenWorkflow: (id: string) => void;
  onOpenEntity?: (id: string) => void;
  flashesRef?: React.MutableRefObject<{ buffer: CosmicFlash[]; version: number }>;
}

interface WorkflowSummary {
  id: string;
  workflow_type?: string;
  status?: string;
  phase?: string;
  age_s?: number;
  /**
   * Owning function key as classified by the API. Sentinel values `legacy`
   * and `unknown` mean the API could not classify the workflow, so the UI
   * falls back to deriving ownership from the workflow_type → function map.
   */
  function?: string;
}

interface TimelineEvent {
  ts?: number;
  /** Server row category: "phase" | "agent" | "tool" | "decision" | actor_kind. */
  kind: string;
  label?: string;
  status?: string;
  actor?: string;
  verdict?: string;
  reason?: string;
  result_summary?: string | null;
  tokens?: number | null;
  details?: Record<string, unknown> | null;
  completed_at?: number | null;
}

/** Slide-in drawer for click-to-drill. */
export function WorkflowDrawer({ view, onClose, onOpenWorkflow, onOpenEntity, flashesRef }: WorkflowDrawerProps) {
  const isOpen = view.type !== null;
  useEffect(() => {
    if (!isOpen) return;
    const onEsc = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    window.addEventListener("keydown", onEsc);
    return () => window.removeEventListener("keydown", onEsc);
  }, [isOpen, onClose]);

  return (
    <>
      {/* Backdrop */}
      <div
        onClick={onClose}
        style={{
          position: "absolute",
          inset: 0,
          background: isOpen ? "rgba(2,6,23,0.45)" : "transparent",
          opacity: isOpen ? 1 : 0,
          pointerEvents: isOpen ? "auto" : "none",
          transition: "opacity 250ms ease",
          zIndex: 30,
        }}
      />
      {/* Drawer */}
      <div
        style={{
          position: "absolute",
          top: 0,
          bottom: 0,
          right: 0,
          width: 480,
          background: "linear-gradient(to left, rgb(2,6,23), rgb(15,23,42))",
          color: "#e2e8f0",
          fontFamily: "ui-sans-serif, system-ui",
          fontSize: 13,
          transform: isOpen ? "translateX(0)" : "translateX(100%)",
          transition: "transform 280ms cubic-bezier(.5,0,.2,1)",
          zIndex: 40,
          boxShadow: "0 0 40px rgba(0,0,0,0.5)",
          borderLeft: "1px solid rgba(99,102,241,0.3)",
          display: "flex",
          flexDirection: "column",
          overflow: "hidden",
        }}
      >
        <DrawerContent view={view} onClose={onClose} onOpenWorkflow={onOpenWorkflow} onOpenEntity={onOpenEntity} flashesRef={flashesRef} />
      </div>
    </>
  );
}

function DrawerContent({
  view,
  onClose,
  onOpenWorkflow,
  onOpenEntity,
  flashesRef,
}: {
  view: DrawerView;
  onClose: () => void;
  onOpenWorkflow: (id: string) => void;
  onOpenEntity?: (id: string) => void;
  flashesRef?: React.MutableRefObject<{ buffer: CosmicFlash[]; version: number }>;
}) {
/** Set of Kuzu entity kinds — used to decide whether a clicked city is an
 *  entity-type slot (route to EntityKindView) vs a capability node (route
 *  to the new CapabilityView). Mirrors api/server/routes/cities.py
 *  ENTITY_KINDS. */
const ENTITY_KIND_SET = new Set([
  "Person", "Organisation", "Asset", "Money", "Decision", "Place", "Period",
  "Workflow", "Brand", "Campaign", "Pitch", "MediaPlan", "Subsidiary",
]);

  if (view.type === "function") {
    return <FunctionView functionKey={view.id ?? ""} label={view.label} onClose={onClose} onOpenWorkflow={onOpenWorkflow} />;
  }
  if (view.type === "workflow") {
    return <WorkflowView workflowId={view.id ?? ""} onClose={onClose} />;
  }
  if (view.type === "city") {
    const cityId = view.id ?? "";
    // Entity-type slot in entities mode → recent records of that kind.
    // Otherwise (capability in capabilities mode) → CapabilityView.
    if (ENTITY_KIND_SET.has(cityId)) {
      return <CityView cityId={cityId} label={view.label} onClose={onClose}
                       onOpenEntity={onOpenEntity ?? (() => {})}
                       flashesRef={flashesRef} />;
    }
    return <CapabilityView cityId={cityId} label={view.label} onClose={onClose}
                            onOpenWorkflow={onOpenWorkflow} />;
  }
  if (view.type === "entity") {
    return <EntityView entityId={view.id ?? ""} onClose={onClose}
                       onOpenWorkflow={onOpenWorkflow}
                       onOpenEntity={onOpenEntity ?? (() => {})} />;
  }
  return null;
}

function DrawerHeader({ title, subtitle, onClose }: { title: string; subtitle?: string; onClose: () => void }) {
  return (
    <div
      style={{
        padding: "16px 20px 14px",
        borderBottom: "1px solid rgba(148,163,184,0.12)",
        display: "flex",
        justifyContent: "space-between",
        alignItems: "flex-start",
      }}
    >
      <div>
        <div style={{ fontSize: 16, fontWeight: 600, color: "#e2e8f0" }}>{title}</div>
        {subtitle && (
          <div style={{ fontSize: 11, color: "#94a3b8", marginTop: 4, textTransform: "uppercase", letterSpacing: 0.5 }}>
            {subtitle}
          </div>
        )}
      </div>
      <button
        onClick={onClose}
        style={{
          background: "transparent",
          border: "1px solid rgba(148,163,184,0.18)",
          color: "#94a3b8",
          width: 28,
          height: 28,
          borderRadius: 6,
          cursor: "pointer",
          fontSize: 14,
        }}
        title="Close (ESC)"
      >
        ×
      </button>
    </div>
  );
}

function PersonaInsightPanel({
  role,
  labels,
}: {
  role: string;
  labels?: LabelMaps;
}) {
  const [insight, setInsight] = useState<{
    id?: string;
    role?: string;
    headline?: string;
    body?: string;
    kpis?: Record<string, unknown>;
    proposed_actions?: Array<{
      id: string;
      label?: string;
      verdict?: string;
      decided_on?: string[];
      attributes?: Record<string, unknown>;
    }>;
  } | null>(null);

  useEffect(() => {
    if (!role) {
      setInsight(null);
      return;
    }
    let cancelled = false;
    const refresh = () => {
      fetch(`/api/personas/${encodeURIComponent(role)}/insights/latest`)
        .then(r => (r.ok ? r.json() : null))
        .then(data => { if (!cancelled) setInsight(data ?? null); })
        .catch(() => { if (!cancelled) setInsight(null); });
    };
    refresh();
    // Re-fetch every 5s so the panel stays current with the cadence loop.
    const id = window.setInterval(refresh, 5000);
    return () => { cancelled = true; window.clearInterval(id); };
  }, [role]);

  if (!insight) return null;
  return (
    <section
      className="insight-panel"
      style={{
        marginTop: 4,
        marginBottom: 14,
        padding: 12,
        border: "1px solid rgba(167,139,250,0.3)",
        borderRadius: 6,
        background: "rgba(76,29,149,0.15)",
      }}
    >
      <div
        className="insight-persona-chip"
        style={{
          display: "inline-block",
          padding: "2px 6px",
          marginBottom: 6,
          fontSize: 10,
          letterSpacing: 0.6,
          textTransform: "uppercase",
          color: "#a78bfa",
          border: "1px solid rgba(167,139,250,0.4)",
          borderRadius: 3,
          background: "rgba(76,29,149,0.25)",
        }}
      >
        {personaTitle(insight.role ?? role, labels)}
      </div>
      <h3 style={{ margin: 0, fontSize: 13, color: "#e2e8f0" }}>{insight.headline}</h3>
      {insight.body && (
        <p style={{ margin: "6px 0 0", fontSize: 12, color: "#cbd5e1", whiteSpace: "pre-wrap" }}>
          {insight.body}
        </p>
      )}
      {insight.kpis && Object.keys(insight.kpis).length > 0 && (
        <dl
          className="insight-kpis"
          style={{
            display: "grid",
            gridTemplateColumns: "auto 1fr",
            gap: "2px 8px",
            margin: "8px 0 0",
            fontSize: 11,
            color: "#94a3b8",
          }}
        >
          {Object.entries(insight.kpis).map(([k, v]) => (
            <Fragment key={k}>
              <dt style={{ color: "#a78bfa" }}>{k}</dt>
              <dd style={{ margin: 0, color: "#e2e8f0" }}>{String(v)}</dd>
            </Fragment>
          ))}
        </dl>
      )}
      {Array.isArray(insight.proposed_actions) && insight.proposed_actions.length > 0 && (
        <ul
          className="insight-actions"
          style={{ listStyle: "none", padding: 0, margin: "10px 0 0" }}
        >
          {insight.proposed_actions.map((a) => (
            <li
              key={a.id}
              style={{
                display: "flex",
                justifyContent: "space-between",
                alignItems: "center",
                padding: "4px 0",
                fontSize: 11,
                color: "#e2e8f0",
              }}
            >
              <span>{prettyAction(a, labels) || a.label || a.id}</span>
              <span
                title="Self-applied — gated only by the AGT matrix"
                style={{
                  color: "#22d3ee",
                  border: "1px solid rgba(34,211,238,0.4)",
                  padding: "2px 8px",
                  borderRadius: 3,
                  fontSize: 11,
                  background: "rgba(34,211,238,0.08)",
                }}
              >
                Auto-applied ✓
              </span>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}

function FunctionView({
  functionKey,
  label,
  onClose,
  onOpenWorkflow,
}: {
  functionKey: string;
  label?: string;
  onClose: () => void;
  onOpenWorkflow: (id: string) => void;
}) {
  const [workflows, setWorkflows] = useState<WorkflowSummary[]>([]);
  const [loading, setLoading] = useState(true);
  const [seniorRole, setSeniorRole] = useState<string | null>(null);
  const [labels, setLabels] = useState<LabelMaps | undefined>(undefined);

  useEffect(() => {
    let cancelled = false;
    fetch(`/api/personas/labels/preview`)
      .then(r => (r.ok ? r.json() : null))
      .then(data => { if (!cancelled && data) setLabels(data as LabelMaps); })
      .catch(() => { /* fall back */ });
    return () => { cancelled = true; };
  }, []);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      setLoading(true);
      try {
        const [wfRes, fnRes] = await Promise.all([
          fetch(ENDPOINTS.inFlight).then((r) => r.json()),
          fetch(ENDPOINTS.functions).then((r) => r.json()),
        ]);
        const allWfs = (Array.isArray(wfRes) ? wfRes : wfRes.workflows ?? []) as WorkflowSummary[];
        const allFns = (Array.isArray(fnRes) ? fnRes : fnRes.functions ?? []) as Array<{
          name?: string; key?: string; ownsDomains?: string[]; domains?: string[];
          personaHierarchy?: { role?: string };
        }>;
        // Build workflow_type -> function map
        const wfTypeMap = new Map<string, string>();
        for (const fn of allFns) {
          const fnK = fn.name ?? fn.key;
          if (!fnK) continue;
          for (const d of fn.ownsDomains ?? fn.domains ?? []) wfTypeMap.set(d, fnK);
        }
        // Resolve senior persona for THIS function planet so we can fetch
        // its latest insight. The CEO planet is special-cased to surface
        // the org-wide synthesis (CEO persona) regardless of what the
        // /api/functions roster has stamped as its senior persona.
        const fnRow = allFns.find((f) => (f.name ?? f.key) === functionKey);
        const senior = functionKey === "ceo"
          ? "ceo"
          : fnRow?.personaHierarchy?.role ?? null;
        if (!cancelled) setSeniorRole(senior);
        // Filter workflows whose owning function == functionKey
        const filtered = allWfs.filter((wf) => {
          if (wf.function && wf.function !== "legacy" && wf.function !== "unknown") {
            return wf.function === functionKey;
          }
          const wfType = wf.workflow_type;
          if (!wfType) return false;
          const owner = wfTypeMap.get(wfType);
          return owner === functionKey;
        });
        if (!cancelled) setWorkflows(filtered);
      } catch (err) {
        console.warn("function workflows fetch failed", err);
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [functionKey]);

  return (
    <>
      <DrawerHeader
        title={label ?? functionKey}
        subtitle={functionKey === "ceo" ? "executive synthesis" : "function"}
        onClose={onClose}
      />
      <div style={{ flex: 1, overflowY: "auto", padding: "12px 20px" }}>
        {seniorRole && <PersonaInsightPanel role={seniorRole} labels={labels} />}
        {loading && <div style={{ color: "#64748b", fontStyle: "italic" }}>Loading workflows…</div>}
        {!loading && workflows.length === 0 && (
          <div style={{ color: "#64748b", fontStyle: "italic" }}>
            No workflows are running here right now.
          </div>
        )}
        {workflows.map((wf) => (
          <button
            key={wf.id}
            onClick={() => onOpenWorkflow(wf.id)}
            style={{
              display: "block",
              width: "100%",
              padding: "10px 12px",
              margin: "4px 0",
              background: "rgba(15,23,42,0.6)",
              border: "1px solid rgba(99,102,241,0.15)",
              borderRadius: 6,
              cursor: "pointer",
              textAlign: "left",
              color: "#e2e8f0",
              fontFamily: "inherit",
              fontSize: 13,
            }}
          >
            <div style={{ fontWeight: 600, color: "#22d3ee" }}>{wf.id}</div>
            <div style={{ fontSize: 11, color: "#94a3b8", marginTop: 3 }}>
              {humanWorkflowType(wf.workflow_type)} · {wf.phase ?? "—"} · {formatAge(wf.age_s)}
            </div>
          </button>
        ))}
      </div>
    </>
  );
}

function WorkflowView({ workflowId, onClose }: { workflowId: string; onClose: () => void }) {
  const [events, setEvents] = useState<TimelineEvent[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      setLoading(true);
      try {
        const res = await fetch(ENDPOINTS.workflowTimeline(workflowId));
        if (!res.ok) throw new Error(`${res.status}`);
        const data = await res.json();
        const items = (
          Array.isArray(data) ? data : data.timeline ?? data.events ?? []
        ) as TimelineEvent[];
        if (!cancelled) setEvents(items);
      } catch (err) {
        console.warn("timeline fetch failed", err);
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [workflowId]);

  return (
    <>
      <DrawerHeader title={workflowId} subtitle="workflow history" onClose={onClose} />
      <div style={{ flex: 1, overflowY: "auto", padding: "12px 20px" }}>
        {loading && <div style={{ color: "#64748b", fontStyle: "italic" }}>loading…</div>}
        {!loading && events.length === 0 && (
          <div style={{ color: "#64748b", fontStyle: "italic" }}>
            Nothing has happened in this workflow yet.
          </div>
        )}
        <HumanTimeline events={events} />
      </div>
    </>
  );
}

function HumanTimeline({ events }: { events: TimelineEvent[] }) {
  const human = useMemo(() => humanizeTimeline(events), [events]);
  if (human.length === 0) return null;
  return (
    <ol style={{ listStyle: "none", padding: 0, margin: 0 }}>
      {human.map((h, i) => (
        <HumanRow key={i} ev={h} />
      ))}
    </ol>
  );
}

function HumanRow({ ev }: { ev: HumanEvent }) {
  const dot = toneColor(ev.tone);
  return (
    <li
      style={{
        display: "grid",
        gridTemplateColumns: "56px 14px 1fr",
        gap: 10,
        alignItems: "baseline",
        padding: "10px 0",
        borderBottom: "1px solid rgba(148,163,184,0.08)",
      }}
    >
      <div
        style={{
          fontSize: 11,
          color: "#64748b",
          fontVariantNumeric: "tabular-nums",
          textAlign: "right",
        }}
      >
        {ev.when}
      </div>
      <div
        aria-hidden
        style={{
          width: 8,
          height: 8,
          borderRadius: 4,
          background: dot,
          boxShadow: `0 0 8px ${dot}`,
          marginTop: 6,
        }}
      />
      <div>
        <div style={{ color: "#e2e8f0", fontSize: 13, fontWeight: 500, lineHeight: 1.35 }}>
          {ev.what}
        </div>
        <div style={{ fontSize: 11, color: "#94a3b8", marginTop: 2 }}>{ev.who}</div>
        {ev.detail && (
          <div
            style={{
              fontSize: 11,
              color: "#cbd5e1",
              marginTop: 6,
              padding: "6px 8px",
              background: "rgba(15,23,42,0.55)",
              borderLeft: `2px solid ${dot}`,
              borderRadius: 2,
              lineHeight: 1.4,
            }}
          >
            {ev.detail}
          </div>
        )}
      </div>
    </li>
  );
}

function toneColor(tone: HumanEvent["tone"]): string {
  switch (tone) {
    case "ok":        return "#22c55e";
    case "warn":      return "#f59e0b";
    case "bad":       return "#ef4444";
    case "milestone": return "#a78bfa";
    case "muted":     return "#64748b";
  }
}

/** CapabilityView — drawer pane shown when the user clicks on a CAPABILITIES-mode
 *  city (mcp / skill / validator / persona). Renders:
 *    • description (from SKILL.md frontmatter or .py docstring)
 *    • kind (mcp/skill/validator/persona)
 *    • parked workflows (for persona kind: list of workflow_ids waiting
 *      at this gate, click to open a WorkflowView in the drawer)
 *    • last-called timestamp + recent invocation count from the local
 *      blueprint recorder
 *
 *  Polled every 8s so parked-workflow counts and last-called update
 *  while the drawer stays open.
 */
function CapabilityView({
  cityId, label, onClose, onOpenWorkflow,
}: {
  cityId: string;
  label?: string;
  onClose: () => void;
  onOpenWorkflow: (id: string) => void;
}) {
  const [meta, setMeta] = useState<{
    id: string;
    kind: string;
    label: string;
    description: string | null;
    parked_workflows: Array<{
      workflow_id: string;
      workflow_type?: string | null;
      phase?: string | null;
      age_s?: number | null;
    }>;
    last_called_at: number | null;
    recent_invocation_count: number;
  } | null>(null);

  useEffect(() => {
    let cancelled = false;
    async function load() {
      try {
        const res = await fetch(`/api/cities/${encodeURIComponent(cityId)}`);
        if (!res.ok) return;
        const body = await res.json();
        if (!cancelled) setMeta(body);
      } catch {
        /* ignore — drawer just keeps last value */
      }
    }
    load();
    const iv = setInterval(load, 8000);
    return () => { cancelled = true; clearInterval(iv); };
  }, [cityId]);

  // Friendly subtitle line: "MCP TOOL", "PERSONA", etc.
  const KIND_PRETTY: Record<string, string> = {
    mcp: "MCP tool",
    skill: "Deterministic skill",
    validator: "Validator",
    persona: "Persona / human role",
  };
  const subtitle = meta?.kind ? (KIND_PRETTY[meta.kind] ?? meta.kind) : "Capability";
  const lastCalledRel = meta?.last_called_at
    ? formatRelative(meta.last_called_at * 1000)
    : null;

  return (
    <>
      <DrawerHeader
        title={prettyActor(label ?? meta?.label ?? cityId)}
        subtitle={subtitle.toUpperCase()}
        onClose={onClose}
      />
      <div style={{ flex: 1, overflowY: "auto", padding: "12px 20px" }}>
        {/* What is this thing? */}
        <SectionHeader>What it does</SectionHeader>
        {meta?.description ? (
          <div style={{
            color: "#cbd5e1",
            fontSize: 12,
            lineHeight: 1.5,
            marginBottom: 14,
            padding: "8px 10px",
            background: "rgba(15,23,42,0.7)",
            border: "1px solid rgba(148,163,184,0.12)",
            borderRadius: 6,
          }}>
            {meta.description}
          </div>
        ) : meta ? (
          <Empty>No description on file for this capability.</Empty>
        ) : (
          <Empty>Loading…</Empty>
        )}

        {/* Activity at-a-glance */}
        <SectionHeader>Activity</SectionHeader>
        <div style={{
          display: "grid",
          gridTemplateColumns: "repeat(2, 1fr)",
          gap: 8,
          marginBottom: 14,
        }}>
          <Stat
            label="Recent invocations"
            value={meta?.recent_invocation_count ?? "—"}
            accent="#22d3ee"
          />
          <Stat
            label="Last called"
            value={lastCalledRel ?? "—"}
            accent={lastCalledRel ? "#a78bfa" : "#475569"}
          />
        </div>

        {/* Parked workflows — only meaningful for persona kind. The API
            returns a list of {workflow_id, workflow_type, phase, age_s}
            for each one, so we render them as clickable rows that open
            the workflow drawer when clicked. */}
        {(meta?.parked_workflows?.length ?? 0) > 0 && (
          <>
            <SectionHeader>
              Workflows currently parked here ({meta!.parked_workflows.length})
            </SectionHeader>
            {meta!.parked_workflows.map((wf) => (
              <Row key={wf.workflow_id} onClick={() => onOpenWorkflow(wf.workflow_id)}>
                <div style={{ color: "#fb923c", fontWeight: 600, fontSize: 12 }}>
                  {wf.workflow_id}
                </div>
                <div style={{ fontSize: 11, color: "#cbd5e1", marginTop: 2 }}>
                  {wf.workflow_type ? humanWorkflowType(wf.workflow_type) : "—"}
                  {wf.phase ? ` · ${wf.phase}` : ""}
                </div>
                <div style={{ fontSize: 10, color: "#64748b", marginTop: 2 }}>
                  {wf.age_s != null ? `Waiting ${formatAge(wf.age_s)}` : "Awaiting decision"} · click to inspect
                </div>
              </Row>
            ))}
          </>
        )}

        {meta?.kind === "persona" && (meta.parked_workflows?.length ?? 0) === 0 && (
          <>
            <SectionHeader>Workflows currently parked here</SectionHeader>
            <Empty>No workflows waiting on {prettyActor(meta.label)} right now.</Empty>
          </>
        )}
      </div>
    </>
  );
}

/** Tiny stat tile — one of two columns shown under 'Activity' in
 *  CapabilityView. Mirrors the chrome of VitalSignsBar's stats. */
function Stat({ label, value, accent }: { label: string; value: number | string; accent: string }) {
  return (
    <div style={{
      padding: "8px 10px",
      background: "rgba(15,23,42,0.7)",
      border: "1px solid rgba(148,163,184,0.12)",
      borderRadius: 6,
      display: "flex",
      flexDirection: "column",
      gap: 2,
    }}>
      <span style={{ color: accent, fontSize: 16, fontWeight: 600, fontVariantNumeric: "tabular-nums" }}>
        {value}
      </span>
      <span style={{ fontSize: 10, color: "#94a3b8", textTransform: "uppercase", letterSpacing: 0.5 }}>
        {label}
      </span>
    </div>
  );
}

function CityView({
  cityId, label, onClose, onOpenEntity, flashesRef,
}: {
  cityId: string;
  label?: string;
  onClose: () => void;
  onOpenEntity: (id: string) => void;
  flashesRef?: React.MutableRefObject<{ buffer: CosmicFlash[]; version: number }>;
}) {
  const [recent, setRecent] = useState<EntityRow[]>([]);
  const [rels, setRels] = useState<AffinityResponse["rels"]>([]);
  const [meta, setMeta] = useState<{ count: number; rate: number } | null>(null);
  const [, setTick] = useState(0);

  useEffect(() => {
    let cancelled = false;
    async function load() {
      try {
        const [r, a, c] = await Promise.all([
          fetch(`/api/entities?kind=${encodeURIComponent(cityId)}&limit=10&order=recent`).then(x => x.json()),
          fetch(`/api/cities/affinity?kind=${encodeURIComponent(cityId)}`).then(x => x.json()),
          fetch(`/api/cities?mode=entities`).then(x => x.json()),
        ]);
        if (cancelled) return;
        setRecent(Array.isArray(r) ? r : []);
        setRels((a as AffinityResponse).rels ?? []);
        const cities = (c.cities ?? c) as Array<{ id: string; count: number; recent_activity_per_min: number }>;
        const me = cities.find(x => x.id === cityId);
        if (me) setMeta({ count: me.count ?? 0, rate: me.recent_activity_per_min ?? 0 });
      } catch (err) {
        console.warn("CityView fetch failed", err);
      }
    }
    load();
    const iv = setInterval(load, 8000);
    const tick = setInterval(() => setTick(t => t + 1), 1000);
    return () => { cancelled = true; clearInterval(iv); clearInterval(tick); };
  }, [cityId]);

  const liveActivity = (() => {
    if (!flashesRef) return [];
    const buf = flashesRef.current.buffer;
    return buf
      .filter(f => (f.type === "entity.read" || f.type === "entity.upserted" || f.type === "entity.linked")
                   && (f as unknown as { kind?: string }).kind === cityId)
      .slice(-5)
      .reverse();
  })();

  const color = colorForEntityType(cityId);
  return (
    <>
      <DrawerHeader
        title={label ?? cityId}
        subtitle={meta ? `${pluralize(meta.count, cityId)} · ${meta.rate.toFixed(1)} updates/min` : "Records of this kind"}
        onClose={onClose}
      />
      <div style={{ flex: 1, overflowY: "auto", padding: "12px 20px" }}>
        <SectionHeader>Most recently touched</SectionHeader>
        {recent.length === 0 && <Empty>Nothing of this kind has been recorded yet.</Empty>}
        {recent.map((r) => {
          const ts = parseTimestamp(r.last_seen_at ?? r.decided_at ?? r.first_seen_at);
          const wfCount = (r.source_workflows ?? []).length;
          const wfTypes = new Set((r.source_workflows ?? []).map((w: string) => w.split("-")[0]));
          const crossDomain = wfTypes.size >= 2;
          return (
            <Row key={r.id} onClick={() => onOpenEntity(r.id)}>
              <div style={{ color: "#22d3ee", fontWeight: 600 }}>{r.id}</div>
              <div style={{ fontSize: 11, color: "#cbd5e1", marginTop: 2 }}>
                {keyAttrFor(cityId, r as Record<string, unknown>)}
              </div>
              <div style={{ fontSize: 10, color: "#64748b", marginTop: 4, display: "flex", gap: 8 }}>
                {ts && <span>{formatRelative(ts)}</span>}
                {wfCount > 0 && <span>{pluralize(wfCount, "workflow")}</span>}
                {crossDomain && <span style={{ color: color, fontWeight: 600 }}>spans several domains</span>}
              </div>
            </Row>
          );
        })}

        <SectionHeader style={{ marginTop: 18 }}>Connected to</SectionHeader>
        {(rels ?? []).length === 0 && <Empty>Nothing connects to records of this kind yet.</Empty>}
        {(rels ?? []).slice(0, 5).map((rl) => (
          <div key={`${rl.rel}-${rl.partner_kind}`} style={{
            padding: "6px 12px", margin: "2px 0",
            background: "rgba(15,23,42,0.4)", fontSize: 12, color: "#cbd5e1",
            display: "flex", justifyContent: "space-between",
          }}>
            <span style={{ color: "#a78bfa" }}>{humanRelationship(rl.rel)}</span>
            <span style={{ color: "#94a3b8" }}>{pluralize(rl.count, rl.partner_kind)}</span>
          </div>
        ))}

        <SectionHeader style={{ marginTop: 18 }}>Live activity</SectionHeader>
        {liveActivity.length === 0 && <Empty>No recent activity for this kind.</Empty>}
        {liveActivity.map((f, i) => (
          <div key={i} style={{
            padding: "4px 12px", fontSize: 11, color: "#94a3b8",
            borderLeft: `2px solid ${color}`, margin: "2px 0",
          }}>
            <span style={{ color: "#cbd5e1" }}>{labelForEntity(f as unknown as RocketEvent)}</span>
            {f.workflow_id && <span style={{ marginLeft: 8 }}>· {humanWorkflowType(f.workflow_id.split("-")[0])} {f.workflow_id}</span>}
          </div>
        ))}
      </div>
    </>
  );
}

function EntityView({
  entityId, onClose, onOpenWorkflow, onOpenEntity,
}: {
  entityId: string;
  onClose: () => void;
  onOpenWorkflow: (id: string) => void;
  onOpenEntity: (id: string) => void;
}) {
  const [entity, setEntity] = useState<EntityRow | null>(null);
  const [linked, setLinked] = useState<Array<{ node: EntityRow; rel: string }>>([]);
  const [precedents, setPrecedents] = useState<Array<{
    id: string; workflow_id: string; phase: string;
    verdict: string; reason: string; decided_at: string | null;
  }>>([]);
  const [insight, setInsight] = useState<{
    id?: string;
    role?: string;
    headline?: string;
    body?: string;
    kpis?: Record<string, unknown>;
    proposed_actions?: Array<{ id: string; label?: string; verdict?: string; decided_on?: string[]; attributes?: Record<string, unknown> }>;
  } | null>(null);
  const [labels, setLabels] = useState<LabelMaps | undefined>(undefined);
  const [, setTick] = useState(0);

  useEffect(() => {
    let cancelled = false;
    fetch(`/api/personas/labels/preview`)
      .then(r => (r.ok ? r.json() : null))
      .then(data => { if (!cancelled && data) setLabels(data as LabelMaps); })
      .catch(() => { /* fall back to defaults */ });
    return () => { cancelled = true; };
  }, []);

  useEffect(() => {
    let cancelled = false;
    async function load() {
      try {
        const [e, l] = await Promise.all([
          fetch(`/api/entities/${encodeURIComponent(entityId)}`).then(r => r.json()),
          fetch(`/api/entities/${encodeURIComponent(entityId)}/linked`).then(r => r.json()),
        ]);
        if (cancelled) return;
        setEntity(e);
        // /api/entities/{id}/linked returns [{rel, entity}]; normalise to {rel, node}.
        const rows = Array.isArray(l) ? l : [];
        const normalised = rows.map((row: { rel: string; entity?: EntityRow; node?: EntityRow }) => ({
          rel: row.rel,
          node: (row.node ?? row.entity ?? {}) as EntityRow,
        }));
        setLinked(normalised);
      } catch (err) {
        console.warn("EntityView fetch failed", err);
      }
    }
    load();
    const tick = setInterval(() => setTick(t => t + 1), 1000);
    return () => { cancelled = true; clearInterval(tick); };
  }, [entityId]);

  useEffect(() => {
    if (entity?.kind !== "Decision" && entity?._label !== "Decision") {
      setPrecedents([]);
      return;
    }
    let cancelled = false;
    fetch(`/api/entities/${encodeURIComponent(entityId)}/precedents`)
      .then(r => (r.ok ? r.json() : Promise.reject(`HTTP ${r.status}`)))
      .then(d => { if (!cancelled) setPrecedents(d.precedents ?? []); })
      .catch(() => { if (!cancelled) setPrecedents([]); });
    return () => { cancelled = true; };
  }, [entityId, entity?.kind, entity?._label]);

  // Persona-insight panel: when the open entity is a Person with a `role`
  // attribute (i.e., a persona planet), fetch the latest published insight
  // for that role. 404 → no insight yet; render nothing.
  const personaRole =
    entity && entity._label === "Person" && typeof entity.role === "string"
      ? (entity.role as string)
      : null;
  useEffect(() => {
    if (!personaRole) {
      setInsight(null);
      return;
    }
    let cancelled = false;
    fetch(`/api/personas/${encodeURIComponent(personaRole)}/insights/latest`)
      .then(r => (r.ok ? r.json() : null))
      .then(data => { if (!cancelled) setInsight(data ?? null); })
      .catch(() => { if (!cancelled) setInsight(null); });
    return () => { cancelled = true; };
  }, [personaRole]);

  if (!entity) {
    return (
      <>
        <DrawerHeader title={entityId} subtitle="Loading…" onClose={onClose} />
        <div style={{ padding: 20, color: "#64748b", fontStyle: "italic" }}>Loading record…</div>
      </>
    );
  }

  const kind = String(entity._label ?? entity.kind ?? "Unknown");
  const color = colorForEntityType(kind);
  const firstSeenMs = parseTimestamp(entity.first_seen_at);
  const lastSeenMs = parseTimestamp(entity.last_seen_at ?? entity.decided_at);
  const sourceWfs = (entity.source_workflows ?? []) as string[];
  const wfTypeCounts = new Map<string, number>();
  for (const wf of sourceWfs) {
    const t = wf.split("-")[0];
    wfTypeCounts.set(t, (wfTypeCounts.get(t) ?? 0) + 1);
  }

  const linkedByRel = new Map<string, Array<{ node: EntityRow; rel: string }>>();
  for (const l of linked) {
    if (!linkedByRel.has(l.rel)) linkedByRel.set(l.rel, []);
    linkedByRel.get(l.rel)!.push(l);
  }

  return (
    <>
      <DrawerHeader
        title={entityId}
        subtitle={kindToVerb(kind)}
        onClose={onClose}
      />
      <div style={{ flex: 1, overflowY: "auto", padding: "12px 20px" }}>
        <div style={{
          display: "flex", gap: 8, marginBottom: 14,
          fontSize: 11, color: "#94a3b8",
        }}>
          <span style={{ background: color, color: "#0f172a", padding: "2px 8px", borderRadius: 4, fontWeight: 600 }}>{kind}</span>
          {firstSeenMs && <span>created {formatRelative(firstSeenMs)}</span>}
          {lastSeenMs && <span>· last touched {formatRelative(lastSeenMs)}</span>}
        </div>

        <NarrativePanel kind={kind} entity={entity} onOpenEntity={onOpenEntity} />

        <SectionHeader>Attributes</SectionHeader>
        <AttributesPanel entity={entity} onOpenEntity={onOpenEntity} />

        <SectionHeader style={{ marginTop: 18 }}>
          Touched by {pluralize(sourceWfs.length, "workflow")} across {pluralize(wfTypeCounts.size, "domain")}
        </SectionHeader>
        {sourceWfs.length === 0 && <Empty>No workflows have touched this record yet.</Empty>}
        {sourceWfs.length > 0 && (
          <div>
            {[...wfTypeCounts.entries()].sort((a, b) => b[1] - a[1]).map(([t, n]) => (
              <div key={t} style={{ display: "flex", alignItems: "center", gap: 8, fontSize: 11, color: "#cbd5e1", padding: "2px 0" }}>
                <span style={{ width: 110 }}>{humanWorkflowType(t)}</span>
                <div style={{ flex: 1, height: 6, background: "rgba(99,102,241,0.15)" }}>
                  <div style={{ width: `${Math.min(100, n * 4)}%`, height: 6, background: "#a78bfa" }} />
                </div>
                <span style={{ width: 24, textAlign: "right" }}>{n}</span>
              </div>
            ))}
            <div style={{ marginTop: 8, fontSize: 10, color: "#64748b" }}>
              {sourceWfs.slice(0, 8).map((wf) => (
                <button
                  key={wf}
                  onClick={() => onOpenWorkflow(wf)}
                  style={{
                    background: "transparent", border: "1px solid rgba(99,102,241,0.2)",
                    color: "#22d3ee", padding: "2px 6px", marginRight: 4, marginBottom: 4,
                    fontSize: 10, cursor: "pointer", borderRadius: 3,
                  }}
                  title={wf}
                >
                  {humanWorkflowType(wf.split("-")[0])} · {wf}
                </button>
              ))}
              {sourceWfs.length > 8 && <span style={{ marginLeft: 4 }}>+{sourceWfs.length - 8} more</span>}
            </div>
          </div>
        )}

        <SectionHeader style={{ marginTop: 18 }}>Connected to</SectionHeader>
        {linkedByRel.size === 0 && <Empty>This record has no outgoing connections yet.</Empty>}
        {[...linkedByRel.entries()].map(([rel, items]) => (
          <div key={rel} style={{ marginBottom: 8 }}>
            <div style={{ fontSize: 10, color: "#a78bfa", fontWeight: 600, padding: "4px 0" }}>{humanRelationship(rel)} ({items.length})</div>
            {items.map((l, i) => {
              const partnerKind = String(l.node._label ?? l.node.kind ?? "?");
              const partnerColor = colorForEntityType(partnerKind);
              return (
                <Row key={`${rel}-${i}`} onClick={() => onOpenEntity(String(l.node.id))}>
                  <div style={{ display: "flex", justifyContent: "space-between" }}>
                    <span style={{ color: "#22d3ee" }}>{String(l.node.id)}</span>
                    <span style={{ color: partnerColor, fontSize: 10 }}>{kindToVerb(partnerKind)}</span>
                  </div>
                </Row>
              );
            })}
          </div>
        ))}

        {insight && (
          <section
            className="insight-panel"
            style={{
              marginTop: 18,
              padding: 12,
              border: "1px solid rgba(167,139,250,0.3)",
              borderRadius: 6,
              background: "rgba(76,29,149,0.15)",
            }}
          >
            {(insight.role ?? personaRole) && (
              <div
                className="insight-persona-chip"
                style={{
                  display: "inline-block",
                  padding: "2px 6px",
                  marginBottom: 6,
                  fontSize: 10,
                  letterSpacing: 0.6,
                  textTransform: "uppercase",
                  color: "#a78bfa",
                  border: "1px solid rgba(167,139,250,0.4)",
                  borderRadius: 3,
                  background: "rgba(76,29,149,0.25)",
                }}
              >
                {personaTitle(insight.role ?? personaRole ?? undefined, labels)}
              </div>
            )}
            <h3 style={{ margin: 0, fontSize: 13, color: "#e2e8f0" }}>{insight.headline}</h3>
            {insight.body && (
              <p style={{ margin: "6px 0 0", fontSize: 12, color: "#cbd5e1" }}>{insight.body}</p>
            )}
            {insight.kpis && Object.keys(insight.kpis).length > 0 && (
              <dl
                className="insight-kpis"
                style={{
                  display: "grid",
                  gridTemplateColumns: "auto 1fr",
                  gap: "2px 8px",
                  margin: "8px 0 0",
                  fontSize: 11,
                  color: "#94a3b8",
                }}
              >
                {Object.entries(insight.kpis).map(([k, v]) => (
                  <Fragment key={k}>
                    <dt style={{ color: "#a78bfa" }}>{k}</dt>
                    <dd style={{ margin: 0, color: "#e2e8f0" }}>{String(v)}</dd>
                  </Fragment>
                ))}
              </dl>
            )}
            {Array.isArray(insight.proposed_actions) && insight.proposed_actions.length > 0 && (
              <ul
                className="insight-actions"
                style={{ listStyle: "none", padding: 0, margin: "10px 0 0" }}
              >
                {insight.proposed_actions.map((a) => (
                  <li
                    key={a.id}
                    style={{
                      display: "flex",
                      justifyContent: "space-between",
                      alignItems: "center",
                      padding: "4px 0",
                      fontSize: 11,
                      color: "#e2e8f0",
                    }}
                  >
                    <span>{prettyAction(a, labels) || a.label || a.id}</span>
                    <span
                      title="Self-applied — gated only by the AGT matrix"
                      style={{
                        color: "#22d3ee",
                        border: "1px solid rgba(34,211,238,0.4)",
                        padding: "2px 8px",
                        borderRadius: 3,
                        fontSize: 11,
                        background: "rgba(34,211,238,0.08)",
                      }}
                    >
                      Auto-applied ✓
                    </span>
                  </li>
                ))}
              </ul>
            )}
          </section>
        )}

        {kind === "Decision" && precedents.length > 0 && (
          <>
            <SectionHeader style={{ marginTop: 18 }}>Precedents</SectionHeader>
            <div className="entity-view__precedents">
              {precedents.map(p => (
                <Row key={p.id} onClick={() => onOpenEntity(p.id)}>
                  <div style={{ display: "flex", justifyContent: "space-between", fontSize: 11 }}>
                    <span style={{ color: "#22d3ee", fontFamily: "monospace" }}>{p.workflow_id}</span>
                    <span style={{ color: verdictColor(p.verdict), fontSize: 10 }}>{p.verdict}</span>
                  </div>
                  <div style={{ fontSize: 10, color: "#94a3b8", marginTop: 2 }}>
                    {p.phase}
                    {p.reason && <span> — {p.reason}</span>}
                  </div>
                </Row>
              ))}
            </div>
          </>
        )}
      </div>
    </>
  );
}

function NarrativePanel({
  kind, entity, onOpenEntity,
}: { kind: string; entity: EntityRow; onOpenEntity: (id: string) => void }) {
  // onOpenEntity reserved for future per-narrative click-throughs.
  void onOpenEntity;
  if (kind === "Decision") {
    const verdict = String(entity.verdict ?? "");
    const reason = String(entity.reason ?? "");
    return (
      <div style={{
        padding: "10px 12px", marginBottom: 14,
        background: "rgba(15,23,42,0.7)",
        borderLeft: `3px solid ${verdictColor(verdict)}`,
      }}>
        <div style={{ fontSize: 14, fontWeight: 600, color: verdictColor(verdict), marginBottom: 4 }}>
          {verdict || "(no verdict)"}
        </div>
        <div style={{ fontSize: 12, color: "#cbd5e1", lineHeight: 1.4 }}>{reason || "(no reason)"}</div>
        <div style={{ fontSize: 10, color: "#64748b", marginTop: 6 }}>
          {[
            entity.persona_role ? prettyActor(String(entity.persona_role)) : null,
            entity.phase,
            entity.workflow_id,
          ].filter(Boolean).join(" · ")}
        </div>
      </div>
    );
  }
  if (kind === "Person") {
    let attrs: Record<string, unknown> = {};
    try {
      const raw = entity.attributes;
      attrs = typeof raw === "string" ? JSON.parse(raw) : (raw as Record<string, unknown> ?? {});
    } catch { /* ignore */ }
    const breaches = (attrs.breach_history as Array<{ category?: string; date?: string; tier?: string }> | undefined) ?? [];
    if (breaches.length === 0) return null;
    return (
      <div style={{ marginBottom: 14 }}>
        <SectionHeader>Policy breaches ({breaches.length})</SectionHeader>
        {breaches.map((b, i) => {
          const dot = b.tier === "escalation" ? "#ef4444" : b.tier === "warning" ? "#fbbf24" : "#94a3b8";
          return (
            <div key={i} style={{
              display: "flex", gap: 8, alignItems: "center",
              padding: "4px 8px", margin: "2px 0",
              background: "rgba(15,23,42,0.4)", fontSize: 11, color: "#cbd5e1",
            }}>
              <span style={{ width: 8, height: 8, borderRadius: 4, background: dot, display: "inline-block" }} />
              <span style={{ flex: 1 }}>{b.category ?? "(unspecified)"}</span>
              <span style={{ color: "#64748b", fontSize: 10 }}>{b.date ?? ""}</span>
            </div>
          );
        })}
      </div>
    );
  }
  if (kind === "Organisation") {
    const sourceWfs = (entity.source_workflows ?? []) as string[];
    const types = new Set(sourceWfs.map((w) => w.split("-")[0]));
    const isHot = types.size >= 3 && sourceWfs.length >= 10;
    let attrs: Record<string, unknown> = {};
    try {
      const raw = entity.attributes;
      attrs = typeof raw === "string" ? JSON.parse(raw) : (raw as Record<string, unknown> ?? {});
    } catch { /* ignore */ }
    return (
      <div style={{ marginBottom: 14 }}>
        {isHot && (
          <div style={{
            background: "rgba(251,146,60,0.15)", border: "1px solid #fb923c",
            color: "#fb923c", padding: "4px 10px", marginBottom: 8,
            fontSize: 11, fontWeight: 600, borderRadius: 4,
          }}>
            🔥 Hot vendor — touches {types.size} workflow types across {sourceWfs.length} workflows
          </div>
        )}
        <SectionHeader>Risk profile</SectionHeader>
        <div style={{ fontSize: 11, color: "#cbd5e1", padding: "4px 0", lineHeight: 1.6 }}>
          {entity.risk_band !== undefined && entity.risk_band !== null && (
            <div>Risk band: <strong style={{ color: entity.risk_band === "red" ? "#ef4444" : entity.risk_band === "amber" ? "#fbbf24" : "#4ade80" }}>{String(entity.risk_band)}</strong></div>
          )}
          {entity.country !== undefined && entity.country !== null && <div>Country: {String(entity.country)}</div>}
          {entity.jurisdiction !== undefined && entity.jurisdiction !== null && <div>Jurisdiction: {String(entity.jurisdiction)}</div>}
          {attrs.creditRating !== undefined && <div>Credit rating: {String(attrs.creditRating)}</div>}
          {attrs.sanctioned !== undefined && <div>Sanctioned: <strong style={{ color: attrs.sanctioned ? "#ef4444" : "#4ade80" }}>{String(attrs.sanctioned)}</strong></div>}
        </div>
      </div>
    );
  }
  if (kind === "Money") {
    const amount = entity.amount;
    const currency = entity.currency;
    if (amount === undefined && currency === undefined) return null;
    return (
      <div style={{
        padding: "10px 12px", marginBottom: 14,
        background: "rgba(34,197,94,0.08)", border: "1px solid rgba(34,197,94,0.3)",
      }}>
        <div style={{ fontSize: 18, fontWeight: 700, color: "#22c55e" }}>
          {currency ? String(currency) : ""} {amount !== undefined ? String(amount) : ""}
        </div>
        {entity.kind !== undefined && entity.kind !== null && (
          <div style={{ fontSize: 11, color: "#94a3b8", marginTop: 4 }}>{kindToVerb(String(entity.kind))}</div>
        )}
      </div>
    );
  }
  // No narrative panel for Asset / Place / Period / Workflow.
  return null;
}

function AttributesPanel({
  entity, onOpenEntity,
}: { entity: EntityRow; onOpenEntity: (id: string) => void }) {
  const skipKeys = new Set([
    "id", "_label", "kind", "source_workflows",
    "first_seen_at", "last_seen_at",
    "verdict", "reason", "persona_role", "phase", "workflow_id",
    "amount", "currency", "risk_band", "country", "jurisdiction",
    "name", "email", "role", "market", "department",
    "label", "starts", "ends",
  ]);

  const rows: Array<[string, unknown]> = [];
  for (const [k, v] of Object.entries(entity)) {
    if (skipKeys.has(k)) continue;
    if (v === null || v === undefined || v === "") continue;
    rows.push([k, v]);
  }

  if (rows.length === 0) {
    return <Empty>No additional attributes.</Empty>;
  }

  return (
    <div style={{ fontSize: 11, fontFamily: "ui-monospace", color: "#cbd5e1", lineHeight: 1.6 }}>
      {rows.map(([k, v]) => {
        let display: string;
        if (typeof v === "string") display = v;
        else {
          try { display = JSON.stringify(v); } catch { display = String(v); }
        }
        const refs = extractEntityIdRefs(display);
        const truncated = display.length > 80 ? display.slice(0, 80) + "…" : display;
        return (
          <div key={k} style={{ padding: "2px 0" }}>
            <span style={{ color: "#64748b" }}>{k}:</span>{" "}
            {refs.length > 0
              ? <button
                  onClick={() => onOpenEntity(refs[0])}
                  style={{ background: "transparent", border: "none", color: "#22d3ee", cursor: "pointer", padding: 0, fontFamily: "inherit", fontSize: 11 }}
                >
                  {refs[0]}
                </button>
              : <span title={display}>{truncated}</span>}
          </div>
        );
      })}
    </div>
  );
}

function SectionHeader({ children, style }: { children: React.ReactNode; style?: React.CSSProperties }) {
  return (
    <div style={{
      fontSize: 10, textTransform: "uppercase", letterSpacing: 0.8,
      color: "#64748b", fontWeight: 700, marginBottom: 6, ...(style || {}),
    }}>
      {children}
    </div>
  );
}

function Empty({ children }: { children: React.ReactNode }) {
  return (
    <div style={{ color: "#475569", fontStyle: "italic", fontSize: 11, padding: "4px 0" }}>
      {children}
    </div>
  );
}

function Row({ children, onClick }: { children: React.ReactNode; onClick?: () => void }) {
  return (
    <button
      onClick={onClick}
      style={{
        display: "block", width: "100%", padding: "8px 12px", margin: "3px 0",
        background: "rgba(15,23,42,0.5)", border: "1px solid rgba(99,102,241,0.12)",
        borderRadius: 6, cursor: onClick ? "pointer" : "default", textAlign: "left",
        color: "#e2e8f0", fontFamily: "inherit", fontSize: 12,
      }}
    >
      {children}
    </button>
  );
}

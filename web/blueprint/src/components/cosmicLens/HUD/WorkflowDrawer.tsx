import { useEffect, useState } from "react";
import { ENDPOINTS } from "../lib/types";

export interface DrawerView {
  type: "function" | "workflow" | "city" | null;
  /** function key, workflow id, or city id depending on type */
  id?: string;
  label?: string;
}

interface WorkflowDrawerProps {
  view: DrawerView;
  onClose: () => void;
  onOpenWorkflow: (id: string) => void;
}

interface WorkflowSummary {
  id: string;
  workflow_type?: string;
  status?: string;
  phase?: string;
  age_s?: number;
}

interface TimelineEvent {
  ts?: number;
  type: string;
  data?: Record<string, unknown>;
}

/** Slide-in drawer for click-to-drill. */
export function WorkflowDrawer({ view, onClose, onOpenWorkflow }: WorkflowDrawerProps) {
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
          background: "linear-gradient(to left, rgba(2,6,23,0.97), rgba(15,23,42,0.95))",
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
        <DrawerContent view={view} onClose={onClose} onOpenWorkflow={onOpenWorkflow} />
      </div>
    </>
  );
}

function DrawerContent({
  view,
  onClose,
  onOpenWorkflow,
}: {
  view: DrawerView;
  onClose: () => void;
  onOpenWorkflow: (id: string) => void;
}) {
  if (view.type === "function") {
    return <FunctionView functionKey={view.id ?? ""} label={view.label} onClose={onClose} onOpenWorkflow={onOpenWorkflow} />;
  }
  if (view.type === "workflow") {
    return <WorkflowView workflowId={view.id ?? ""} onClose={onClose} />;
  }
  if (view.type === "city") {
    return <CityView cityId={view.id ?? ""} label={view.label} onClose={onClose} />;
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
        }>;
        // Build workflow_type -> function map
        const wfTypeMap = new Map<string, string>();
        for (const fn of allFns) {
          const fnK = fn.name ?? fn.key;
          if (!fnK) continue;
          for (const d of fn.ownsDomains ?? fn.domains ?? []) wfTypeMap.set(d, fnK);
        }
        // Filter workflows whose owning function == functionKey
        const filtered = allWfs.filter((wf: any) => {
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
      <DrawerHeader title={label ?? functionKey} subtitle="function" onClose={onClose} />
      <div style={{ flex: 1, overflowY: "auto", padding: "12px 20px" }}>
        {loading && <div style={{ color: "#64748b", fontStyle: "italic" }}>loading…</div>}
        {!loading && workflows.length === 0 && (
          <div style={{ color: "#64748b", fontStyle: "italic" }}>
            No in-flight workflows for this function right now.
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
              {wf.workflow_type ?? "—"} · {wf.phase ?? "—"} · {Math.round(wf.age_s ?? 0)}s old
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
        const items = (Array.isArray(data) ? data : data.events ?? []) as TimelineEvent[];
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
      <DrawerHeader title={workflowId} subtitle="workflow timeline" onClose={onClose} />
      <div style={{ flex: 1, overflowY: "auto", padding: "12px 20px" }}>
        {loading && <div style={{ color: "#64748b", fontStyle: "italic" }}>loading timeline…</div>}
        {!loading && events.length === 0 && (
          <div style={{ color: "#64748b", fontStyle: "italic" }}>
            No timeline events recorded.
          </div>
        )}
        {events.map((ev, i) => (
          <div
            key={i}
            style={{
              padding: "8px 12px",
              margin: "3px 0",
              borderLeft: `3px solid ${eventColor(ev.type)}`,
              background: "rgba(15,23,42,0.5)",
              fontSize: 12,
            }}
          >
            <div style={{ color: "#e2e8f0", fontWeight: 500 }}>{ev.type}</div>
            <div style={{ fontSize: 10, color: "#64748b", marginTop: 2 }}>
              {ev.ts ? new Date(ev.ts * 1000).toLocaleTimeString() : ""}
            </div>
            {ev.data && Object.keys(ev.data).length > 0 && (
              <div style={{ fontSize: 10, color: "#94a3b8", marginTop: 4, fontFamily: "monospace", lineHeight: 1.4 }}>
                {Object.entries(ev.data)
                  .filter(([k, v]) => v !== null && v !== undefined && k !== "ts")
                  .slice(0, 5)
                  .map(([k, v]) => (
                    <div key={k}>
                      <span style={{ color: "#64748b" }}>{k}:</span> {String(v).slice(0, 60)}
                    </div>
                  ))}
              </div>
            )}
          </div>
        ))}
      </div>
    </>
  );
}

function CityView({ cityId, label, onClose }: { cityId: string; label?: string; onClose: () => void }) {
  return (
    <>
      <DrawerHeader title={label ?? cityId} subtitle="city" onClose={onClose} />
      <div style={{ flex: 1, padding: 20, color: "#94a3b8", fontSize: 12 }}>
        <div style={{ marginBottom: 12 }}>
          City queue inspector. Phase E: live list of currently-parked rockets.
        </div>
        <div style={{ fontSize: 11, fontFamily: "monospace", color: "#64748b" }}>
          city.id = <span style={{ color: "#e2e8f0" }}>{cityId}</span>
        </div>
      </div>
    </>
  );
}

function eventColor(type: string): string {
  if (type.includes("decided") || type.includes("decision")) return "#fbbf24";
  if (type.includes("thinking")) return "#a78bfa";
  if (type.includes("completed") || type.includes("done")) return "#4ade80";
  if (type.includes("exception") || type.includes("failed")) return "#ef4444";
  if (type.includes("started") || type.includes("workflow")) return "#22d3ee";
  if (type.includes("entity")) return "#14b8a6";
  return "#64748b";
}

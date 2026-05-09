/**
 * WorkflowDrawer — slide-in panel showing one function's in-flight
 * workflows + click-through to a workflow's full timeline.
 *
 * Two modes:
 *   - mode="function" : list of in-flight workflows for the named function
 *   - mode="workflow" : full event timeline for one workflow_id
 *
 * Closes via X / ESC / click on backdrop.
 */
import { useEffect, useState } from "react";

import type { InFlightWorkflow } from "../../lib/useLiveOrg";

export type DrawerTarget =
  | { mode: "function"; key: string; display: string }
  | { mode: "workflow"; key: string };

interface Props {
  target: DrawerTarget | null;
  inFlight: InFlightWorkflow[];
  onClose: () => void;
  onPickWorkflow: (id: string) => void;
}

interface TimelineRow {
  ts: number;
  kind: string;
  label: string;
  status?: string;
  actor?: string;
  verdict?: string;
  reason?: string;
  details?: unknown;
}

const KIND_COLOR: Record<string, string> = {
  phase: "#7faed4",
  agent: "#06b6d4",
  tool: "#a78bfa",
  decision: "#5fd49d",
  human: "#fbbf24",
  system: "#9aa0a6",
};

export function WorkflowDrawer({ target, inFlight, onClose, onPickWorkflow }: Props) {
  const [timeline, setTimeline] = useState<{
    workflow: { id: string; type: string; status: string; currentPhase: string };
    timeline: TimelineRow[];
  } | null>(null);
  const [loading, setLoading] = useState(false);

  // Fetch timeline when drawer opens on a workflow.
  useEffect(() => {
    if (target?.mode !== "workflow") {
      setTimeline(null);
      return;
    }
    let cancelled = false;
    setLoading(true);
    fetch(`/api/workflows/index/timeline/${encodeURIComponent(target.key)}`)
      .then((r) => (r.ok ? r.json() : null))
      .then((d) => {
        if (cancelled) return;
        setTimeline(d);
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [target]);

  // ESC closes.
  useEffect(() => {
    if (!target) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [target, onClose]);

  if (!target) return null;

  return (
    <>
      {/* Backdrop. */}
      <div
        onClick={onClose}
        style={{
          position: "absolute",
          top: 56,
          left: 0,
          bottom: 88,
          right: 392,
          background: "rgba(6,7,10,0.18)",
          zIndex: 8,
        }}
      />

      {/* Drawer. */}
      <div
        style={{
          position: "absolute",
          top: 56,
          left: 16,
          bottom: 96,
          width: 480,
          background: "rgba(6,7,10,0.96)",
          border: "1px solid rgba(255,255,255,0.1)",
          borderRadius: 10,
          zIndex: 9,
          display: "flex",
          flexDirection: "column",
          backdropFilter: "blur(10px)",
          boxShadow: "0 12px 40px rgba(0,0,0,0.55)",
          color: "#cfd2d6",
          fontFamily: "var(--mono-family, monospace)",
        }}
      >
        <div
          style={{
            padding: "12px 16px",
            borderBottom: "1px solid rgba(255,255,255,0.08)",
            display: "flex",
            alignItems: "center",
            gap: 12,
          }}
        >
          {target.mode === "workflow" && (
            <button
              type="button"
              onClick={onClose}
              title="back"
              style={{
                background: "transparent",
                border: "none",
                color: "#9aa0a6",
                fontSize: 18,
                cursor: "pointer",
                padding: 0,
              }}
            >
              ←
            </button>
          )}
          <div style={{ flex: 1 }}>
            <div
              style={{
                fontSize: 10,
                color: "#9aa0a6",
                letterSpacing: "0.16em",
                textTransform: "uppercase",
              }}
            >
              {target.mode === "workflow" ? "WORKFLOW" : "FUNCTION"}
            </div>
            <div style={{ fontSize: 16, color: "#f5f5f7", marginTop: 2 }}>
              {target.mode === "workflow" ? target.key : target.display}
            </div>
          </div>
          <button
            type="button"
            onClick={onClose}
            title="close"
            style={{
              background: "rgba(20,22,28,0.7)",
              border: "1px solid rgba(207,210,214,0.3)",
              borderRadius: 999,
              color: "#cfd2d6",
              fontSize: 12,
              padding: "2px 10px",
              cursor: "pointer",
              fontFamily: "inherit",
            }}
          >
            ✕
          </button>
        </div>

        <div style={{ flex: 1, overflowY: "auto", padding: "8px 16px" }}>
          {target.mode === "function" && (
            <FunctionView
              fnKey={target.key}
              inFlight={inFlight.filter((w) => w.function === target.key)}
              onPickWorkflow={onPickWorkflow}
            />
          )}
          {target.mode === "workflow" && (
            <WorkflowView loading={loading} timeline={timeline} />
          )}
        </div>
      </div>
    </>
  );
}

function FunctionView({
  fnKey,
  inFlight,
  onPickWorkflow,
}: {
  fnKey: string;
  inFlight: InFlightWorkflow[];
  onPickWorkflow: (id: string) => void;
}) {
  if (inFlight.length === 0) {
    return (
      <div style={{ color: "#6b7077", padding: 12, fontSize: 12 }}>
        no in-flight workflows on {fnKey}
      </div>
    );
  }
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
      <div
        style={{
          fontSize: 10,
          color: "#9aa0a6",
          letterSpacing: "0.12em",
          textTransform: "uppercase",
          margin: "4px 4px 8px",
        }}
      >
        {inFlight.length} in flight · click any to inspect
      </div>
      {inFlight.map((w) => (
        <button
          key={w.id}
          type="button"
          onClick={() => onPickWorkflow(w.id)}
          style={{
            background: "rgba(20,22,28,0.7)",
            border: `1px solid ${
              w.status === "awaiting_hitl" ? "rgba(251,191,36,0.4)" : "rgba(95,212,157,0.3)"
            }`,
            borderRadius: 6,
            padding: "10px 12px",
            color: "#cfd2d6",
            fontFamily: "inherit",
            fontSize: 12,
            textAlign: "left",
            cursor: "pointer",
            display: "flex",
            flexDirection: "column",
            gap: 4,
          }}
        >
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "baseline" }}>
            <span style={{ color: "#f5f5f7", fontSize: 13 }}>{w.id}</span>
            <span style={{ color: "#9aa0a6", fontSize: 10 }}>{w.workflow_type}</span>
          </div>
          <div style={{ display: "flex", gap: 12, fontSize: 10, color: "#9aa0a6" }}>
            <span style={{ color: w.status === "awaiting_hitl" ? "#fbbf24" : "#5fd49d" }}>
              ● {w.status}
            </span>
            <span>{w.phase}</span>
            <span style={{ marginLeft: "auto" }}>{Math.round(w.age_s)}s old</span>
          </div>
        </button>
      ))}
    </div>
  );
}

function WorkflowView({
  loading,
  timeline,
}: {
  loading: boolean;
  timeline: {
    workflow: { id: string; type: string; status: string; currentPhase: string };
    timeline: TimelineRow[];
  } | null;
}) {
  if (loading) {
    return <div style={{ color: "#6b7077", padding: 12 }}>loading timeline…</div>;
  }
  if (!timeline) {
    return <div style={{ color: "#e87a5d", padding: 12 }}>workflow not found</div>;
  }
  const w = timeline.workflow;
  const rows = timeline.timeline;
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
      <div
        style={{
          padding: "8px 10px",
          background: "rgba(20,22,28,0.7)",
          border: "1px solid rgba(255,255,255,0.07)",
          borderRadius: 6,
          fontSize: 11,
          color: "#cfd2d6",
        }}
      >
        <div style={{ display: "flex", justifyContent: "space-between" }}>
          <span style={{ color: "#9aa0a6" }}>type</span>
          <span>{w.type}</span>
        </div>
        <div style={{ display: "flex", justifyContent: "space-between" }}>
          <span style={{ color: "#9aa0a6" }}>status</span>
          <span style={{ color: w.status === "awaiting_hitl" ? "#fbbf24" : "#5fd49d" }}>
            {w.status}
          </span>
        </div>
        <div style={{ display: "flex", justifyContent: "space-between" }}>
          <span style={{ color: "#9aa0a6" }}>phase</span>
          <span>{w.currentPhase}</span>
        </div>
      </div>
      <div
        style={{
          fontSize: 10,
          color: "#9aa0a6",
          letterSpacing: "0.12em",
          textTransform: "uppercase",
          marginTop: 6,
        }}
      >
        TIMELINE · {rows.length} events
      </div>
      <div style={{ display: "flex", flexDirection: "column", gap: 3 }}>
        {rows.length === 0 && (
          <div style={{ color: "#6b7077", padding: 10, fontSize: 11 }}>
            no events captured yet
          </div>
        )}
        {rows.map((r, i) => (
          <div
            key={i}
            style={{
              padding: "6px 8px",
              borderLeft: `3px solid ${KIND_COLOR[r.kind] ?? "#9aa0a6"}`,
              background: "rgba(255,255,255,0.02)",
              borderRadius: 3,
              fontSize: 11,
              color: "#cfd2d6",
              display: "flex",
              gap: 8,
            }}
          >
            <span style={{ color: "#6b7077", flexShrink: 0, width: 56 }}>
              {new Date(r.ts * 1000).toLocaleTimeString("en-GB", {
                hour: "2-digit",
                minute: "2-digit",
                second: "2-digit",
              })}
            </span>
            <span
              style={{
                color: KIND_COLOR[r.kind] ?? "#9aa0a6",
                flexShrink: 0,
                width: 56,
                textTransform: "uppercase",
                fontSize: 10,
              }}
            >
              {r.kind}
            </span>
            <span style={{ flex: 1, wordBreak: "break-word" }}>
              {r.label}
              {r.actor && (
                <span style={{ color: "#9aa0a6" }}> · {r.actor}</span>
              )}
              {r.verdict && (
                <span style={{ color: "#5fd49d" }}> · {r.verdict}</span>
              )}
              {r.reason && (
                <div style={{ color: "#7faed4", marginTop: 2, fontSize: 10 }}>
                  &quot;{r.reason}&quot;
                </div>
              )}
            </span>
          </div>
        ))}
      </div>
    </div>
  );
}

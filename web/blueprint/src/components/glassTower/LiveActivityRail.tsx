/**
 * LiveActivityRail — right-side scrolling feed of semantic events.
 *
 * Filtered to the events an operator actually cares about (decisions,
 * completions, exceptions, persona thinking, sub-spawns). Each row is a
 * single human-readable English sentence.
 *
 * Subscribes to the same SSE stream as the rest of the scene; keeps a
 * rolling buffer of ~80 entries; auto-scrolls to top unless user scrolls.
 */
import { useEffect, useRef, useState } from "react";
import { useObservatory } from "../../lib/useObservatory";
import type { ObservatoryEvent } from "../../lib/types";

interface Row {
  id: string;
  ts: number;
  kind: "decision" | "completed" | "exception" | "thinking" | "started" | "spawned" | "tool";
  message: string;
  workflow_id: string | null;
  function: string | null;
}

const KIND_COLOR: Record<Row["kind"], string> = {
  decision: "#a78bfa",
  completed: "#5fd49d",
  exception: "#e87a5d",
  thinking: "#fbbf24",
  started: "#06b6d4",
  spawned: "#ec4899",
  tool: "#7faed4",
};

const KIND_ICON: Record<Row["kind"], string> = {
  decision: "✓",
  completed: "▣",
  exception: "⚠",
  thinking: "⏳",
  started: "▸",
  spawned: "↳",
  tool: "🛠",
};

const PREFIX_TO_FN: Record<string, string> = {
  EXP: "finance",
  HIRE: "hr",
  TRV: "hr",
  TRVL: "hr",
  VKY: "finance",
  ONB: "hr",
  ITAR: "tech",
  CRN: "finance",
  PRR: "hr",
  API: "finance",
  POW: "finance",
  CRW: "legal",
  DPI: "legal",
  TFX: "finance",
  CMP: "marketing",
};

function fnFromWid(wid: string | null | undefined): string | null {
  if (!wid) return null;
  const m = wid.match(/^([A-Z]+)-/);
  return m ? PREFIX_TO_FN[m[1]] ?? null : null;
}

function formatRow(event: ObservatoryEvent, idx: number): Row | null {
  const wid = event.workflow_id ?? null;
  const fn = fnFromWid(wid) ?? null;
  const id = `${event.ts ?? Date.now()}-${idx}-${Math.random().toString(36).slice(2, 6)}`;
  const ts = event.ts ?? Date.now() / 1000;
  const ev = event as unknown as Record<string, unknown>;

  switch (event.type) {
    case "workflow.started":
    case "durable.workflow.started":
      return { id, ts, kind: "started", workflow_id: wid, function: fn,
        message: `${wid ?? "?"} started` };
    case "durable.workflow.completed":
    case "workflow.resolved":
      return { id, ts, kind: "completed", workflow_id: wid, function: fn,
        message: `${wid ?? "?"} completed` };
    case "workflow.exception.detected":
      return { id, ts, kind: "exception", workflow_id: wid, function: fn,
        message: `${wid ?? "?"} exception: ${(ev.reason as string) ?? "unspecified"}` };
    case "workflow.hitl.escalated":
      return { id, ts, kind: "exception", workflow_id: wid, function: fn,
        message: `${wid ?? "?"} escalated to ${(ev.persona as string) ?? "operator"}` };
    case "persona.thinking":
      return { id, ts, kind: "thinking", workflow_id: wid, function: fn,
        message: `${(ev.persona as string) ?? "?"} thinking on ${wid ?? "?"}` };
    case "persona.decided": {
      const verdict = (ev.verdict as string) ?? "?";
      return { id, ts, kind: "decision", workflow_id: wid, function: fn,
        message: `${(ev.persona as string) ?? "?"} ${verdict} ${wid ?? "?"}${
          ev.reason ? ` — ${(ev.reason as string).slice(0, 80)}` : ""
        }` };
    }
    case "decision.recorded":
      return { id, ts, kind: "decision", workflow_id: wid, function: fn,
        message: `decision recorded for ${wid ?? "?"}` };
    case "workflow.sub_spawned":
      return { id, ts, kind: "spawned", workflow_id: wid, function: fn,
        message: `${wid ?? "?"} spawned ${(ev.child_workflow_id as string) ?? "child"}` };
    case "tool.invoked":
    case "durable.executor.invoked": {
      const tool = (ev.tool as string) ?? (ev.skill as string);
      if (!tool || !wid) return null;
      return { id, ts, kind: "tool", workflow_id: wid, function: fn,
        message: `${tool} on ${wid}` };
    }
    default:
      return null;
  }
}

const MAX_ROWS = 80;

const KIND_LABEL: Record<Row["kind"], string> = {
  decision: "decisions",
  completed: "done",
  exception: "exceptions",
  thinking: "thinking",
  started: "started",
  spawned: "spawned",
  tool: "tools",
};

const ALL_KINDS: Row["kind"][] = ["decision", "thinking", "completed", "exception", "started", "spawned", "tool"];
const DEFAULT_ENABLED: Set<Row["kind"]> = new Set([
  "decision",
  "thinking",
  "completed",
  "exception",
  "started",
  "spawned",
]);

export function LiveActivityRail() {
  const [rows, setRows] = useState<Row[]>([]);
  const [enabledKinds, setEnabledKinds] = useState<Set<Row["kind"]>>(DEFAULT_ENABLED);
  const counterRef = useRef(0);
  const scrollRef = useRef<HTMLDivElement>(null);
  const stickToTopRef = useRef(true);

  useObservatory({
    bufferSize: 1,
    onEvent: (event) => {
      counterRef.current = (counterRef.current + 1) | 0;
      const row = formatRow(event, counterRef.current);
      if (!row) return;
      setRows((cur) => {
        const next = [row, ...cur];
        if (next.length > MAX_ROWS) next.length = MAX_ROWS;
        return next;
      });
    },
  });

  useEffect(() => {
    if (!stickToTopRef.current) return;
    const el = scrollRef.current;
    if (el) el.scrollTop = 0;
  }, [rows]);

  function onScroll() {
    const el = scrollRef.current;
    if (!el) return;
    stickToTopRef.current = el.scrollTop < 8;
  }

  function toggleKind(kind: Row["kind"]) {
    setEnabledKinds((cur) => {
      const next = new Set(cur);
      if (next.has(kind)) next.delete(kind);
      else next.add(kind);
      return next;
    });
  }

  const filtered = rows.filter((r) => enabledKinds.has(r.kind));

  return (
    <div
      style={{
        position: "absolute",
        top: 56,
        right: 16,
        bottom: 96,
        width: 360,
        background: "rgba(6,7,10,0.78)",
        border: "1px solid rgba(255,255,255,0.07)",
        borderRadius: 10,
        zIndex: 6,
        display: "flex",
        flexDirection: "column",
        backdropFilter: "blur(8px)",
        boxShadow: "0 12px 40px rgba(0,0,0,0.45)",
      }}
    >
      <div
        style={{
          padding: "10px 14px",
          borderBottom: "1px solid rgba(255,255,255,0.08)",
          fontFamily: "var(--mono-family, monospace)",
          fontSize: 10,
          letterSpacing: "0.16em",
          color: "#9aa0a6",
          textTransform: "uppercase",
          display: "flex",
          alignItems: "center",
          gap: 10,
        }}
      >
        <span
          style={{
            width: 8,
            height: 8,
            borderRadius: 999,
            background: "#5fd49d",
            boxShadow: "0 0 8px #5fd49d",
            display: "inline-block",
          }}
        />
        Live activity · {filtered.length} / {rows.length}
      </div>

      {/* Filter chips. */}
      <div
        style={{
          padding: "6px 10px 8px",
          borderBottom: "1px solid rgba(255,255,255,0.06)",
          display: "flex",
          flexWrap: "wrap",
          gap: 4,
        }}
      >
        {ALL_KINDS.map((k) => {
          const enabled = enabledKinds.has(k);
          return (
            <button
              key={k}
              type="button"
              onClick={() => toggleKind(k)}
              style={{
                background: enabled ? `${KIND_COLOR[k]}26` : "rgba(20,22,28,0.4)",
                border: `1px solid ${enabled ? KIND_COLOR[k] : "rgba(255,255,255,0.07)"}80`,
                borderRadius: 999,
                padding: "2px 8px",
                fontFamily: "var(--mono-family, monospace)",
                fontSize: 9,
                letterSpacing: "0.08em",
                textTransform: "uppercase",
                color: enabled ? KIND_COLOR[k] : "#6b7077",
                cursor: "pointer",
              }}
            >
              {KIND_ICON[k]} {KIND_LABEL[k]}
            </button>
          );
        })}
      </div>

      <div
        ref={scrollRef}
        onScroll={onScroll}
        style={{
          flex: 1,
          overflowY: "auto",
          padding: 8,
          fontFamily: "var(--mono-family, monospace)",
          fontSize: 11,
          color: "#cfd2d6",
          lineHeight: 1.5,
        }}
      >
        {filtered.length === 0 ? (
          <div style={{ padding: 14, color: "#6b7077", fontSize: 11 }}>
            waiting for events…
          </div>
        ) : (
          filtered.map((r) => (
            <div
              key={r.id}
              style={{
                display: "flex",
                gap: 8,
                padding: "4px 8px",
                borderLeft: `3px solid ${KIND_COLOR[r.kind]}`,
                marginBottom: 2,
                background: "rgba(255,255,255,0.02)",
                borderRadius: 3,
              }}
            >
              <span style={{ color: "#6b7077", flexShrink: 0, width: 56 }}>
                {new Date(r.ts * 1000).toLocaleTimeString("en-GB", {
                  hour: "2-digit",
                  minute: "2-digit",
                  second: "2-digit",
                })}
              </span>
              <span style={{ color: KIND_COLOR[r.kind], flexShrink: 0, width: 14 }}>
                {KIND_ICON[r.kind]}
              </span>
              <span style={{ flex: 1, wordBreak: "break-word" }}>{r.message}</span>
            </div>
          ))
        )}
      </div>
    </div>
  );
}

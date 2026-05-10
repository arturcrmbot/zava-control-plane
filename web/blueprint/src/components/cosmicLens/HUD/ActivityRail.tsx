import { useEffect, useRef, useState } from "react";
import type { CosmicFlash } from "../lib/types";
import { labelForCapability, labelForEntity } from "../lib/labels";

interface ActivityRailProps {
  flashesRef: React.MutableRefObject<{ buffer: CosmicFlash[]; version: number }>;
  mode: "capabilities" | "entities";
}

interface RailEntry {
  id: string;
  ts: number;
  type: string;
  category: string; // for filter chip
  title: string;
  workflow_id?: string;
}

const FILTERS = [
  { key: "decision", label: "decisions", color: "#fbbf24", default: true },
  { key: "thinking", label: "thinking", color: "#a78bfa", default: true },
  { key: "done", label: "done", color: "#4ade80", default: true },
  { key: "exception", label: "exceptions", color: "#ef4444", default: true },
  { key: "started", label: "started", color: "#22d3ee", default: true },
  { key: "spawned", label: "spawned", color: "#ec4899", default: true },
  { key: "tool", label: "tools", color: "#0ea5e9", default: false },
  { key: "entity", label: "entities", color: "#14b8a6", default: true },
] as const;

/** Right-edge live event feed with filter chips. */
export function ActivityRail({ flashesRef, mode }: ActivityRailProps) {
  const [entries, setEntries] = useState<RailEntry[]>([]);
  const [enabled, setEnabled] = useState<Set<string>>(
    () => new Set(FILTERS.filter((f) => f.default).map((f) => f.key)),
  );
  const lastVersionRef = useRef(0);
  const counterRef = useRef(0);

  useEffect(() => {
    const interval = setInterval(() => {
      const ref = flashesRef.current;
      if (ref.version === lastVersionRef.current) return;
      const flushed = ref.buffer.slice(); // copy
      lastVersionRef.current = ref.version;

      const newEntries: RailEntry[] = [];
      for (const flash of flushed) {
        const cat = categorise(flash.type);
        if (!cat) continue;
        const title =
          mode === "entities" ? labelForEntity(flash) : labelForCapability(flash);
        counterRef.current += 1;
        newEntries.push({
          id: `e-${counterRef.current}`,
          ts: flash.ts,
          type: flash.type,
          category: cat,
          title: prettyEntry(flash, title),
          workflow_id: flash.workflow_id,
        });
      }

      if (newEntries.length === 0) return;
      setEntries((prev) => {
        const merged = [...newEntries.reverse(), ...prev];
        if (merged.length > 200) merged.length = 200;
        return merged;
      });
    }, 700);
    return () => clearInterval(interval);
  }, [flashesRef, mode]);

  const visible = entries.filter((e) => enabled.has(e.category));

  return (
    <div
      style={{
        position: "absolute",
        top: 70,
        right: 0,
        bottom: 0,
        width: 320,
        background: "linear-gradient(to left, rgba(2,6,23,0.85), rgba(2,6,23,0.55) 60%, transparent)",
        color: "#e2e8f0",
        fontFamily: "ui-sans-serif, system-ui",
        fontSize: 12,
        display: "flex",
        flexDirection: "column",
        zIndex: 15,
        pointerEvents: "auto",
      }}
    >
      <div
        style={{
          padding: "10px 14px 8px",
          borderBottom: "1px solid rgba(148,163,184,0.12)",
        }}
      >
        <div style={{ color: "#94a3b8", fontSize: 10, textTransform: "uppercase", letterSpacing: 1, marginBottom: 6 }}>
          Live activity
        </div>
        <div style={{ display: "flex", flexWrap: "wrap", gap: 4 }}>
          {FILTERS.map((f) => {
            const active = enabled.has(f.key);
            return (
              <button
                key={f.key}
                onClick={() => {
                  const next = new Set(enabled);
                  if (active) next.delete(f.key);
                  else next.add(f.key);
                  setEnabled(next);
                }}
                style={{
                  padding: "2px 8px",
                  fontSize: 10,
                  background: active ? `${f.color}20` : "rgba(30,41,59,0.5)",
                  color: active ? f.color : "#64748b",
                  border: `1px solid ${active ? f.color + "60" : "rgba(148,163,184,0.15)"}`,
                  borderRadius: 999,
                  cursor: "pointer",
                  fontWeight: 500,
                }}
              >
                {f.label}
              </button>
            );
          })}
        </div>
      </div>

      <div
        style={{
          flex: 1,
          overflowY: "auto",
          padding: "8px 14px",
        }}
      >
        {visible.length === 0 && (
          <div style={{ color: "#475569", padding: "20px 4px", fontStyle: "italic", fontSize: 11 }}>
            No activity yet. Try the ⚡ BURST button.
          </div>
        )}
        {visible.slice(0, 80).map((e) => (
          <div
            key={e.id}
            style={{
              padding: "5px 0",
              borderBottom: "1px solid rgba(148,163,184,0.05)",
              display: "flex",
              gap: 8,
              alignItems: "flex-start",
            }}
          >
            <div
              style={{
                marginTop: 5,
                width: 6,
                height: 6,
                borderRadius: "50%",
                background: categoryColor(e.category),
                boxShadow: `0 0 6px ${categoryColor(e.category)}`,
                flexShrink: 0,
              }}
            />
            <div style={{ flex: 1, minWidth: 0 }}>
              <div
                style={{
                  color: "#e2e8f0",
                  fontSize: 11,
                  lineHeight: 1.35,
                  overflow: "hidden",
                  textOverflow: "ellipsis",
                  whiteSpace: "nowrap",
                }}
                title={e.title}
              >
                {e.title}
              </div>
              {e.workflow_id && (
                <div style={{ color: "#64748b", fontSize: 9, marginTop: 1 }}>
                  {e.workflow_id}
                </div>
              )}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

function categorise(type: string): string | null {
  if (type === "persona.thinking") return "thinking";
  if (type === "persona.decided" || type === "decision.recorded" || type === "ambient.decided")
    return "decision";
  if (type.includes("completed") || type === "tool.completed") return "done";
  if (type.includes("exception") || type === "entity.write.failed") return "exception";
  if (type.includes("started") || type === "workflow.started") return "started";
  if (type === "workflow.sub_spawned") return "spawned";
  if (type === "tool.invoked") return "tool";
  if (type.startsWith("entity.")) return "entity";
  return null;
}

function categoryColor(category: string): string {
  const f = FILTERS.find((x) => x.key === category);
  return f?.color ?? "#94a3b8";
}

function prettyEntry(flash: CosmicFlash, base: string): string {
  // Some events have workflow id but the label doesn't include it; prepend.
  const wid = flash.workflow_id ? `${flash.workflow_id}: ` : "";
  return `${wid}${base}`;
}

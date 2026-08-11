import { useEffect, useRef, useState } from "react";
import type { CosmicFlash, FunctionMeta, WorkflowMoonData } from "../lib/types";
import { labelForCapability, labelForEntity } from "../lib/labels";
import { HotFunctions } from "./HotFunctions";
import { useReplayMode } from "../../../lib/useReplayMode";

interface ActivityRailProps {
  flashesRef: React.MutableRefObject<{ buffer: CosmicFlash[]; version: number }>;
  mode: "capabilities" | "entities";
  inFlight?: WorkflowMoonData[];
  functions?: FunctionMeta[];
  onFunctionClick?: (key: string, label: string) => void;
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
  { key: "decision", label: "Decisions", color: "#fbbf24", default: true },
  { key: "thinking", label: "People reviewing", color: "#a78bfa", default: true },
  { key: "done", label: "Completed", color: "#4ade80", default: true },
  { key: "exception", label: "Problems", color: "#ef4444", default: true },
  { key: "started", label: "Started", color: "#22d3ee", default: true },
  { key: "spawned", label: "New cases", color: "#ec4899", default: true },
  { key: "tool", label: "System tools", color: "#0ea5e9", default: false },
  { key: "entity", label: "Records", color: "#14b8a6", default: false },
] as const;

/** Right-edge live event feed with filter chips. */
export function ActivityRail({
  flashesRef,
  mode,
  inFlight,
  functions,
  onFunctionClick,
}: ActivityRailProps) {
  const [entries, setEntries] = useState<RailEntry[]>([]);
  const [enabled, setEnabled] = useState<Set<string>>(
    () => new Set(FILTERS.filter((f) => f.default).map((f) => f.key)),
  );
  const { isReplay } = useReplayMode();
  // When user switches to Entities mode, auto-enable the entity chip so the
  // rail surfaces the right signal for that view. We still let users override.
  useEffect(() => {
    if (mode === "entities") {
      setEnabled((prev) => {
        if (prev.has("entity")) return prev;
        const next = new Set(prev);
        next.add("entity");
        return next;
      });
    } else {
      setEnabled((prev) => {
        if (!prev.has("entity")) return prev;
        const next = new Set(prev);
        next.delete("entity");
        return next;
      });
    }
  }, [mode]);
  const lastVersionRef = useRef(0);
  const counterRef = useRef(0);

  useEffect(() => {
    const interval = setInterval(() => {
      const ref = flashesRef.current;
      if (ref.version === lastVersionRef.current) return;
      // Only process events added since the last cycle. Buffer is a ring
      // capped at FLASH_BUFFER_SIZE; version increments per push so the
      // delta against version IS the count of new pushes (capped by
      // current buffer length when delta exceeds it).
      const delta = ref.version - lastVersionRef.current;
      const startIdx = Math.max(0, ref.buffer.length - delta);
      const flushed = ref.buffer.slice(startIdx);
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
        // Coalesce passes:
        //  (a) consecutive same-type same-category WITHOUT workflow_id
        //      (entity.upserted noise) — collapse via "(xN)".
        //  (b) consecutive same-workflow_id rows — workflows often emit
        //      bursts of started/completed pairs as steps progress, and
        //      the rail filled up with the same WF-id repeating 9 times.
        //      Collapse any two adjacent rows with the same workflow_id
        //      into a single row showing the most recent event + a
        //      "(xN events)" count suffix.
        const merged: RailEntry[] = [];
        const all = [...newEntries.reverse(), ...prev];
        for (const e of all) {
          const last = merged[merged.length - 1];
          // (a) noise dedup
          if (
            last &&
            last.type === e.type &&
            last.category === e.category &&
            !last.workflow_id &&
            !e.workflow_id
          ) {
            const m = last.title.match(/^(.+?)(?:\s+\(x(\d+)\))?$/);
            const base = m?.[1] ?? last.title;
            const n = (m?.[2] ? parseInt(m[2], 10) : 1) + 1;
            last.title = `${base} (x${n})`;
            continue;
          }
          // (b) same-workflow_id burst dedup. We iterate newest-first so
          //    `last` is the more-recent event; e is the older one. Bump
          //    the count on `last` but DO NOT overwrite its title/type —
          //    that would replace e.g. "step.completed (newer)" with
          //    "workflow.started (older)" and the rail would forever read
          //    "workflow.started" no matter how much real progress
          //    happened.
          if (
            last &&
            last.workflow_id &&
            e.workflow_id &&
            last.workflow_id === e.workflow_id
          ) {
            const m = last.title.match(/^(.+?)(?:\s+\(x(\d+)\))?$/);
            const baseTitle = m?.[1] ?? last.title;
            const baseN = m?.[2] ? parseInt(m[2], 10) : 1;
            last.title = `${baseTitle} (x${baseN + 1})`;
            continue;
          }
          merged.push(e);
        }
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
          {isReplay ? "Recorded activity" : "Live activity"}
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
            Waiting for organisational activity to arrive.
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
      {inFlight && functions && (
        <HotFunctions
          inFlight={inFlight}
          functions={functions}
          onFunctionClick={onFunctionClick}
        />
      )}
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

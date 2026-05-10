import { useMemo } from "react";
import type { FunctionMeta, WorkflowMoonData } from "../lib/types";
import { colorForFunction } from "../lib/colors";
import {
  buildWorkflowTypeToFunction,
  resolveFunction,
  workflowTypeFromId,
} from "../lib/workflowFunction";

interface HotFunctionsProps {
  inFlight: WorkflowMoonData[];
  functions: FunctionMeta[];
  /** Optional click handler to drill into a function. */
  onFunctionClick?: (key: string, label: string) => void;
}

/**
 * Bottom-of-rail leaderboard: top 6 functions by current in-flight load,
 * with bars proportional to load. Instant operator readout of where the
 * work is concentrated.
 */
export function HotFunctions({ inFlight, functions, onFunctionClick }: HotFunctionsProps) {
  const ranked = useMemo(() => {
    const wfTypeMap = buildWorkflowTypeToFunction(functions);
    const counts = new Map<string, number>();
    for (const wf of inFlight) {
      const wfType = wf.workflow_type || workflowTypeFromId(wf.id) || "";
      const fn = resolveFunction({ ...wf, workflow_type: wfType }, wfTypeMap);
      counts.set(fn, (counts.get(fn) ?? 0) + 1);
    }
    const fnLabel = new Map<string, string>();
    for (const f of functions) {
      const k = f.name ?? f.key ?? "";
      if (k) fnLabel.set(k, f.display ?? f.label ?? k);
    }
    const arr = Array.from(counts.entries()).map(([k, n]) => ({
      key: k,
      label: fnLabel.get(k) ?? k,
      count: n,
      color: colorForFunction(k),
    }));
    arr.sort((a, b) => b.count - a.count);
    return arr.slice(0, 6);
  }, [inFlight, functions]);

  if (ranked.length === 0) return null;
  const max = ranked[0].count || 1;

  return (
    <div
      style={{
        borderTop: "1px solid rgba(148,163,184,0.12)",
        padding: "10px 14px 12px",
        background: "rgba(2,6,23,0.55)",
      }}
    >
      <div
        style={{
          color: "#94a3b8",
          fontSize: 10,
          textTransform: "uppercase",
          letterSpacing: 1,
          marginBottom: 8,
          display: "flex",
          alignItems: "center",
          gap: 6,
        }}
      >
        <span>Hot functions</span>
        <span style={{ color: "#475569", fontSize: 9 }}>· in-flight</span>
      </div>
      <div style={{ display: "flex", flexDirection: "column", gap: 5 }}>
        {ranked.map((r) => (
          <div
            key={r.key}
            onClick={() => onFunctionClick?.(r.key, r.label)}
            style={{
              display: "flex",
              alignItems: "center",
              gap: 8,
              cursor: onFunctionClick ? "pointer" : "default",
            }}
          >
            <span
              style={{
                color: r.color,
                fontSize: 10,
                fontWeight: 600,
                width: 90,
                whiteSpace: "nowrap",
                overflow: "hidden",
                textOverflow: "ellipsis",
                textTransform: "uppercase",
                letterSpacing: 0.4,
              }}
              title={r.label}
            >
              {r.label}
            </span>
            <div
              style={{
                flex: 1,
                height: 6,
                background: "rgba(30,41,59,0.6)",
                borderRadius: 999,
                overflow: "hidden",
                position: "relative",
              }}
            >
              <div
                style={{
                  position: "absolute",
                  left: 0,
                  top: 0,
                  bottom: 0,
                  width: `${(r.count / max) * 100}%`,
                  background: `linear-gradient(90deg, ${r.color}cc, ${r.color}88)`,
                  boxShadow: `0 0 6px ${r.color}66`,
                  transition: "width 0.4s ease-out",
                }}
              />
            </div>
            <span
              style={{
                color: "#cbd5e1",
                fontSize: 10,
                fontVariantNumeric: "tabular-nums",
                fontWeight: 600,
                minWidth: 32,
                textAlign: "right",
              }}
            >
              {r.count}
            </span>
          </div>
        ))}
      </div>
    </div>
  );
}

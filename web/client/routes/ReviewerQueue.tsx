// src/client/routes/ReviewerQueue.tsx
//
// SSC Reviewer queue (AC #8). Composes existing UI primitives — no new
// components introduced. Reads /api/exceptions via the existing useExceptions
// hook, sorts by severity (critical/high/medium first) then by created_at
// (oldest first → SLA-driven), and renders one card per item with the
// fleet-manager-composed recommendation pre-selected.
import { Link } from "react-router-dom";
import { useExceptions } from "../hooks/useExceptions";
import type { Exception as ExceptionT } from "@shared/types";

const SEVERITY_RANK: Record<string, number> = { critical: 0, high: 1, medium: 2 };

function severityBadgeClass(s: ExceptionT["severity"]): string {
  if (s === "critical") return "bg-red-50 text-red-700";
  if (s === "high") return "bg-amber-50 text-amber-700";
  return "bg-slate-50 text-slate-600";
}

export default function ReviewerQueue() {
  const { items } = useExceptions();
  const queue = items
    .filter((e) => !e.resolvedAt)
    .slice()
    .sort((a, b) => {
      const sa = SEVERITY_RANK[a.severity] ?? 9;
      const sb = SEVERITY_RANK[b.severity] ?? 9;
      if (sa !== sb) return sa - sb;
      return a.createdAt - b.createdAt;
    });

  return (
    <div className="space-y-4">
      <div>
        <div className="text-xl font-semibold text-slate-900">SSC Reviewer Queue</div>
        <div className="text-xs text-slate-500">
          {queue.length} item{queue.length === 1 ? "" : "s"} awaiting your decision
        </div>
      </div>

      {queue.length === 0 && (
        <div className="panel panel-body text-xs text-slate-500 italic">
          No items awaiting reviewer decision.
        </div>
      )}

      <div className="panel">
        <div className="panel-body divide-y divide-slate-200">
          {queue.map((e) => (
            <Link
              key={e.id}
              to={`/workflows/${e.workflowId}`}
              className="block py-3 hover:bg-slate-50"
            >
              <div className="flex items-center gap-3 text-sm">
                <span className="font-mono text-slate-900">{e.workflowId}</span>
                <span
                  className={`text-[10px] uppercase tracking-wide px-1.5 py-0.5 rounded ${severityBadgeClass(
                    e.severity,
                  )}`}
                >
                  {e.severity}
                </span>
                <span className="text-xs text-slate-500 capitalize">{e.category.replace(/-/g, " ")}</span>
                <span className="ml-auto text-[11px] text-slate-500">
                  {new Date(e.createdAt * 1000).toLocaleTimeString()}
                </span>
              </div>
              <div className="text-xs text-slate-700 mt-1">{e.summary}</div>
              {e.recommendation && (
                <div className="text-xs text-emerald-700 mt-1 font-medium">
                  → {e.recommendation}
                </div>
              )}
              {e.options && e.options.length > 0 && (
                <div className="text-[11px] text-slate-500 mt-1">
                  {e.options.length} option{e.options.length === 1 ? "" : "s"} ·{" "}
                  {e.options.map((o) => o.label).join(" / ")}
                </div>
              )}
            </Link>
          ))}
        </div>
      </div>
    </div>
  );
}

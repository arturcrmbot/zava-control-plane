// src/client/routes/ReviewerQueue.tsx
//
// SSC Reviewer queue (AC #8). Each row shows the receipt thumbnail,
// claim summary, fleet-manager-composed recommendation, and inline
// action buttons (Approve / Request docs / Escalate / Reject) that
// drive /api/exceptions/{id}/resolve.
import { useState } from "react";
import { Link } from "react-router-dom";
import { useExceptions } from "../hooks/useExceptions";
import { useWorkflows } from "../hooks/useWorkflows";
import type { Exception as ExceptionT, Workflow } from "@shared/types";

const SEVERITY_RANK: Record<string, number> = { critical: 0, high: 1, medium: 2 };

function severityBadgeClass(s: ExceptionT["severity"]): string {
  if (s === "critical") return "bg-red-50 text-red-700 ring-1 ring-red-200";
  if (s === "high") return "bg-amber-50 text-amber-700 ring-1 ring-amber-200";
  return "bg-slate-50 text-slate-600 ring-1 ring-slate-200";
}

function verdictBadgeClass(v: Workflow["verdict"] | undefined): string {
  if (v === "red") return "bg-red-50 text-red-700 ring-1 ring-red-200";
  if (v === "amber") return "bg-amber-50 text-amber-700 ring-1 ring-amber-200";
  if (v === "green") return "bg-emerald-50 text-emerald-700 ring-1 ring-emerald-200";
  return "bg-slate-50 text-slate-600 ring-1 ring-slate-200";
}

function fmtAge(seconds: number): string {
  const ageMin = (Date.now() / 1000 - seconds) / 60;
  if (ageMin < 1) return "just now";
  if (ageMin < 60) return `${Math.round(ageMin)}m ago`;
  const ageHr = ageMin / 60;
  if (ageHr < 24) return `${ageHr.toFixed(1)}h ago`;
  return `${Math.round(ageHr / 24)}d ago`;
}

const ACTION_LABEL: Record<string, string> = {
  approve: "Approve",
  "request-info": "Request docs",
  escalate: "Escalate L2",
  reject: "Reject",
};
const ACTION_ORDER = ["approve", "request-info", "escalate", "reject"] as const;
type ActionId = typeof ACTION_ORDER[number];

const ACTION_BUTTON_CLASS: Record<ActionId, string> = {
  approve: "bg-emerald-600 hover:bg-emerald-700 text-white",
  "request-info": "bg-white text-slate-700 ring-1 ring-slate-300 hover:bg-slate-50",
  escalate: "bg-white text-amber-700 ring-1 ring-amber-300 hover:bg-amber-50",
  reject: "bg-white text-red-700 ring-1 ring-red-300 hover:bg-red-50",
};

function ReceiptThumb({ claimId, flavour }: { claimId?: string; flavour?: string }) {
  const [errored, setErrored] = useState(false);
  if (!claimId) {
    return (
      <div className="w-16 h-20 bg-slate-100 rounded border border-slate-200 flex items-center justify-center text-[9px] text-slate-400 text-center px-1">
        no claim
      </div>
    );
  }
  if (errored || flavour === "missing-receipt") {
    return (
      <div className="w-16 h-20 bg-amber-50 border border-dashed border-amber-300 rounded flex items-center justify-center text-[9px] text-amber-700 text-center px-1 leading-tight">
        receipt<br />missing
      </div>
    );
  }
  return (
    <img
      src={`/api/receipts/${claimId}.png`}
      alt={`receipt ${claimId}`}
      onError={() => setErrored(true)}
      className="w-16 h-20 object-cover bg-white rounded border border-slate-200"
    />
  );
}

export default function ReviewerQueue() {
  const { items, refresh } = useExceptions();
  const workflows = useWorkflows();
  const wfById = new Map(workflows.map((w) => [w.id, w]));
  const [resolving, setResolving] = useState<Record<string, boolean>>({});

  const queue = items
    .filter((e) => !e.resolvedAt)
    .slice()
    .sort((a, b) => {
      const sa = SEVERITY_RANK[a.severity] ?? 9;
      const sb = SEVERITY_RANK[b.severity] ?? 9;
      if (sa !== sb) return sa - sb;
      return a.createdAt - b.createdAt;
    });

  const act = async (exceptionId: string, action: ActionId) => {
    setResolving((r) => ({ ...r, [exceptionId]: true }));
    try {
      const r = await fetch(`/api/exceptions/${exceptionId}/resolve`, {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ resolution: action, resolvedBy: "reviewer@wpp" }),
      });
      if (!r.ok) {
        console.error("resolve failed", await r.text());
      }
      await refresh();
    } finally {
      setResolving((r) => ({ ...r, [exceptionId]: false }));
    }
  };

  return (
    <div className="space-y-4">
      <div className="flex items-baseline justify-between">
        <div>
          <div className="text-xl font-semibold text-slate-900">SSC Reviewer Queue</div>
          <div className="text-xs text-slate-500">
            {queue.length} item{queue.length === 1 ? "" : "s"} awaiting your decision · sorted by severity then SLA
          </div>
        </div>
      </div>

      {queue.length === 0 && (
        <div className="panel panel-body text-xs text-slate-500 italic">
          No items awaiting reviewer decision.
        </div>
      )}

      <div className="space-y-3">
        {queue.map((e) => {
          const w = wfById.get(e.workflowId);
          const claim = w?.claim;
          const isResolving = !!resolving[e.id];
          return (
            <div
              key={e.id}
              className="panel panel-body flex items-start gap-4 hover:border-slate-300 transition"
            >
              <ReceiptThumb claimId={claim?.claimId} flavour={claim?.receiptMismatchFlavour} />
              <div className="flex-1 min-w-0 space-y-2">
                <div className="flex items-center gap-2 flex-wrap">
                  <Link
                    to={`/workflows/${e.workflowId}`}
                    className="font-mono text-sm text-slate-900 hover:text-blue-700"
                  >
                    {e.workflowId}
                  </Link>
                  {claim && (
                    <span className="text-xs text-slate-500">
                      · {claim.claimId} · {claim.employeeId}
                    </span>
                  )}
                  <span className={`text-[10px] uppercase tracking-wide px-1.5 py-0.5 rounded font-medium ${severityBadgeClass(e.severity)}`}>
                    {e.severity}
                  </span>
                  {w?.verdict && (
                    <span className={`text-[10px] uppercase tracking-wide px-1.5 py-0.5 rounded font-medium ${verdictBadgeClass(w.verdict)}`}>
                      {w.verdict}
                    </span>
                  )}
                  <span className="ml-auto text-[11px] text-slate-500">{fmtAge(e.createdAt)}</span>
                </div>
                {claim && (
                  <div className="text-xs text-slate-700">
                    <span className="font-semibold text-slate-900">{claim.currency} {claim.amount.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}</span>
                    {" · "}
                    <span className="capitalize">{claim.category}</span>
                    {" · "}
                    <span>{claim.vendor}</span>
                    {claim.attendees > 1 && <span className="text-slate-500"> · {claim.attendees} attendees</span>}
                    <span className="text-slate-500"> · {claim.market} · via {claim.emsSource}</span>
                  </div>
                )}
                <div className="text-xs text-slate-700">{e.summary}</div>
                {e.recommendation && (
                  <div className="text-xs text-emerald-700 font-medium">
                    → {e.recommendation}
                  </div>
                )}
                <div className="flex gap-2 pt-1">
                  {ACTION_ORDER.map((a) => (
                    <button
                      key={a}
                      type="button"
                      disabled={isResolving}
                      onClick={() => void act(e.id, a)}
                      className={`text-xs px-3 py-1.5 rounded font-medium transition disabled:opacity-50 disabled:cursor-not-allowed ${ACTION_BUTTON_CLASS[a]}`}
                    >
                      {ACTION_LABEL[a]}
                    </button>
                  ))}
                </div>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}

// src/client/components/WorkflowCard.tsx
import type { Workflow } from "@shared/types";
import { Link } from "react-router-dom";
import { PHASE_ORDER, EXPENSE_PHASE_ORDER, HIRING_PHASE_ORDER } from "@shared/types";
import { AlertTriangle, Clock } from "lucide-react";

const STATUS_COLOR: Record<Workflow["status"], string> = {
  in_progress: "bg-blue-50 dark:bg-blue-950/30 text-blue-700 dark:text-blue-300 ring-1 ring-blue-200",
  awaiting_hitl: "bg-amber-50 dark:bg-amber-950/30 text-amber-700 dark:text-amber-400 ring-1 ring-amber-200",
  completed: "bg-emerald-50 dark:bg-emerald-950/30 text-emerald-700 dark:text-emerald-400 ring-1 ring-emerald-200",
  failed: "bg-red-50 dark:bg-red-950/30 text-red-700 dark:text-red-400 ring-1 ring-red-200",
};

const STATUS_LABEL: Record<Workflow["status"], string> = {
  in_progress: "in flight",
  awaiting_hitl: "needs review",
  completed: "done",
  failed: "failed",
};

const VERDICT_COLOR: Record<NonNullable<Workflow["verdict"]>, string> = {
  green: "bg-emerald-100 text-emerald-700 dark:text-emerald-400",
  amber: "bg-amber-100 text-amber-700 dark:text-amber-400",
  red: "bg-red-100 text-red-700 dark:text-red-400",
};

const PROGRESS_BAR: Record<Workflow["status"], string> = {
  in_progress: "bg-blue-500",
  awaiting_hitl: "bg-amber-500",
  completed: "bg-emerald-500",
  failed: "bg-red-500",
};

const DOMAIN_LABEL: Record<string, string> = {
  "expense-claim": "expense",
  "hiring": "hiring",
  "invoice-p2p": "invoice",
  "travel-preapproval": "travel",
  "vendor-kyc": "kyc",
  "employee-onboarding": "onboarding",
  "it-access-request": "it access",
  "contract-renewal": "contract",
  "perf-review": "perf review",
  "ap-invoice": "ap",
  "purchase-order": "po",
  "contract-review": "contract review",
  "privacy-dpia": "dpia",
  "treasury-fx": "treasury",
  "creative-campaign": "creative",
};

const DOMAIN_COLOR: Record<string, string> = {
  "expense-claim": "bg-sky-50 text-sky-700 ring-1 ring-sky-200",
  "hiring": "bg-violet-50 text-violet-700 ring-1 ring-violet-200",
  "invoice-p2p": "bg-slate-50 dark:bg-slate-800 text-slate-600 dark:text-slate-300 ring-1 ring-slate-200 dark:ring-slate-700",
  "travel-preapproval": "bg-cyan-50 text-cyan-700 ring-1 ring-cyan-200",
  "vendor-kyc": "bg-orange-50 text-orange-700 ring-1 ring-orange-200",
  "employee-onboarding": "bg-emerald-50 dark:bg-emerald-950/30 text-emerald-700 dark:text-emerald-400 ring-1 ring-emerald-200",
  "it-access-request": "bg-indigo-50 text-indigo-700 ring-1 ring-indigo-200",
  "contract-renewal": "bg-yellow-50 text-yellow-700 ring-1 ring-yellow-200",
  "perf-review": "bg-pink-50 text-pink-700 ring-1 ring-pink-200",
  "ap-invoice": "bg-stone-50 text-stone-700 ring-1 ring-stone-200",
  "purchase-order": "bg-teal-50 text-teal-700 ring-1 ring-teal-200",
  "contract-review": "bg-amber-50 dark:bg-amber-950/30 text-amber-700 dark:text-amber-400 ring-1 ring-amber-200",
  "privacy-dpia": "bg-red-50 dark:bg-red-950/30 text-red-700 dark:text-red-400 ring-1 ring-red-200",
  "treasury-fx": "bg-lime-50 text-lime-700 ring-1 ring-lime-200",
  "creative-campaign": "bg-fuchsia-50 text-fuchsia-700 ring-1 ring-fuchsia-200",
};

function hiringSubtitle(metadata: Record<string, unknown> | undefined): string {
  const name = (metadata?.candidate_name as string | undefined) ?? "";
  const role = (metadata?.role_family as string | undefined) ?? "";
  const jur = (metadata?.jurisdiction as string | undefined) ?? "";
  const parts = [name, role, jur].filter(Boolean);
  return parts.join(" · ") || "—";
}

function fmtSlaRemaining(slaDueAt: number): { text: string; warn: boolean } | null {
  const remainSec = slaDueAt - Date.now() / 1000;
  if (remainSec < 0) return { text: "SLA breached", warn: true };
  const remainHr = remainSec / 3600;
  if (remainHr < 1) return { text: `${Math.round(remainSec / 60)}m left`, warn: true };
  if (remainHr < 4) return { text: `${remainHr.toFixed(1)}h left`, warn: true };
  return null;
}

export default function WorkflowCard({ w }: { w: Workflow }) {
  const phaseOrder =
    w.type === "expense-claim" ? EXPENSE_PHASE_ORDER :
    w.type === "hiring" ? HIRING_PHASE_ORDER :
    PHASE_ORDER;
  const phaseIdx = phaseOrder.indexOf(w.currentPhase);
  const pct = ((phaseIdx + 1) / phaseOrder.length) * 100;
  const subtitle = w.claim
    ? `${w.claim.employeeId} · ${w.claim.vendor}`
    : w.type === "hiring"
    ? hiringSubtitle(w.metadata)
    : w.vendor?.name ?? w.id;
  const amount = w.claim ?? w.invoice;
  const sla = fmtSlaRemaining(w.slaDueAt);
  const hasException = !!w.activeExceptionId;
  const cardBorder = hasException
    ? "border-amber-300 bg-amber-50 dark:bg-amber-950/30/30"
    : sla?.warn
    ? "border-red-200 dark:border-red-800"
    : "border-slate-200 dark:border-slate-700";

  return (
    <Link
      to={`/workflows/${w.id}`}
      className={`block bg-white dark:bg-slate-900 border ${cardBorder} rounded-lg p-3 shadow-sm hover:border-blue-400 hover:shadow transition`}
    >
      <div className="flex items-center justify-between gap-2">
        <div className="flex items-center gap-2 min-w-0">
          <span
            className={`text-[10px] uppercase tracking-wide font-medium px-1.5 py-0.5 rounded whitespace-nowrap ${DOMAIN_COLOR[w.type] ?? "bg-slate-50 dark:bg-slate-800 text-slate-600 dark:text-slate-300 ring-1 ring-slate-200 dark:ring-slate-700"}`}
          >
            {DOMAIN_LABEL[w.type] ?? w.type}
          </span>
          <div className="font-semibold text-sm text-slate-900 dark:text-slate-100 truncate">{w.id}</div>
        </div>
        <span
          className={`text-[10px] uppercase tracking-wide font-medium px-1.5 py-0.5 rounded whitespace-nowrap ${STATUS_COLOR[w.status]}`}
        >
          {STATUS_LABEL[w.status]}
        </span>
      </div>
      <div className="text-xs text-slate-500 dark:text-slate-400 mt-0.5 truncate">{subtitle}</div>
      {amount && (
        <div className="text-xs text-slate-700 dark:text-slate-200 mt-1 flex items-center gap-2 flex-wrap">
          <span className="font-semibold text-slate-900 dark:text-slate-100">
            {amount.currency} {amount.amount.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
          </span>
          {w.claim && (
            <span className="text-[10px] text-slate-500 dark:text-slate-400 capitalize">{w.claim.category}</span>
          )}
          {w.verdict && (
            <span className={`text-[10px] uppercase tracking-wide px-1.5 py-0.5 rounded font-medium ${VERDICT_COLOR[w.verdict]}`}>
              {w.verdict}
            </span>
          )}
        </div>
      )}
      <div className="mt-2 flex items-center justify-between gap-2">
        <div className="text-[10px] text-slate-500 dark:text-slate-400 truncate">{w.currentPhase}</div>
        {sla && (
          <div className={`text-[10px] flex items-center gap-1 whitespace-nowrap ${sla.warn ? "text-red-600 font-medium" : "text-slate-500 dark:text-slate-400"}`}>
            <Clock size={10} />
            {sla.text}
          </div>
        )}
      </div>
      <div className="h-1 bg-slate-100 dark:bg-slate-800 rounded mt-1">
        <div className={`h-1 rounded ${PROGRESS_BAR[w.status]}`} style={{ width: `${pct}%` }} />
      </div>
      {hasException && (
        <div className="mt-2 flex items-center gap-1 text-[10px] text-amber-800 font-medium">
          <AlertTriangle size={11} />
          exception · awaiting reviewer
        </div>
      )}
    </Link>
  );
}

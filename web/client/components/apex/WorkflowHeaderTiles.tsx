// web/client/components/apex/WorkflowHeaderTiles.tsx
import type { Workflow } from "@shared/types";

function riskFactor(w: Workflow): "low" | "medium" | "high" {
  const hrsToSLA = (w.slaDueAt - Date.now() / 1000) / 3600;
  const hasExc = !!w.activeExceptionId;
  if (hasExc && hrsToSLA < 24) return "high";
  if (hasExc || hrsToSLA < 48) return "medium";
  return "low";
}

function slaHealth(w: Workflow): string {
  const hrs = Math.max(0, (w.slaDueAt - Date.now() / 1000) / 3600);
  if (hrs >= 24) return `${Math.round(hrs / 24)}d remaining`;
  return `${Math.round(hrs)}h remaining`;
}

const RISK_COLOR = {
  low:    "text-emerald-700 dark:text-emerald-400 bg-emerald-50 dark:bg-emerald-950/30 border-emerald-200 dark:border-emerald-800",
  medium: "text-amber-700 dark:text-amber-400 bg-amber-50 dark:bg-amber-950/30 border-amber-200 dark:border-amber-800",
  high:   "text-red-700 dark:text-red-400 bg-red-50 dark:bg-red-950/30 border-red-200 dark:border-red-800",
};

const STATUS_HUMAN: Record<Workflow["status"], string> = {
  in_progress: "In progress",
  awaiting_hitl: "Awaiting operator",
  completed: "Completed",
  failed: "Failed",
};

const STATUS_COLOR: Record<Workflow["status"], string> = {
  in_progress: "text-blue-700 dark:text-blue-300 bg-blue-50 dark:bg-blue-950/30 border-blue-200 dark:border-blue-800",
  awaiting_hitl: "text-amber-700 dark:text-amber-400 bg-amber-50 dark:bg-amber-950/30 border-amber-200 dark:border-amber-800",
  completed: "text-emerald-700 dark:text-emerald-400 bg-emerald-50 dark:bg-emerald-950/30 border-emerald-200 dark:border-emerald-800",
  failed: "text-red-700 dark:text-red-400 bg-red-50 dark:bg-red-950/30 border-red-200 dark:border-red-800",
};

// Generic wait-kind labels — domain-agnostic. Domain-friendly copy
// ("Awaiting screening call", "Awaiting reviewer decision") lives in the
// domain's own surface (recruiter portal for hiring, reviewer-queue for
// expense). The Agent Administrator shell only sees the platform truth.
const WAIT_KIND_LABEL: Record<string, string> = {
  external_party:  "Awaiting external party",
  operator_review: "Awaiting operator review",
};

export default function WorkflowHeaderTiles({ workflow }: { workflow: Workflow }) {
  const risk = riskFactor(workflow);
  const meta = (workflow.metadata as { wait_kind?: string; rejected_at_phase?: string; rejected_by?: string } | undefined) ?? {};
  const waitLabel = meta.wait_kind && WAIT_KIND_LABEL[meta.wait_kind];
  const isExternalWait = meta.wait_kind === "external_party";
  // Terminal states win over everything: a rejected/completed workflow
  // shouldn't paint a stale "Awaiting…" or "STALLED" pill from when the
  // gate was still open. Backend clears wait_kind on rejection (see
  // internal_durable_event.workflow.rejected) so the second branch only
  // catches the residual race; this guard is the final word.
  const isTerminal = workflow.status === "failed" || workflow.status === "completed";
  // External-party waits never paint the dashboard red — they're not on the
  // operator's plate. Operator-review waits + validator blocks DO show as
  // STALLED so they get the operator's attention.
  const stalled = !isTerminal && !isExternalWait && !!workflow.activeExceptionId;
  const statusTile = isTerminal
    ? workflow.status === "failed"
      ? { label: "STATUS · REJECTED",
          value: meta.rejected_at_phase
            ? `Rejected at ${meta.rejected_at_phase}`
            : "Rejected",
          cls: "text-red-700 dark:text-red-400 bg-red-50 dark:bg-red-950/30 border-red-200 dark:border-red-800" }
      : { label: "STATUS", value: "Completed",
          cls: "text-emerald-700 dark:text-emerald-400 bg-emerald-50 dark:bg-emerald-950/30 border-emerald-200 dark:border-emerald-800" }
    : stalled
      ? { label: "STATUS · STALLED", value: `Exception at ${workflow.currentPhase}`, cls: "text-red-700 dark:text-red-400 bg-red-50 dark:bg-red-950/30 border-red-200 dark:border-red-800" }
      : waitLabel
        ? { label: "STATUS", value: waitLabel,
            cls: isExternalWait ? "text-blue-700 dark:text-blue-300 bg-blue-50 dark:bg-blue-950/30 border-blue-200 dark:border-blue-800"
                                : "text-amber-700 dark:text-amber-400 bg-amber-50 dark:bg-amber-950/30 border-amber-200 dark:border-amber-800" }
        : { label: "STATUS", value: STATUS_HUMAN[workflow.status], cls: STATUS_COLOR[workflow.status] };
  return (
    <div className="grid grid-cols-3 gap-3" data-testid="workflow-header-tiles">
      {[
        statusTile,
        { label: "SLA HEALTH", value: slaHealth(workflow), cls: "text-slate-700 dark:text-slate-200 bg-slate-50 dark:bg-slate-800 border-slate-200 dark:border-slate-700" },
        { label: "RISK FACTOR", value: risk.toUpperCase(), cls: RISK_COLOR[risk] },
      ].map(t => (
        <div key={t.label} className={`rounded-lg border p-3 ${t.cls}`}>
          <div className="text-[10px] uppercase font-semibold tracking-wide opacity-70">{t.label}</div>
          <div className="text-base font-semibold mt-1">{t.value}</div>
        </div>
      ))}
    </div>
  );
}

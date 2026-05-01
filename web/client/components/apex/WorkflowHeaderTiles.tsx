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
  low:    "text-emerald-700 bg-emerald-50 border-emerald-200",
  medium: "text-amber-700 bg-amber-50 border-amber-200",
  high:   "text-red-700 bg-red-50 border-red-200",
};

const STATUS_HUMAN: Record<Workflow["status"], string> = {
  in_progress: "In progress",
  awaiting_hitl: "Awaiting operator",
  completed: "Completed",
  failed: "Failed",
};

const STATUS_COLOR: Record<Workflow["status"], string> = {
  in_progress: "text-blue-700 bg-blue-50 border-blue-200",
  awaiting_hitl: "text-amber-700 bg-amber-50 border-amber-200",
  completed: "text-emerald-700 bg-emerald-50 border-emerald-200",
  failed: "text-red-700 bg-red-50 border-red-200",
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
  const meta = (workflow.metadata as { wait_kind?: string } | undefined) ?? {};
  const waitLabel = meta.wait_kind && WAIT_KIND_LABEL[meta.wait_kind];
  const isExternalWait = meta.wait_kind === "external_party";
  // External-party waits never paint the dashboard red — they're not on the
  // operator's plate. Operator-review waits + validator blocks DO show as
  // STALLED so they get the operator's attention.
  const stalled = !isExternalWait && !!workflow.activeExceptionId;
  const statusTile = stalled
    ? { label: "STATUS · STALLED", value: `Exception at ${workflow.currentPhase}`, cls: "text-red-700 bg-red-50 border-red-200" }
    : waitLabel
      ? { label: "STATUS", value: waitLabel,
          cls: isExternalWait ? "text-blue-700 bg-blue-50 border-blue-200"
                              : "text-amber-700 bg-amber-50 border-amber-200" }
      : { label: "STATUS", value: STATUS_HUMAN[workflow.status], cls: STATUS_COLOR[workflow.status] };
  return (
    <div className="grid grid-cols-3 gap-3" data-testid="workflow-header-tiles">
      {[
        statusTile,
        { label: "SLA HEALTH", value: slaHealth(workflow), cls: "text-slate-700 bg-slate-50 border-slate-200" },
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

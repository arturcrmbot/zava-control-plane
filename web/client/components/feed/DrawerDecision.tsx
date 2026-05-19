// web/client/components/feed/DrawerDecision.tsx
//
// First drawer section: receipt + recommendation + 4 actions + AuthorityCard
// + KillSwitchPanel. Mirrors WorkflowDetail.tsx's Overview tab content but
// laid out top-down inside the drawer.
import { useState } from "react";
import type { RolePreset } from "@shared/roles";
import type { DrawerData } from "./Drawer";
import type { ClaimData } from "@shared/types";
import AuthorityCard from "@client/components/apex/AuthorityCard";
import KillSwitchPanel from "@client/features/governance/KillSwitchPanel";
import ExceptionAnalysisCard from "@client/components/apex/ExceptionAnalysisCard";
import InterventionProtocols from "@client/components/apex/InterventionProtocols";
import CreativeCampaignArtefacts from "@client/components/apex/CreativeCampaignArtefacts";
import AgentDrivenComponent, { type AgentComponentSpec } from "@client/components/AgentDrivenComponent";

const ACTIONS = [
  { id: "approve",      label: "Approve",      cls: "bg-emerald-600 hover:bg-emerald-700 text-white" },
  { id: "request-info", label: "Request docs", cls: "bg-white dark:bg-slate-900 text-slate-700 dark:text-slate-200 ring-1 ring-slate-300 dark:ring-slate-600 hover:bg-slate-50 dark:hover:bg-slate-800" },
  { id: "escalate",     label: "Escalate L2",  cls: "bg-white dark:bg-slate-900 text-amber-700 ring-1 ring-amber-300 hover:bg-amber-50" },
  { id: "reject",       label: "Reject",       cls: "bg-white dark:bg-slate-900 text-red-700 ring-1 ring-red-300 hover:bg-red-50" },
];

function ReceiptPanel({ claim }: { claim: ClaimData }) {
  const [errored, setErrored] = useState(false);
  const missing = errored || claim.receiptMismatchFlavour === "missing-receipt";
  return (
    <div className="panel">
      <div className="panel-header">Receipt · {claim.claimId}</div>
      <div className="panel-body flex gap-4">
        {missing ? (
          <div className="w-32 h-40 bg-amber-50 border-2 border-dashed border-amber-300 rounded flex items-center justify-center text-xs text-amber-700">no receipt</div>
        ) : (
          <img
            src={`/api/receipts/${claim.claimId}.png`}
            alt={`receipt ${claim.claimId}`}
            onError={() => setErrored(true)}
            className="w-32 h-40 object-contain bg-white dark:bg-slate-900 rounded border border-slate-200 dark:border-slate-700"
          />
        )}
        <div className="text-xs text-slate-700 dark:text-slate-200 space-y-1">
          <div><span className="text-slate-500 dark:text-slate-400">Vendor</span> <span className="font-medium">{claim.vendor}</span></div>
          <div><span className="text-slate-500 dark:text-slate-400">Amount</span> <span className="font-semibold">{claim.currency} {claim.amount.toLocaleString()}</span></div>
          <div><span className="text-slate-500 dark:text-slate-400">Category</span> <span className="font-medium capitalize">{claim.category}</span></div>
        </div>
      </div>
    </div>
  );
}

export default function DrawerDecision({
  data, role, onRefresh,
}: {
  data: DrawerData;
  role: RolePreset;
  onRefresh: () => Promise<void> | void;
}) {
  const w = data.workflow;
  const [busy, setBusy] = useState<string | null>(null);

  const exceptionId = data.activeException?.id ?? w.activeExceptionId;
  const act = async (id: string) => {
    if (!exceptionId) return;
    setBusy(id);
    try {
      await fetch(`/api/exceptions/${exceptionId}/resolve`, {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ resolution: id, resolvedBy: "reviewer@zava" }),
      });
      await onRefresh();
    } finally {
      setBusy(null);
    }
  };

  const agentOutputs = (w as unknown as { agentOutputs?: Record<string, unknown> }).agentOutputs ?? {};
  const triage = (agentOutputs["cv_crystalliser"] ?? {}) as { componentSpec?: unknown[]; component_spec?: unknown[] };
  const specs = ((triage.componentSpec ?? triage.component_spec) ?? []) as AgentComponentSpec[];

  return (
    <section className="space-y-4">
      <h2 className="text-[11px] uppercase tracking-wide font-semibold text-slate-500 dark:text-slate-400">Decision</h2>

      {w.type === "hiring" && specs.length > 0 && (
        <div className="grid grid-cols-1 gap-3">
          {specs.map((spec, i) => <AgentDrivenComponent key={i} spec={spec} />)}
        </div>
      )}

      {w.type === "creative-campaign" && (
        <CreativeCampaignArtefacts workflow={w} onChange={onRefresh} />
      )}

      {w.claim && <ReceiptPanel claim={w.claim} />}

      {data.narrative && data.activeException && (
        <>
          <ExceptionAnalysisCard narrative={data.narrative} />
          <InterventionProtocols exception={data.activeException} onResolved={onRefresh} />
        </>
      )}

      {!role.hideActionButtons && (
        <div className="flex gap-2 flex-wrap">
          {ACTIONS.map((a) => (
            <button
              key={a.id}
              type="button"
              disabled={busy != null || !exceptionId}
              onClick={() => void act(a.id)}
              className={`text-xs px-3 py-1.5 rounded font-medium disabled:opacity-50 ${a.cls}`}
            >{busy === a.id ? "…" : a.label}</button>
          ))}
        </div>
      )}

      <AuthorityCard workflow={w} />
      <details className="rounded border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-900">
        <summary className="cursor-pointer text-xs text-slate-700 dark:text-slate-200 px-3 py-2">Kill switch</summary>
        <div className="px-3 pb-3"><KillSwitchPanel /></div>
      </details>
    </section>
  );
}

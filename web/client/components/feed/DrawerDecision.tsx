// web/client/components/feed/DrawerDecision.tsx
//
// First drawer section: receipt + recommendation + 4 actions + AuthorityCard
// + KillSwitchPanel. Mirrors WorkflowDetail.tsx's Overview tab content but
// laid out top-down inside the drawer.
import { useState, useRef, useEffect } from "react";
import type { RolePreset } from "@shared/roles";
import type { DrawerData } from "./Drawer";
import type { ClaimData } from "@shared/types";
import AuthorityCard from "@client/components/apex/AuthorityCard";
import KillSwitchPanel from "@client/features/governance/KillSwitchPanel";
import ExceptionAnalysisCard from "@client/components/apex/ExceptionAnalysisCard";
import InterventionProtocols from "@client/components/apex/InterventionProtocols";
import CreativeCampaignArtefacts from "@client/components/apex/CreativeCampaignArtefacts";
import AgentDrivenComponent, { type AgentComponentSpec } from "@client/components/AgentDrivenComponent";

const PRIMARY = [
  { id: "approve", label: "Approve", cls: "bg-emerald-600 hover:bg-emerald-700 text-white" },
  { id: "reject",  label: "Reject",  cls: "bg-white dark:bg-slate-900 text-red-700 ring-1 ring-red-300 hover:bg-red-50" },
];
const OVERFLOW = [
  { id: "request-info", label: "Request docs" },
  { id: "escalate",     label: "Escalate L2"  },
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
  const activeException = data.activeException;
  const [busy, setBusy] = useState<string | null>(null);

  const hasActiveHitlException = (
    w.status === "awaiting_hitl"
    && activeException != null
    && activeException.resolvedAt == null
  );
  const exceptionId = hasActiveHitlException ? activeException?.id : undefined;
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

      {data.narrative && activeException && (
        <ExceptionAnalysisCard narrative={data.narrative} />
      )}
      {data.narrative && activeException && hasActiveHitlException && (
        <InterventionProtocols exception={activeException} onResolved={onRefresh} />
      )}

      {!role.hideActionButtons && hasActiveHitlException && (
        <DecisionActions
          busy={busy}
          disabled={!exceptionId}
          onAct={(id) => void act(id)}
        />
      )}

      <AuthorityCard workflow={w} />
      <details className="rounded border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-900">
        <summary className="cursor-pointer text-xs text-slate-700 dark:text-slate-200 px-3 py-2">Kill switch</summary>
        <div className="px-3 pb-3"><KillSwitchPanel /></div>
      </details>
    </section>
  );
}

function DecisionActions({
  busy, disabled, onAct,
}: {
  busy: string | null;
  disabled: boolean;
  onAct: (id: string) => void;
}) {
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);
  useEffect(() => {
    if (!open) return;
    const onDocClick = (e: MouseEvent) => {
      if (!ref.current?.contains(e.target as Node)) setOpen(false);
    };
    window.addEventListener("mousedown", onDocClick);
    return () => window.removeEventListener("mousedown", onDocClick);
  }, [open]);
  return (
    <div className="flex gap-2 flex-wrap items-center">
      {PRIMARY.map((a) => (
        <button
          key={a.id}
          type="button"
          disabled={busy != null || disabled}
          onClick={() => onAct(a.id)}
          className={`text-xs px-3 py-1.5 rounded font-medium disabled:opacity-50 ${a.cls}`}
        >{busy === a.id ? "…" : a.label}</button>
      ))}
      <div className="relative" ref={ref}>
        <button
          type="button"
          aria-label="More actions"
          onClick={() => setOpen((o) => !o)}
          className="text-slate-500 dark:text-slate-300 hover:text-slate-900 dark:hover:text-white text-base px-2 py-1 rounded leading-none"
        >⋯</button>
        {open && (
          <div
            role="menu"
            className="absolute right-0 mt-1 w-40 rounded-md border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-900 shadow z-10"
          >
            {OVERFLOW.map((a) => (
              <button
                key={a.id}
                type="button"
                role="menuitem"
                disabled={busy != null || disabled}
                onClick={() => { setOpen(false); onAct(a.id); }}
                className="block w-full text-left text-xs px-3 py-2 text-slate-700 dark:text-slate-200 hover:bg-slate-50 dark:hover:bg-slate-800 disabled:opacity-50"
              >{busy === a.id ? "…" : a.label}</button>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

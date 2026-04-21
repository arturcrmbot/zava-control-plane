// src/client/routes/WorkflowDetail.tsx
import { useEffect, useState } from "react";
import { useParams } from "react-router-dom";
import type { Workflow, Phase, OtelSpan, Exception, SkillAmplification, ActionLedgerEntry } from "@shared/types";
import OtelSpanTree from "../components/OtelSpanTree";
import PhaseTimeline from "../components/PhaseTimeline";
import SkillAmplificationPanel from "../components/SkillAmplificationPanel";
import OrchestrationView from "../components/OrchestrationView";

type DetailResp = {
  workflow: Workflow; phases: Phase[]; spans: OtelSpan[];
  amplifications: SkillAmplification[]; activeException: Exception | null;
};

const tabs = ["Overview", "Phases", "Traces", "Ledger", "Amplification", "Orchestration"] as const;

export default function WorkflowDetail() {
  const { id } = useParams();
  const [d, setD] = useState<DetailResp | null>(null);
  const [tab, setTab] = useState<typeof tabs[number]>("Overview");

  useEffect(() => {
    if (!id) return;
    void fetch(`/api/workflows/${id}`).then(r => r.json()).then(setD);
  }, [id]);

  if (!d) return <div className="text-xs text-slate-500">loading…</div>;
  const w = d.workflow;

  return (
    <div className="space-y-3">
      <div>
        <div className="text-lg font-semibold">{w.id} · {w.vendor.name}</div>
        <div className="text-xs text-slate-400">{w.invoice.currency} {w.invoice.amount.toLocaleString()} · PO {w.invoice.poRef} · {w.agency}</div>
      </div>
      <div className="flex gap-1 border-b border-slate-800">
        {tabs.map(t => (
          <button key={t} onClick={() => setTab(t)}
            className={`text-xs px-3 py-1.5 ${tab === t ? "text-slate-100 border-b-2 border-blue-400" : "text-slate-400"}`}>
            {t}
          </button>
        ))}
      </div>
      {tab === "Overview" && (() => {
        const rejectedEntry = [...w.actionLedger].reverse().find(
          a => a.action === "bulk-resolve:reject" || a.action === "bulk-resolve:rejected"
        );
        const isRejected = w.status === "failed" && w.currentPhase === "Approval" && !!rejectedEntry;
        return (
          <div className="text-xs text-slate-300 space-y-1">
            <div>status: <span className={isRejected ? "text-red-400" : undefined}>{w.status}</span></div>
            <div>phase: <span className={isRejected ? "text-red-400" : undefined}>{w.currentPhase}</span></div>
            {isRejected && (
              <div className="mt-2 border border-red-700 rounded p-2 bg-red-950/30 text-red-300">
                Rejected by {rejectedEntry?.actor.id ?? "operator"}
              </div>
            )}
            {d.activeException && (
              <div className="mt-2 border border-amber-700 rounded p-2 bg-amber-950/30">
                <div className="text-amber-300 font-medium">⚠ {d.activeException.category} · {d.activeException.severity}</div>
                <div>{d.activeException.summary}</div>
                <div className="text-emerald-300">→ {d.activeException.recommendation}</div>
              </div>
            )}
          </div>
        );
      })()}
      {tab === "Phases" && <PhaseTimeline phases={d.phases} />}
      {tab === "Traces" && <OtelSpanTree spans={d.spans} />}
      {tab === "Ledger" && (
        <div className="space-y-1 text-xs">
          {w.actionLedger.map((a: ActionLedgerEntry, i) => (
            <div key={i} className="border border-slate-800 rounded p-2 bg-slate-900/30">
              <div className="text-slate-200">{a.action}</div>
              <div className="text-slate-500">
                {new Date(a.timestamp).toLocaleString()} · {a.actor.kind}:{a.actor.id} · {a.revocable ? "revocable" : "non-revocable"}
              </div>
            </div>
          ))}
        </div>
      )}
      {tab === "Amplification" && <SkillAmplificationPanel items={d.amplifications} />}
      {tab === "Orchestration" && <OrchestrationView workflowId={id!} />}
    </div>
  );
}

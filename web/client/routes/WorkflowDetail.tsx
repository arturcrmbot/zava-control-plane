// web/client/routes/WorkflowDetail.tsx
import { useEffect, useState, useCallback } from "react";
import { useParams } from "react-router-dom";
import type {
  Workflow, Phase, OtelSpan, Exception, SkillAmplification,
  ActionLedgerEntry, McpCall, Economics, Narrative,
} from "@shared/types";
import OtelSpanTree from "../components/OtelSpanTree";
import PhaseTimeline from "../components/PhaseTimeline";
import SkillAmplificationPanel from "../components/SkillAmplificationPanel";
import PhaseRibbon from "../components/apex/PhaseRibbon";
import WorkflowHeaderTiles from "../components/apex/WorkflowHeaderTiles";
import ExceptionAnalysisCard from "../components/apex/ExceptionAnalysisCard";
import InterventionProtocols from "../components/apex/InterventionProtocols";
import EconomicsPanel from "../components/apex/EconomicsPanel";
import FleetAssignment from "../components/apex/FleetAssignment";
import AuditTrail from "../components/apex/AuditTrail";
import ExecutionTimelineTab from "../components/apex/ExecutionTimelineTab";

type DetailResp = {
  workflow: Workflow; phases: Phase[]; spans: OtelSpan[];
  amplifications: SkillAmplification[];
  activeException: Exception | null;
  mcpCalls: McpCall[];
  economics: Economics;
  narrative: Narrative | null;
};

const TABS = ["Overview", "Phases", "Traces", "Ledger", "Amplification", "Execution Timeline"] as const;

export default function WorkflowDetail() {
  const { id } = useParams();
  const [d, setD] = useState<DetailResp | null>(null);
  const [tab, setTab] = useState<typeof TABS[number]>("Overview");

  const refresh = useCallback(async () => {
    if (!id) return;
    const r = await fetch(`/api/workflows/${id}`);
    setD(await r.json());
  }, [id]);

  useEffect(() => {
    void refresh();
    const i = setInterval(() => { void refresh(); }, 2500);
    return () => clearInterval(i);
  }, [refresh]);

  const logAction = useCallback(async (action: string) => {
    if (!id) return;
    // Log-only: reuse the existing `workflow.rejected` handler to append an
    // audit-trail entry with the illustrative action name. No other state
    // change happens; Fork/Rollback are visual stubs for the demo.
    await fetch("/internal/durable-event", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        workflow_id: id, kind: "workflow.rejected",
        payload: { by: "operator", reason: `illustrative ${action}` },
      }),
    }).catch(() => {});
    await refresh();
  }, [id, refresh]);

  if (!d) return <div className="text-sm text-slate-500">loading…</div>;
  const w = d.workflow;

  return (
    <div className="grid grid-cols-4 gap-4 min-w-0">
      <div className="col-span-3 space-y-4 min-w-0">
        <div>
          <div className="text-xs text-slate-500">{w.id}</div>
          <div className="text-xl font-semibold text-slate-900">{w.id} · {w.vendor.name}</div>
          <div className="text-xs text-slate-500">
            {w.invoice.currency} {w.invoice.amount.toLocaleString()} · PO {w.invoice.poRef} · {w.agency}
          </div>
        </div>

        <WorkflowHeaderTiles workflow={w} />
        <PhaseRibbon workflow={w} phases={d.phases} />

        <div className="flex gap-1 border-b border-slate-200">
          {TABS.map(t => (
            <button key={t} onClick={() => setTab(t)}
                    className={`text-sm px-4 py-2 ${tab === t ?
                      "text-blue-700 border-b-2 border-blue-600 font-medium" :
                      "text-slate-500 hover:text-slate-800"}`}>{t}</button>
          ))}
        </div>

        {tab === "Overview" && (
          <div className="space-y-4">
            {d.narrative && d.activeException && (
              <>
                <ExceptionAnalysisCard narrative={d.narrative} />
                <InterventionProtocols exception={d.activeException} onResolved={refresh} />
              </>
            )}
            {!d.activeException && (
              <div className="panel panel-body text-sm text-slate-500">
                No active exception. Workflow is progressing autonomously.
              </div>
            )}
          </div>
        )}
        {tab === "Phases" && <PhaseTimeline phases={d.phases} />}
        {tab === "Traces" && <OtelSpanTree spans={d.spans} />}
        {tab === "Ledger" && (
          <div className="space-y-1 text-xs">
            {(w.actionLedger as ActionLedgerEntry[]).map((a, i) => (
              <div key={i} className="panel panel-body">
                <div className="font-medium text-slate-800">{a.action}</div>
                <div className="text-slate-500">
                  {new Date(a.timestamp * 1000).toLocaleString()} · {a.actorKind}:{a.actorId}
                  · {a.revocable ? "revocable" : "non-revocable"}
                </div>
              </div>
            ))}
          </div>
        )}
        {tab === "Amplification" && <SkillAmplificationPanel items={d.amplifications} />}
        {tab === "Execution Timeline" &&
          <ExecutionTimelineTab mcpCalls={d.mcpCalls} workflowId={w.id} onLogAction={logAction} />}
      </div>

      <div className="col-span-1 space-y-3">
        <EconomicsPanel e={d.economics} />
        <FleetAssignment spans={d.spans} />
        <AuditTrail ledger={w.actionLedger as ActionLedgerEntry[]} />
      </div>
    </div>
  );
}

// web/client/components/feed/DrawerActivity.tsx
//
// Second drawer section: merges WorkflowDetail's separate Phases, Timeline,
// and Traces tabs + the Ledger tab into one filterable activity stream
// fronted by a 3-view toggle.
import { useState, useCallback } from "react";
import type { DrawerData } from "./Drawer";
import OtelSpanTree from "@client/components/OtelSpanTree";
import ExecutionTimelineTab from "@client/components/apex/ExecutionTimelineTab";
import PhaseRibbon from "@client/components/apex/PhaseRibbon";
import type { ActionLedgerEntry } from "@shared/types";

const VIEWS = ["Timeline", "Spans", "Ledger"] as const;
type View = typeof VIEWS[number];

export default function DrawerActivity({ data }: { data: DrawerData }) {
  const [view, setView] = useState<View>("Timeline");

  const logAction = useCallback(async (action: string) => {
    await fetch("/internal/durable-event", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        workflow_id: data.workflow.id, kind: "log.action",
        payload: { by: "operator", action },
      }),
    }).catch(() => {});
  }, [data.workflow.id]);

  return (
    <section className="space-y-3">
      <div className="flex items-center gap-3">
        <h2 className="text-[11px] uppercase tracking-wide font-semibold text-slate-500 dark:text-slate-400">Activity</h2>
        <div className="inline-flex rounded-md border border-slate-200 dark:border-slate-700 overflow-hidden ml-auto">
          {VIEWS.map((v) => (
            <button
              key={v}
              type="button"
              onClick={() => setView(v)}
              className={`text-xs px-3 py-1 font-medium ${view === v ? "bg-blue-600 text-white" : "bg-white dark:bg-slate-900 text-slate-600 dark:text-slate-300 hover:bg-slate-50 dark:hover:bg-slate-800"}`}
            >{v}</button>
          ))}
        </div>
      </div>

      {/* Phase ribbon is the always-visible header for the section —
          PhaseTimeline used to duplicate this in the now-removed
          'Phases' tab. */}
      <PhaseRibbon workflow={data.workflow} phases={data.phases} />

      {view === "Timeline" && (
        <ExecutionTimelineTab mcpCalls={data.mcpCalls} workflowId={data.workflow.id} onLogAction={logAction} />
      )}
      {view === "Spans" && <OtelSpanTree spans={data.spans} />}
      {view === "Ledger" && (
        <div className="space-y-1 text-xs">
          {(data.workflow.actionLedger as ActionLedgerEntry[]).map((a, i) => (
            <div key={i} className="panel panel-body">
              <div className="font-medium text-slate-800 dark:text-slate-100">{a.action}</div>
              <div className="text-slate-500 dark:text-slate-400">
                {new Date(a.timestamp * 1000).toLocaleString()} · {a.actorKind}:{a.actorId} · {a.revocable ? "revocable" : "non-revocable"}
              </div>
            </div>
          ))}
        </div>
      )}
    </section>
  );
}

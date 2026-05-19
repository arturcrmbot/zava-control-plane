// web/client/components/feed/cards/AgentEventCard.tsx
//
// FM/orchestration event surface. Spec §3.4: "Expand JSON" is an inline
// accordion, not a drawer open — raw JSON is not worth a drawer.
import { useState } from "react";
import { Activity } from "lucide-react";
import type { AgentEventItem } from "@shared/feedItems";
import CardShell from "../CardShell";

const SOURCE_LABEL: Record<AgentEventItem["source"], string> = {
  "fleet-manager": "Fleet Manager",
  "orchestration": "Orchestration",
};

export default function AgentEventCard({ item }: { item: AgentEventItem }) {
  const [open, setOpen] = useState(false);

  const body = (
    <div className="min-w-0">
      <div className="text-sm text-slate-800 dark:text-slate-100">
        <span className="font-medium">{SOURCE_LABEL[item.source]}</span>
        <span className="text-slate-400 dark:text-slate-500"> · </span>
        <span className="font-mono text-xs">{item.kind}</span>
        {item.workflowId ? <span className="text-slate-500 dark:text-slate-400 text-xs"> on {item.workflowId}</span> : null}
      </div>
      {open && item.data != null && (
        <pre className="text-[11px] text-slate-700 dark:text-slate-200 bg-slate-50 dark:bg-slate-800 rounded p-2 mt-2 max-h-64 overflow-auto whitespace-pre-wrap break-all">
{JSON.stringify(item.data, null, 2)}
        </pre>
      )}
    </div>
  );

  const actions = (
    <button
      type="button"
      onClick={(e) => { e.stopPropagation(); setOpen((v) => !v); }}
      className="text-xs px-3 py-1.5 rounded font-medium bg-white dark:bg-slate-900 text-slate-700 dark:text-slate-200 ring-1 ring-slate-300 dark:ring-slate-600 hover:bg-slate-50 dark:hover:bg-slate-800"
    >
      {open ? "Hide JSON" : "Expand JSON"}
    </button>
  );

  return (
    <CardShell
      severity={item.severity ?? null}
      icon={<Activity size={12} className="text-purple-600" />}
      typeLabel="Agent event"
      workflowId={item.workflowId ?? "—"}
      timestampSec={item.timestamp}
      body={body}
      actions={actions}
    />
  );
}

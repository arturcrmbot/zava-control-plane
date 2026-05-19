// web/client/components/feed/cards/PolicyCard.tsx
//
// Policy / autonomy change event. v1 surfaces the description, current
// value, and actor; View diff opens the policy in the drawer (routed by
// policy id, not workflow id — drawer handles this case).
import { useState } from "react";
import { GitBranch } from "lucide-react";
import type { PolicyItem } from "@shared/feedItems";
import CardShell from "../CardShell";

export default function PolicyCard({
  item, hideActions = false, onOpenDrawer,
}: {
  item: PolicyItem;
  hideActions?: boolean;
  onOpenDrawer?: (policyId: string) => void;
}) {
  const [ack, setAck] = useState(false);
  if (ack) return null;

  const body = (
    <div className="text-sm text-slate-700 dark:text-slate-200 min-w-0">
      <div className="font-medium text-slate-900 dark:text-slate-100">{item.description}</div>
      <div className="text-xs text-slate-500 dark:text-slate-400 mt-1">
        current: <span className="font-medium text-slate-800 dark:text-slate-100">{String(item.currentValue)}</span>
        {item.actor ? <> · by <span className="font-medium text-slate-700 dark:text-slate-200">{item.actor}</span></> : null}
      </div>
    </div>
  );

  const actions = hideActions ? null : (
    <>
      <button
        type="button"
        onClick={(e) => { e.stopPropagation(); setAck(true); }}
        className="text-xs px-3 py-1.5 rounded font-medium bg-white dark:bg-slate-900 text-slate-700 dark:text-slate-200 ring-1 ring-slate-300 dark:ring-slate-600 hover:bg-slate-50 dark:hover:bg-slate-800"
      >Acknowledge</button>
      <button
        type="button"
        onClick={(e) => { e.stopPropagation(); onOpenDrawer?.(item.policyId); }}
        className="text-xs px-3 py-1.5 rounded font-medium bg-white dark:bg-slate-900 text-blue-700 ring-1 ring-blue-300 hover:bg-blue-50"
      >View diff</button>
    </>
  );

  return (
    <CardShell
      severity={null}
      icon={<GitBranch size={12} className="text-blue-600" />}
      typeLabel="Policy · change"
      workflowId={item.policyId}
      timestampSec={item.timestamp}
      body={body}
      actions={actions}
    />
  );
}

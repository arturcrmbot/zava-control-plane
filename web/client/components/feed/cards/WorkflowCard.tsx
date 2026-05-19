// web/client/components/feed/cards/WorkflowCard.tsx
//
// Generic per-workflow card. Renders when a workflow doesn't match any
// of the more-specific card types (HITL, exception, external-wait,
// milestone). Guarantees that every active or recently-finished
// workflow is observable in the control plane.
import { useState } from "react";
import { Activity } from "lucide-react";
import type { WorkflowItem } from "@shared/feedItems";
import CardShell from "../CardShell";

const STATUS_LABEL: Record<string, string> = {
  in_progress: "in progress",
  awaiting_hitl: "awaiting human",
  completed: "completed",
  failed: "failed",
  cancelled: "cancelled",
};

export default function WorkflowCard({
  item, hideActions = false, onOpenDrawer, onDismiss,
}: {
  item: WorkflowItem;
  hideActions?: boolean;
  onOpenDrawer?: (workflowId: string) => void;
  onDismiss?: (itemId: string) => void;
}) {
  const w = item.workflow;
  const [dismissed, setDismissed] = useState(false);
  if (dismissed) return null;

  const statusLabel = STATUS_LABEL[item.status] ?? item.status;

  const body = (
    <div className="text-sm text-slate-700 dark:text-slate-200">
      <span className="font-semibold text-slate-900 dark:text-slate-100">{w.id}</span>
      <span className="text-slate-500 dark:text-slate-400"> ({w.type})</span>{" "}
      <span>{statusLabel}</span>
      <span className="text-slate-500 dark:text-slate-400"> · phase {item.phase}</span>
    </div>
  );

  const actions = hideActions ? null : (
    <button
      type="button"
      onClick={(e) => { e.stopPropagation(); setDismissed(true); onDismiss?.(item.id); }}
      className="text-xs px-3 py-1.5 rounded font-medium bg-white dark:bg-slate-900 text-slate-500 dark:text-slate-400 ring-1 ring-slate-200 dark:ring-slate-700 hover:bg-slate-50 dark:hover:bg-slate-800"
    >Dismiss</button>
  );

  return (
    <CardShell
      severity={item.severity ?? null}
      icon={<Activity size={12} className="text-slate-500 dark:text-slate-400" />}
      typeLabel="Workflow"
      workflowId={w.id}
      timestampSec={item.timestamp}
      body={body}
      actions={actions}
      onPrimaryClick={onOpenDrawer ? () => onOpenDrawer(w.id) : undefined}
    />
  );
}

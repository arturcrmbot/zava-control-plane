// web/client/components/feed/cards/MilestoneCard.tsx
//
// Terminal status transition. Only visible in "all-activity" mode. Carries
// an Open (drawer) and a local Dismiss; Dismiss simply removes the card via
// the parent's optimistic store (no backend call — purely a personal-feed
// affordance).
import { useState } from "react";
import { CheckCircle2, XCircle } from "lucide-react";
import type { MilestoneItem } from "@shared/feedItems";
import CardShell from "../CardShell";

export default function MilestoneCard({
  item, hideActions = false, onOpenDrawer, onDismiss,
}: {
  item: MilestoneItem;
  hideActions?: boolean;
  onOpenDrawer?: (workflowId: string) => void;
  onDismiss?: (itemId: string) => void;
}) {
  const w = item.workflow;
  const [dismissed, setDismissed] = useState(false);
  if (dismissed) return null;

  const verb = item.outcome === "completed" ? "completed" : "failed";
  const icon = item.outcome === "completed"
    ? <CheckCircle2 size={12} className="text-emerald-600" />
    : <XCircle size={12} className="text-red-600" />;

  const body = (
    <div className="text-sm text-slate-700">
      <span className="font-semibold text-slate-900">{w.id}</span>
      <span className="text-slate-500"> ({w.type})</span> {verb}.
    </div>
  );

  const actions = hideActions ? null : (
    <>
      <button
        type="button"
        onClick={(e) => { e.stopPropagation(); onOpenDrawer?.(w.id); }}
        className="text-xs px-3 py-1.5 rounded font-medium bg-white text-slate-700 ring-1 ring-slate-300 hover:bg-slate-50"
      >Open</button>
      <button
        type="button"
        onClick={(e) => { e.stopPropagation(); setDismissed(true); onDismiss?.(item.id); }}
        className="text-xs px-3 py-1.5 rounded font-medium bg-white text-slate-500 ring-1 ring-slate-200 hover:bg-slate-50"
      >Dismiss</button>
    </>
  );

  return (
    <CardShell
      severity={item.severity ?? null}
      icon={icon}
      typeLabel="Milestone"
      workflowId={w.id}
      timestampSec={item.timestamp}
      body={body}
      actions={actions}
      onPrimaryClick={onOpenDrawer ? () => onOpenDrawer(w.id) : undefined}
    />
  );
}

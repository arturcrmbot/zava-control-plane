// web/client/components/feed/cards/ResolvedCard.tsx
//
// Collapsed in-place replacement for a HITL/Exception/ExternalWait card
// the user has acted on. Per spec §3.5: "✓ <Verb> by you · <relative time>
// · undo · audit ↗". Undo is live for 30s (managed by useResolutionStore);
// after TTL the undo button hides.
import { useState } from "react";
import { CheckCircle2 } from "lucide-react";
import type { ResolvedItem } from "@shared/feedItems";
import CardShell from "../CardShell";
import { useResolutionStore } from "@client/hooks/useResolutionStore";

function relativeTime(tsSec: number): string {
  const diff = Math.max(0, Date.now() / 1000 - tsSec);
  if (diff < 60) return `${Math.round(diff)}s ago`;
  if (diff < 3600) return `${Math.round(diff / 60)}m ago`;
  return `${(diff / 3600).toFixed(1)}h ago`;
}

export default function ResolvedCard({
  item, onOpenDrawer,
}: {
  item: ResolvedItem;
  onOpenDrawer?: (workflowId: string) => void;
}) {
  const store = useResolutionStore();
  const [didUndo, setDidUndo] = useState(false);
  const originKey = item.origin?.id ?? item.originId ?? "";
  const r = originKey ? store.get(originKey) : undefined;
  const undoable = !didUndo && (r?.undoable ?? false);

  const body = (
    <div className="text-sm text-slate-600 dark:text-slate-300 truncate">
      <CheckCircle2 size={14} className="inline-block text-emerald-600 mr-1.5 align-text-bottom" />
      <span className="font-medium text-slate-800 dark:text-slate-100">{item.verb} by {item.actor}</span>
      <span className="text-slate-400 dark:text-slate-500"> · {relativeTime(item.actedAt)}</span>
    </div>
  );

  const actions = undoable ? (
    <button
      type="button"
      onClick={(e) => { e.stopPropagation(); setDidUndo(true); store.revert(originKey); }}
      className="text-xs px-3 py-1 rounded font-medium bg-white dark:bg-slate-900 text-amber-700 ring-1 ring-amber-300 hover:bg-amber-50"
    >Undo</button>
  ) : null;

  return (
    <CardShell
      severity={null}
      icon={<CheckCircle2 size={12} className="text-emerald-600" />}
      typeLabel="Resolved"
      workflowId={item.workflowId ?? "—"}
      timestampSec={item.actedAt}
      body={body}
      actions={actions}
      onPrimaryClick={item.workflowId && onOpenDrawer ? () => onOpenDrawer(item.workflowId!) : undefined}
    />
  );
}

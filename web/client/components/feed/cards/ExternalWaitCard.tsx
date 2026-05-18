// web/client/components/feed/cards/ExternalWaitCard.tsx
//
// Workflow suspended on an external party (metadata.wait_kind="external_party").
// Actions are advisory in v1 — Nudge fires log.action via the durable event
// bus; Reassign and View token open the drawer for further detail.
import { useState } from "react";
import { Hourglass } from "lucide-react";
import type { ExternalWaitItem } from "@shared/feedItems";
import CardShell from "../CardShell";
import { useResolutionStore } from "@client/hooks/useResolutionStore";
import { useToast } from "../Toast";

export default function ExternalWaitCard({
  item, hideActions = false, onOpenDrawer,
}: {
  item: ExternalWaitItem;
  hideActions?: boolean;
  onOpenDrawer?: (workflowId: string) => void;
}) {
  const store = useResolutionStore();
  const toast = useToast();
  const [busy, setBusy] = useState<string | null>(null);

  const nudge = async () => {
    setBusy("nudge");
    store.record(item.id, { verb: "Nudged", actor: "you", actedAt: Math.floor(Date.now() / 1000) });
    try {
      const r = await fetch("/internal/durable-event", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          workflow_id: item.workflowId, kind: "log.action",
          payload: { by: "operator", action: "nudge-external" },
        }),
      });
      if (!r.ok) {
        store.revert(item.id);
        toast.show("Couldn't nudge — try again");
      }
    } catch {
      store.revert(item.id);
      toast.show("Couldn't nudge — try again");
    } finally {
      setBusy(null);
    }
  };

  const body = (
    <div className="min-w-0 space-y-1">
      <div className="text-sm font-medium text-slate-900">Awaiting external party</div>
      <div className="text-xs text-slate-600">
        reason: <code className="bg-slate-100 px-1.5 py-0.5 rounded">{item.awaitingReason ?? "unspecified"}</code>
      </div>
      <div className="text-[11px] text-slate-500">ages against their SLA, not yours</div>
    </div>
  );

  const actions = hideActions ? null : (
    <>
      <button
        type="button" disabled={busy != null}
        onClick={(e) => { e.stopPropagation(); void nudge(); }}
        className="text-xs px-3 py-1.5 rounded font-medium bg-blue-600 hover:bg-blue-700 text-white disabled:opacity-50"
      >Nudge</button>
      <button
        type="button" disabled={busy != null}
        onClick={(e) => { e.stopPropagation(); onOpenDrawer?.(item.workflowId); }}
        className="text-xs px-3 py-1.5 rounded font-medium bg-white text-slate-700 ring-1 ring-slate-300 hover:bg-slate-50"
      >Reassign</button>
      <button
        type="button" disabled={busy != null}
        onClick={(e) => { e.stopPropagation(); onOpenDrawer?.(item.workflowId); }}
        className="text-xs px-3 py-1.5 rounded font-medium bg-white text-slate-700 ring-1 ring-slate-300 hover:bg-slate-50"
      >View token</button>
    </>
  );

  return (
    <CardShell
      severity={item.severity ?? null}
      icon={<Hourglass size={12} className="text-blue-600" />}
      typeLabel="External wait · Needs you"
      workflowId={item.workflowId}
      timestampSec={item.timestamp}
      body={body}
      actions={actions}
      onPrimaryClick={onOpenDrawer ? () => onOpenDrawer(item.workflowId) : undefined}
    />
  );
}

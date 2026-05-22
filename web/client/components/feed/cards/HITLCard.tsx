// web/client/components/feed/cards/HITLCard.tsx
//
// HITL = workflow currently awaiting human-in-the-loop. The card surfaces
// the receipt (when present), claim summary, fleet-manager recommendation
// (when present), and four inline actions. Clicking an action optimistically
// records a resolution (flips the card to ResolvedCard via useFeedItems'
// overlay) and POSTs to /api/exceptions/{activeExceptionId}/resolve. On
// backend failure the optimistic state is reverted.
import { useState } from "react";
import { Link } from "react-router-dom";
import { AlertTriangle } from "lucide-react";
import type { HITLItem } from "@shared/feedItems";
import CardShell from "../CardShell";
import ReceiptThumb from "./ReceiptThumb";
import { summariseWorkflow } from "./workflowSummary";
import { useResolutionStore } from "@client/hooks/useResolutionStore";
import { apiFetch } from "@client/lib/api";
import { useToast } from "../Toast";

const ACTIONS = [
  { id: "approve",       label: "Approve",      cls: "bg-emerald-600 hover:bg-emerald-700 text-white", verb: "Approved" },
  { id: "request-info",  label: "Request docs", cls: "bg-white dark:bg-slate-900 text-slate-700 dark:text-slate-200 ring-1 ring-slate-300 dark:ring-slate-600 hover:bg-slate-50 dark:hover:bg-slate-800", verb: "Requested docs" },
  { id: "escalate",      label: "Escalate L2",  cls: "bg-white dark:bg-slate-900 text-amber-700 ring-1 ring-amber-300 hover:bg-amber-50", verb: "Escalated" },
  { id: "reject",        label: "Reject",       cls: "bg-white dark:bg-slate-900 text-red-700 ring-1 ring-red-300 hover:bg-red-50", verb: "Rejected" },
] as const;

export default function HITLCard({
  item, hideActions = false, onOpenDrawer,
}: {
  item: HITLItem;
  hideActions?: boolean;
  onOpenDrawer?: (workflowId: string) => void;
}) {
  const w = item.workflow!;
  const store = useResolutionStore();
  const toast = useToast();
  const [busy, setBusy] = useState<string | null>(null);

  const onAction = async (id: string, verb: string) => {
    setBusy(id);
    store.record(item.id, { verb, actor: "you", actedAt: Math.floor(Date.now() / 1000) });
    const exceptionId = w.activeExceptionId;
    const ctrl = new AbortController();
    let undone = false;
    toast.showWithAction({
      msg: `${verb} ${w.id}`,
      ttlMs: 5_000,
      action: {
        label: "Undo",
        onAction: () => {
          undone = true;
          ctrl.abort();
          store.revert(item.id);
        },
      },
    });
    await new Promise((res) => setTimeout(res, 5_000));
    if (undone) {
      setBusy(null);
      return;
    }
    // No backend exception to resolve (HITL view without an activeException):
    // the optimistic local resolution is the only state we need to preserve.
    if (!exceptionId) {
      setBusy(null);
      return;
    }
    try {
      const r = await apiFetch(`/api/exceptions/${exceptionId}/resolve`, {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ resolution: id, resolvedBy: "reviewer@zava" }),
        signal: ctrl.signal,
      });
      if (!r.ok) {
        store.revert(item.id);
        toast.show("Couldn't resolve — try again");
      }
    } catch (err) {
      if ((err as Error).name === "AbortError") return;
      store.revert(item.id);
      toast.show("Couldn't resolve — try again");
    } finally {
      setBusy(null);
    }
  };

  const summary = summariseWorkflow(w);
  const body = (
    <div className="flex gap-3 min-w-0">
      {w.claim ? (
        <ReceiptThumb claimId={w.claim.claimId} flavour={w.claim.receiptMismatchFlavour} />
      ) : null}
      <div className="min-w-0 space-y-0.5">
        <div className="text-sm font-medium text-slate-900 dark:text-slate-100 truncate">{summary.headline}</div>
        {summary.subline ? (
          <div className="text-xs text-slate-500 dark:text-slate-400 truncate">{summary.subline}</div>
        ) : null}
      </div>
    </div>
  );

  const actions = hideActions ? null : (
    <>
      {ACTIONS.map((a) => (
        <button
          key={a.id}
          type="button"
          disabled={busy != null}
          onClick={(e) => { e.stopPropagation(); void onAction(a.id, a.verb); }}
          className={`text-xs px-3 py-1.5 rounded font-medium transition disabled:opacity-50 ${a.cls}`}
        >
          {busy === a.id ? "…" : a.label}
        </button>
      ))}
    </>
  );

  return (
    <CardShell
      severity={item.severity ?? null}
      icon={<AlertTriangle size={12} className="text-amber-600" />}
      typeLabel="HITL · Needs you"
      workflowId={w.id}
      timestampSec={item.timestamp}
      body={body}
      actions={actions}
      onPrimaryClick={
        onOpenDrawer
          ? () => onOpenDrawer(w.id)
          : undefined
      }
    />
  );
}

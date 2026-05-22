// web/client/components/feed/cards/ExceptionCard.tsx
//
// Open exception not yet picked up. Same four resolve actions as HITL plus
// a Snooze 1h that defers (no backend call in v1; sets a local timer to
// re-surface). All actions go through useResolutionStore.
import { useState } from "react";
import { ShieldAlert } from "lucide-react";
import type { ExceptionItem } from "@shared/feedItems";
import CardShell from "../CardShell";
import { summariseWorkflow } from "./workflowSummary";
import { useResolutionStore } from "@client/hooks/useResolutionStore";
import { apiFetch } from "@client/lib/api";
import { useToast } from "../Toast";

const ACTIONS = [
  { id: "approve",       label: "Approve",       cls: "bg-emerald-600 hover:bg-emerald-700 text-white",       verb: "Approved" },
  { id: "request-info",  label: "Request docs",  cls: "bg-white dark:bg-slate-900 text-slate-700 dark:text-slate-200 ring-1 ring-slate-300 dark:ring-slate-600 hover:bg-slate-50 dark:hover:bg-slate-800", verb: "Requested docs" },
  { id: "escalate",      label: "Escalate L2",   cls: "bg-white dark:bg-slate-900 text-amber-700 ring-1 ring-amber-300 hover:bg-amber-50", verb: "Escalated" },
  { id: "reject",        label: "Reject",        cls: "bg-white dark:bg-slate-900 text-red-700 ring-1 ring-red-300 hover:bg-red-50",       verb: "Rejected" },
  { id: "snooze",        label: "Snooze 1h",     cls: "bg-white dark:bg-slate-900 text-slate-600 dark:text-slate-300 ring-1 ring-slate-200 dark:ring-slate-700 hover:bg-slate-50 dark:hover:bg-slate-800", verb: "Snoozed 1h" },
] as const;

export default function ExceptionCard({
  item, hideActions = false, onOpenDrawer,
}: {
  item: ExceptionItem;
  hideActions?: boolean;
  onOpenDrawer?: (workflowId: string) => void;
}) {
  const e = item.exception;
  const store = useResolutionStore();
  const toast = useToast();
  const [busy, setBusy] = useState<string | null>(null);

  const onAction = async (id: string, verb: string) => {
    setBusy(id);
    store.record(item.id, { verb, actor: "you", actedAt: Math.floor(Date.now() / 1000) });
    if (id === "snooze") {
      setBusy(null);
      toast.showWithAction({
        msg: `${verb} ${e.workflowId}`,
        action: { label: "Undo", onAction: () => store.revert(item.id) },
      });
      return;
    }
    // Defer the actual network call by 5s, giving the user a window to
    // click Undo (which aborts the in-flight request before it leaves the
    // browser). Pattern: setTimeout + AbortController.
    const ctrl = new AbortController();
    let undone = false;
    toast.showWithAction({
      msg: `${verb} ${e.workflowId}`,
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
    // Hold the optimistic state for ~5s, then fire. The store.record
    // already flipped the card to ResolvedCard via the overlay so the
    // user sees instant feedback either way.
    await new Promise((res) => setTimeout(res, 5_000));
    if (undone) {
      setBusy(null);
      return;
    }
    try {
      const r = await apiFetch(`/api/exceptions/${e.id}/resolve`, {
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

  const body = (
    <div className="min-w-0 space-y-1">
      {item.workflow ? (
        <div className="text-sm font-medium text-slate-900 dark:text-slate-100 truncate">
          {summariseWorkflow(item.workflow).headline}
        </div>
      ) : (
        <div className="text-sm font-medium text-slate-900 dark:text-slate-100">{e.summary}</div>
      )}
      <div className="text-xs text-slate-600 dark:text-slate-300 line-clamp-2">{e.recommendation}</div>
      {item.workflow ? (
        <div className="text-[11px] text-slate-500 dark:text-slate-400 truncate">
          {summariseWorkflow(item.workflow).subline ?? e.category}
        </div>
      ) : (
        <div className="text-[11px] text-slate-500 dark:text-slate-400">{e.category}</div>
      )}
    </div>
  );

  const actions = hideActions ? null : (
    <>
      {ACTIONS.map((a) => (
        <button
          key={a.id}
          type="button"
          disabled={busy != null}
          onClick={(ev) => { ev.stopPropagation(); void onAction(a.id, a.verb); }}
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
      icon={<ShieldAlert size={12} className="text-red-600" />}
      typeLabel="Exception · Needs you"
      workflowId={e.workflowId}
      timestampSec={item.timestamp}
      body={body}
      actions={actions}
      onPrimaryClick={onOpenDrawer ? () => onOpenDrawer(e.workflowId) : undefined}
    />
  );
}

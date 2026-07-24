// web/client/components/feed/Drawer.tsx
//
// Right-side drawer over the feed. Loads /api/workflows/:id and renders 3
// sections (Decision · Activity · Audit) in the role-dictated order. Esc
// or the ✕ button fires onClose. The drawer width is fluid (50–65 % of
// viewport via Tailwind responsive utilities); below 1024px it's full-screen.
import { useEffect, useState, useCallback, type ReactElement } from "react";
import type {
  WorkflowDetailResponse,
} from "@shared/types";
import type { RolePreset } from "@shared/roles";
import DrawerDecision from "./DrawerDecision";
import DrawerActivity from "./DrawerActivity";
import DrawerAudit from "./DrawerAudit";
import DrawerReasoning from "./DrawerReasoning";

export type DrawerData = WorkflowDetailResponse;

export default function Drawer({
  workflowId, role, onClose,
}: {
  workflowId: string;
  role: RolePreset;
  onClose: () => void;
}) {
  const [d, setD] = useState<DrawerData | null>(null);
  const [notFound, setNotFound] = useState(false);

  const refresh = useCallback(async () => {
    const r = await fetch(`/api/workflows/${workflowId}`);
    if (r.status === 404) {
      setNotFound(true);
      return;
    }
    if (!r.ok) return;
    setNotFound(false);
    setD((await r.json()) as DrawerData);
  }, [workflowId]);

  useEffect(() => {
    setNotFound(false);
    setD(null);
  }, [workflowId]);

  useEffect(() => {
    void refresh();
    if (notFound) return;
    const i = setInterval(() => { void refresh(); }, 2500);
    return () => clearInterval(i);
  }, [refresh, notFound]);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);

  if (notFound) {
    return (
      <aside
        className="fixed inset-y-0 right-0 z-40 w-full lg:w-[65%] xl:w-[60%] 2xl:w-[50%] bg-white dark:bg-slate-900 border-l border-slate-200 dark:border-slate-700 shadow-xl flex flex-col"
        aria-label="Workflow not found"
      >
        <header className="flex items-center gap-3 px-5 h-14 border-b border-slate-200 dark:border-slate-700">
          <div className="font-mono text-sm text-slate-900 dark:text-slate-100">{workflowId}</div>
          <button
            type="button"
            onClick={onClose}
            aria-label="Close drawer"
            className="ml-auto text-slate-400 dark:text-slate-500 hover:text-slate-700 text-lg px-2"
          >✕</button>
        </header>
        <div className="flex-1 overflow-y-auto px-5 py-8 space-y-4">
          <h2 className="text-base font-semibold text-slate-800 dark:text-slate-100">Workflow not found</h2>
          <p className="text-sm text-slate-600 dark:text-slate-300">
            <span className="font-mono">{workflowId}</span> doesn’t match an active workflow. It may have completed and been archived, or the id may be an exception/HITL reference rather than a workflow id.
          </p>
          <button
            type="button"
            onClick={onClose}
            className="text-sm text-blue-600 hover:underline"
          >← Back to feed</button>
        </div>
      </aside>
    );
  }

  if (!d) {
    return (
      <aside className="fixed inset-y-0 right-0 z-40 w-full lg:w-[65%] xl:w-[60%] 2xl:w-[50%] bg-white dark:bg-slate-900 border-l border-slate-200 dark:border-slate-700 shadow-xl flex flex-col">
        <div className="p-4 text-sm text-slate-500 dark:text-slate-400">loading…</div>
      </aside>
    );
  }

  const sections: Record<string, ReactElement> = {
    decision: (
      <DrawerDecision data={d} role={role} onRefresh={refresh} />
    ),
    reasoning: (
      <DrawerReasoning data={d} />
    ),
    activity: (
      <DrawerActivity data={d} />
    ),
    audit: (
      <DrawerAudit data={d} />
    ),
  };

  return (
    <aside
      className="fixed inset-y-0 right-0 z-40 w-full lg:w-[65%] xl:w-[60%] 2xl:w-[50%] bg-white dark:bg-slate-900 border-l border-slate-200 dark:border-slate-700 shadow-xl flex flex-col"
      aria-label="Workflow detail drawer"
    >
      <header className="flex items-center gap-3 px-5 h-14 border-b border-slate-200 dark:border-slate-700">
        <div className="font-mono text-sm text-slate-900 dark:text-slate-100">{d.workflow.id}</div>
        <span className="text-[10px] uppercase tracking-wide bg-slate-100 dark:bg-slate-800 text-slate-600 dark:text-slate-300 px-1.5 py-0.5 rounded">
          {d.workflow.type}
        </span>
        <span className="text-[10px] uppercase tracking-wide bg-amber-50 text-amber-700 px-1.5 py-0.5 rounded">
          {d.workflow.status}
        </span>
        <button
          type="button"
          onClick={onClose}
          aria-label="Close drawer"
          className="ml-auto text-slate-400 dark:text-slate-500 hover:text-slate-700 text-lg px-2"
        >✕</button>
      </header>
      <div className="flex-1 overflow-y-auto px-5 py-4 space-y-6">
        {role.drawerSectionOrder.map((s) => (
          <div key={s}>{sections[s]}</div>
        ))}
      </div>
    </aside>
  );
}

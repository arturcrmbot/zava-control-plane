// web/client/components/feed/Drawer.tsx
//
// Right-side drawer over the feed. Loads /api/workflows/:id and renders 3
// sections (Decision · Activity · Audit) in the role-dictated order. Esc
// or the ✕ button fires onClose. The drawer width is fluid (50–65 % of
// viewport via Tailwind responsive utilities); below 1024px it's full-screen.
import { useEffect, useState, useCallback } from "react";
import type {
  Workflow, Phase, OtelSpan, Exception, SkillAmplification,
  McpCall, Economics, Narrative,
} from "@shared/types";
import type { RolePreset } from "@shared/roles";
import DrawerDecision from "./DrawerDecision";
import DrawerActivity from "./DrawerActivity";
import DrawerAudit from "./DrawerAudit";

export interface DrawerData {
  workflow: Workflow;
  phases: Phase[];
  spans: OtelSpan[];
  amplifications: SkillAmplification[];
  activeException: Exception | null;
  mcpCalls: McpCall[];
  economics: Economics;
  narrative: Narrative | null;
  auditBlobUrl?: string | null;
}

export default function Drawer({
  workflowId, role, onClose,
}: {
  workflowId: string;
  role: RolePreset;
  onClose: () => void;
}) {
  const [d, setD] = useState<DrawerData | null>(null);

  const refresh = useCallback(async () => {
    const r = await fetch(`/api/workflows/${workflowId}`);
    setD((await r.json()) as DrawerData);
  }, [workflowId]);

  useEffect(() => {
    void refresh();
    const i = setInterval(() => { void refresh(); }, 2500);
    return () => clearInterval(i);
  }, [refresh]);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);

  if (!d) {
    return (
      <aside className="fixed inset-y-0 right-0 z-40 w-full lg:w-[65%] xl:w-[60%] 2xl:w-[50%] bg-white dark:bg-slate-900 border-l border-slate-200 dark:border-slate-700 shadow-xl flex flex-col">
        <div className="p-4 text-sm text-slate-500 dark:text-slate-400">loading…</div>
      </aside>
    );
  }

  const sections: Record<string, JSX.Element> = {
    decision: (
      <DrawerDecision data={d} role={role} onRefresh={refresh} />
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
        <DomainDeepLink workflow={d.workflow} />
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

function DomainDeepLink({ workflow }: { workflow: Workflow }) {
  // Preserves cross-app deep-links carried over from WorkflowDetail.tsx.
  const candidateId = (workflow.metadata as { candidate_id?: string } | undefined)?.candidate_id;
  if (workflow.type === "hiring" && candidateId) {
    return (
      <a
        href={`http://localhost:5274/recruiter/c/${encodeURIComponent(candidateId)}`}
        target="_blank" rel="noreferrer"
        className="text-xs text-blue-600 hover:underline"
      >open in recruiter view ↗</a>
    );
  }
  return null;
}

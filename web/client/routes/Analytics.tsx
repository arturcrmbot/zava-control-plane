// src/client/routes/Analytics.tsx
import { useMemo } from "react";
import { useWorkflows } from "../hooks/useWorkflows";
import { useExceptions } from "../hooks/useExceptions";
import type { Workflow } from "@shared/types";

const CATEGORY_COLOR: Record<string, string> = {
  meals: "bg-amber-400",
  travel: "bg-blue-400",
  accommodation: "bg-purple-400",
  entertainment: "bg-pink-400",
  miscellaneous: "bg-slate-400",
};

const PHASE_COLOR: Record<string, string> = {
  Intake: "bg-slate-400",
  Classify: "bg-blue-400",
  "Validate Receipt": "bg-indigo-400",
  Route: "bg-amber-400",
  Notify: "bg-orange-400",
  Arbitrate: "bg-purple-400",
  Audit: "bg-emerald-400",
};

function StackedBar({ buckets, total, palette }: {
  buckets: Array<{ key: string; n: number }>; total: number;
  palette: Record<string, string>;
}) {
  if (total === 0) {
    return <div className="text-xs text-slate-400 dark:text-slate-500 italic">no data yet</div>;
  }
  return (
    <div className="space-y-2">
      <div className="flex h-3 rounded overflow-hidden bg-slate-100 dark:bg-slate-800">
        {buckets.map(b => (
          <div
            key={b.key}
            className={`${palette[b.key] ?? "bg-slate-300"} h-3`}
            style={{ width: `${(b.n / total) * 100}%` }}
            title={`${b.key}: ${b.n}`}
          />
        ))}
      </div>
      <div className="grid grid-cols-2 gap-1 text-[11px]">
        {buckets.map(b => (
          <div key={b.key} className="flex items-center gap-1.5">
            <span className={`inline-block w-2 h-2 rounded-sm ${palette[b.key] ?? "bg-slate-300"}`} />
            <span className="text-slate-600 dark:text-slate-300 capitalize">{b.key}</span>
            <span className="ml-auto text-slate-900 dark:text-slate-100 font-medium tabular-nums">{b.n}</span>
          </div>
        ))}
      </div>
    </div>
  );
}

function Bucket(workflows: Workflow[], get: (w: Workflow) => string | undefined) {
  const map: Record<string, number> = {};
  for (const w of workflows) {
    const k = get(w);
    if (!k) continue;
    map[k] = (map[k] ?? 0) + 1;
  }
  return Object.entries(map).sort((a, b) => b[1] - a[1]).map(([key, n]) => ({ key, n }));
}

export default function Analytics() {
  const workflows = useWorkflows();
  const { items: exceptions } = useExceptions();

  const m = useMemo(() => {
    const total = workflows.length;
    const completed = workflows.filter(w => w.status === "completed").length;
    const inFlight = workflows.filter(w => w.status === "in_progress").length;
    const awaiting = workflows.filter(w => w.status === "awaiting_hitl").length;
    const failed = workflows.filter(w => w.status === "failed").length;
    const humanTouched = workflows.filter(w =>
      w.actionLedger?.some(a => a.actorKind === "human")
    ).length;
    const interventionRate = total ? humanTouched / total : 0;
    const exceptionRate = total ? exceptions.length / total : 0;

    // Average resolution time across completed
    const resolutionTimes: number[] = [];
    for (const w of workflows) {
      if (w.status !== "completed") continue;
      const completedEntry = w.actionLedger?.find(a => a.action === "workflow.completed");
      if (completedEntry) {
        resolutionTimes.push(completedEntry.timestamp - w.createdAt);
      }
    }
    const avgResolutionSec = resolutionTimes.length
      ? resolutionTimes.reduce((a, b) => a + b, 0) / resolutionTimes.length
      : 0;

    const expense = workflows.filter(w => w.type === "expense-claim" && w.claim);
    const totalUsdEquivalent = expense.reduce((sum, w) => {
      const fx: Record<string, number> = { USD: 1.0, GBP: 1.27, EUR: 1.08, INR: 0.012 };
      return sum + (w.claim!.amount * (fx[w.claim!.currency] ?? 1.0));
    }, 0);

    const byCategory = Bucket(expense, w => w.claim?.category);
    const byPhase = Bucket(workflows, w => w.currentPhase);
    const byVerdict = Bucket(workflows, w => w.verdict ?? undefined);
    const byEms = Bucket(expense, w => w.claim?.emsSource);
    const byMarket = Bucket(expense, w => w.claim?.market);

    return {
      total, completed, inFlight, awaiting, failed,
      interventionRate, exceptionRate, avgResolutionSec,
      totalUsdEquivalent,
      byCategory, byPhase, byVerdict, byEms, byMarket,
    };
  }, [workflows, exceptions]);

  const cards = [
    { label: "Workflows processed", v: m.total.toLocaleString() },
    { label: "Auto-completed", v: m.completed.toLocaleString(), sub: `${m.total ? Math.round((m.completed / m.total) * 100) : 0}% straight-through` },
    { label: "Human intervention rate", v: `${(m.interventionRate * 100).toFixed(1)}%` },
    { label: "Avg resolution time", v: m.avgResolutionSec ? `${Math.round(m.avgResolutionSec)}s` : "—" },
    { label: "Open exceptions", v: exceptions.length.toLocaleString(), sub: `${(m.exceptionRate * 100).toFixed(1)}% rate` },
    { label: "Spend under management", v: `$${Math.round(m.totalUsdEquivalent).toLocaleString()}`, sub: "USD equivalent" },
  ];

  return (
    <div className="space-y-4">
      <div>
        <div className="text-lg font-semibold text-slate-900 dark:text-slate-100">Analytics</div>
        <div className="text-xs text-slate-500 dark:text-slate-400">Live fleet telemetry across {m.total} workflows</div>
      </div>

      <div className="grid grid-cols-2 lg:grid-cols-3 gap-3">
        {cards.map(c => (
          <div key={c.label} className="panel panel-body">
            <div className="text-[11px] uppercase tracking-wide text-slate-500 dark:text-slate-400">{c.label}</div>
            <div className="text-2xl font-semibold text-slate-900 dark:text-slate-100 mt-1 tabular-nums">{c.v}</div>
            {c.sub && <div className="text-[11px] text-slate-500 dark:text-slate-400 mt-0.5">{c.sub}</div>}
          </div>
        ))}
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-3">
        <div className="panel">
          <div className="panel-header">By category</div>
          <div className="panel-body">
            <StackedBar buckets={m.byCategory} total={m.byCategory.reduce((s, b) => s + b.n, 0)} palette={CATEGORY_COLOR} />
          </div>
        </div>
        <div className="panel">
          <div className="panel-header">By phase</div>
          <div className="panel-body">
            <StackedBar buckets={m.byPhase} total={m.byPhase.reduce((s, b) => s + b.n, 0)} palette={PHASE_COLOR} />
          </div>
        </div>
        <div className="panel">
          <div className="panel-header">By EMS source</div>
          <div className="panel-body">
            <StackedBar buckets={m.byEms} total={m.byEms.reduce((s, b) => s + b.n, 0)} palette={{ workday: "bg-blue-500", concur: "bg-emerald-500" }} />
          </div>
        </div>
        <div className="panel">
          <div className="panel-header">By market</div>
          <div className="panel-body">
            <StackedBar buckets={m.byMarket} total={m.byMarket.reduce((s, b) => s + b.n, 0)} palette={{ UK: "bg-blue-500", US: "bg-red-500", DE: "bg-amber-500", IN: "bg-emerald-500" }} />
          </div>
        </div>
      </div>
    </div>
  );
}

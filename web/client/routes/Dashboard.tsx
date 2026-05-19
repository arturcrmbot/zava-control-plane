// web/client/routes/Dashboard.tsx
//
// At-a-glance KPI page for the Fleet Control feed. Computes everything
// client-side from the live useWorkflows + useExceptions hooks (so it
// follows the same multiplexed SSE connection the feed itself uses).
//
// Sections:
//   1. Top tiles: open exceptions, critical, awaiting HITL, throughput-1h
//   2. By-domain breakdown (counts + critical fraction)
//   3. Activity over the last hour (sparkline-ish bar chart, 5-min buckets)
//   4. Last 10 resolutions (local optimistic, from useResolutionStore)
import { useMemo } from "react";
import { Link } from "react-router-dom";
import { ArrowLeft, AlertTriangle, Inbox, Users, Activity } from "lucide-react";
import { useWorkflows } from "@client/hooks/useWorkflows";
import { useExceptions } from "@client/hooks/useExceptions";
import { useResolutionStore } from "@client/hooks/useResolutionStore";
import { useNow } from "@client/hooks/useNow";
import { usePersonaDecisions } from "@client/hooks/usePersonaDecisions";

interface Tile {
  label: string;
  value: string | number;
  sub?: string;
  icon: React.ReactNode;
  accent: string;
}

function KpiTile({ label, value, sub, icon, accent }: Tile) {
  return (
    <div className="bg-white border border-slate-200 rounded-lg p-4 flex items-start gap-3 dark:bg-slate-900 dark:border-slate-700">
      <div className={`p-2 rounded ${accent}`}>{icon}</div>
      <div className="min-w-0">
        <div className="text-[11px] uppercase tracking-wide text-slate-500 dark:text-slate-400">{label}</div>
        <div className="text-2xl font-semibold text-slate-900 dark:text-slate-100 tabular-nums leading-tight">{value}</div>
        {sub && <div className="text-xs text-slate-500 dark:text-slate-400 mt-0.5">{sub}</div>}
      </div>
    </div>
  );
}

export default function Dashboard() {
  // 30s re-render cadence is enough for KPI display; the underlying data
  // hooks update via SSE so values are always fresh — useNow just ticks
  // the "X minutes ago" labels.
  useNow(30_000);
  const workflows = useWorkflows();
  const { items: exceptions } = useExceptions();
  const resolutions = useResolutionStore();
  const personaDecisions = usePersonaDecisions({ limit: 200 });

  const stats = useMemo(() => {
    const openExceptions = exceptions.filter((e) => !e.resolvedAt);
    const critical = openExceptions.filter((e) => e.severity === "critical").length;
    const high = openExceptions.filter((e) => e.severity === "high").length;
    const awaitingHITL = workflows.filter((w) => w.status === "awaiting_hitl").length;
    const completed = workflows.filter((w) => w.status === "completed");
    const now = Date.now() / 1000;
    const completed1h = completed.filter((w) => {
      const ts = (w as { updatedAt?: number; createdAt?: number }).updatedAt
        ?? (w as { createdAt?: number }).createdAt
        ?? 0;
      return ts > now - 3600;
    }).length;

    // Resolve exception → workflow domain via a lookup table.
    const workflowDomain = new Map<string, string>();
    for (const w of workflows) workflowDomain.set(w.id, w.type);

    const byDomain = new Map<string, { total: number; critical: number }>();
    for (const e of openExceptions) {
      const d = workflowDomain.get(e.workflowId) ?? "unknown";
      const slot = byDomain.get(d) ?? { total: 0, critical: 0 };
      slot.total += 1;
      if (e.severity === "critical") slot.critical += 1;
      byDomain.set(d, slot);
    }
    const domainRows = [...byDomain.entries()]
      .map(([domain, v]) => ({ domain, ...v }))
      .sort((a, b) => b.total - a.total);

    // 12 × 5-minute buckets covering the past hour. Uses Exception.createdAt
    // (set by the producer when the exception was raised).
    const buckets = Array.from({ length: 12 }, () => 0);
    for (const e of openExceptions) {
      const age = now - (e.createdAt ?? 0);
      if (age < 0 || age >= 3600) continue;
      const idx = 11 - Math.floor(age / 300);
      if (idx >= 0 && idx < 12) buckets[idx] += 1;
    }
    const bucketMax = Math.max(1, ...buckets);

    return {
      openExceptions: openExceptions.length,
      critical, high, awaitingHITL, completed1h,
      domainRows, buckets, bucketMax,
    };
  }, [workflows, exceptions]);

  const recentResolutions = useMemo(() => {
    const entries = Object.entries(resolutions.all())
      .map(([itemId, r]) => ({ itemId, ...r }))
      .sort((a, b) => b.actedAt - a.actedAt)
      .slice(0, 10);
    return entries;
  }, [resolutions]);

  // Merge persona Decision nodes with the operator's own resolutions into
  // a single chronological list. The shape is intentionally narrow so the
  // existing "Recent decisions" UI can render either source uniformly.
  type MergedDecision =
    | {
        kind: "operator";
        key: string;
        verb: string;
        actor: string;
        target: string;
        actedAt: number;
      }
    | {
        kind: "persona";
        key: string;
        verb: string;
        actor: string;
        target: string;
        actedAt: number;
        phase: string;
        reason: string;
      };

  const mergedRecentDecisions = useMemo<MergedDecision[]>(() => {
    const operatorRows: MergedDecision[] = recentResolutions.map((r) => ({
      kind: "operator",
      key: `op:${r.itemId}`,
      verb: r.verb,
      actor: r.actor || "you",
      target: r.itemId,
      actedAt: r.actedAt,
    }));
    const personaRows: MergedDecision[] = personaDecisions.map((d) => ({
      kind: "persona",
      key: `ai:${d.id}`,
      verb: d.verdict,
      actor: d.personaRole,
      target: d.workflowId,
      actedAt: d.decidedAtSec,
      phase: d.phase,
      reason: d.reason,
    }));
    return [...operatorRows, ...personaRows]
      .sort((a, b) => b.actedAt - a.actedAt)
      .slice(0, 12);
  }, [recentResolutions, personaDecisions]);

  // KPI tile shows everything decided in the last hour (operator + persona),
  // not just the lifetime operator click count.
  const decisionsLastHour = useMemo(() => {
    const cutoff = Date.now() / 1000 - 3600;
    return mergedRecentDecisions.filter((d) => d.actedAt >= cutoff).length;
  }, [mergedRecentDecisions]);

  return (
    <div className="flex-1 min-w-0 overflow-y-auto bg-slate-50 dark:bg-slate-950 p-6">
      <div className="max-w-5xl mx-auto space-y-6">
        <div className="flex items-center gap-3">
          <Link
            to="/"
            className="text-xs text-slate-500 hover:text-slate-800 flex items-center gap-1 dark:text-slate-400 dark:hover:text-slate-100"
          ><ArrowLeft size={14} /> Back to feed</Link>
        </div>
        <h1 className="text-xl font-semibold text-slate-900 dark:text-slate-100">Dashboard</h1>

        <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
          <KpiTile
            label="Open exceptions"
            value={stats.openExceptions}
            sub={`${stats.critical} crit · ${stats.high} high`}
            icon={<AlertTriangle size={16} className="text-red-600 dark:text-red-400" />}
            accent="bg-red-50 dark:bg-red-950/30"
          />
          <KpiTile
            label="Awaiting HITL"
            value={stats.awaitingHITL}
            sub="workflows blocked on a human"
            icon={<Inbox size={16} className="text-amber-600 dark:text-amber-400" />}
            accent="bg-amber-50 dark:bg-amber-950/30"
          />
          <KpiTile
            label="Completed (1h)"
            value={stats.completed1h}
            sub="throughput last hour"
            icon={<Activity size={16} className="text-emerald-600 dark:text-emerald-400" />}
            accent="bg-emerald-50 dark:bg-emerald-950/30"
          />
          <KpiTile
            label="Recent decisions"
            value={decisionsLastHour}
            sub="last hour · personas + operators"
            icon={<Users size={16} className="text-blue-600 dark:text-blue-400" />}
            accent="bg-blue-50 dark:bg-blue-950/30"
          />
        </div>

        <section className="bg-white border border-slate-200 rounded-lg dark:bg-slate-900 dark:border-slate-700">
          <header className="px-4 py-3 border-b border-slate-200 text-sm font-semibold text-slate-800 dark:border-slate-700 dark:text-slate-100">
            Exceptions arriving (last hour, 5-minute buckets)
          </header>
          <div className="p-4 flex items-end gap-1 h-32">
            {stats.buckets.map((n, i) => (
              <div
                key={i}
                title={`${n} arrivals · ${(11 - i) * 5}-${(12 - i) * 5} minutes ago`}
                className="flex-1 bg-blue-500/70 dark:bg-blue-400/80 rounded-t"
                style={{ height: `${Math.max(2, (n / stats.bucketMax) * 100)}%` }}
              />
            ))}
          </div>
          <div className="flex justify-between px-4 pb-3 text-[10px] text-slate-400 dark:text-slate-500">
            <span>60m ago</span>
            <span>now</span>
          </div>
        </section>

        <section className="bg-white border border-slate-200 rounded-lg dark:bg-slate-900 dark:border-slate-700">
          <header className="px-4 py-3 border-b border-slate-200 text-sm font-semibold text-slate-800 dark:border-slate-700 dark:text-slate-100">
            Open exceptions by domain
          </header>
          {stats.domainRows.length === 0 ? (
            <div className="p-6 text-center text-xs text-slate-500 dark:text-slate-400">No open exceptions.</div>
          ) : (
            <table className="w-full text-xs">
              <thead className="text-[10px] uppercase tracking-wide text-slate-500 dark:text-slate-400 border-b border-slate-200 dark:border-slate-700">
                <tr>
                  <th className="text-left px-4 py-2 font-medium">Domain</th>
                  <th className="text-right px-4 py-2 font-medium">Total</th>
                  <th className="text-right px-4 py-2 font-medium">Critical</th>
                  <th className="text-left px-4 py-2 font-medium w-1/3">Distribution</th>
                </tr>
              </thead>
              <tbody>
                {stats.domainRows.map((r) => {
                  const max = stats.domainRows[0]?.total ?? 1;
                  return (
                    <tr key={r.domain} className="border-b border-slate-100 last:border-0 dark:border-slate-800">
                      <td className="px-4 py-2 text-slate-700 dark:text-slate-200">{r.domain}</td>
                      <td className="px-4 py-2 text-right tabular-nums text-slate-700 dark:text-slate-200">{r.total}</td>
                      <td className="px-4 py-2 text-right tabular-nums">
                        {r.critical > 0 ? (
                          <span className="text-red-600 dark:text-red-400 font-medium">{r.critical}</span>
                        ) : (
                          <span className="text-slate-400 dark:text-slate-500">0</span>
                        )}
                      </td>
                      <td className="px-4 py-2">
                        <div className="h-2 bg-slate-100 dark:bg-slate-800 rounded overflow-hidden">
                          <div
                            className="h-full bg-blue-500 dark:bg-blue-400"
                            style={{ width: `${(r.total / max) * 100}%` }}
                          />
                        </div>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          )}
        </section>

        {mergedRecentDecisions.length > 0 && (
          <section className="bg-white border border-slate-200 rounded-lg dark:bg-slate-900 dark:border-slate-700">
            <header className="px-4 py-3 border-b border-slate-200 text-sm font-semibold text-slate-800 dark:border-slate-700 dark:text-slate-100 flex items-center justify-between">
              <span>Recent decisions</span>
              <span className="text-[10px] font-normal uppercase tracking-wide text-slate-400 dark:text-slate-500">
                personas + operators
              </span>
            </header>
            <ul className="divide-y divide-slate-100 dark:divide-slate-800">
              {mergedRecentDecisions.map((r) => {
                const isPersona = r.kind === "persona";
                const badge = isPersona ? "persona" : "you";
                const badgeClass = isPersona
                  ? "bg-indigo-100 text-indigo-700 dark:bg-indigo-950/60 dark:text-indigo-300"
                  : "bg-emerald-100 text-emerald-700 dark:bg-emerald-950/60 dark:text-emerald-300";
                const phaseTag = isPersona && r.phase ? ` · ${r.phase}` : "";
                return (
                  <li
                    key={r.key}
                    className="px-4 py-2 flex items-center gap-3 text-xs"
                    title={isPersona ? r.reason : undefined}
                  >
                    <span
                      className={`text-[10px] font-semibold uppercase tracking-wide px-1.5 py-0.5 rounded shrink-0 ${badgeClass}`}
                    >
                      {badge}
                    </span>
                    <span className="font-medium text-slate-800 dark:text-slate-200 w-20 shrink-0 truncate">
                      {r.verb}
                    </span>
                    <span className="text-slate-600 dark:text-slate-400 w-32 shrink-0 truncate">
                      {r.actor}
                    </span>
                    <span className="font-mono text-slate-600 dark:text-slate-400 truncate">
                      {r.target}
                      {phaseTag}
                    </span>
                    <span className="ml-auto text-slate-400 dark:text-slate-500 tabular-nums shrink-0">
                      {r.actedAt > 0
                        ? new Date(r.actedAt * 1000).toLocaleTimeString()
                        : "—"}
                    </span>
                  </li>
                );
              })}
            </ul>
          </section>
        )}
      </div>
    </div>
  );
}

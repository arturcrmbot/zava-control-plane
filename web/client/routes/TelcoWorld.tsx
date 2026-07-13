// web/client/routes/TelcoWorld.tsx
//
// The /world view when ZAVA_WORLD=telco: a real cell-site floor where every
// card is an actual CellSite actor from /api/world/state and every token a
// real NetworkSession. The Durable intervention strip and failed-site /
// neighbour highlighting are driven entirely by the causal journal. No chart,
// map, canvas or KPI table.
import { useMemo, useState } from "react";
import { RadioTower, AlertTriangle, Zap } from "lucide-react";
import {
  type WorldEvent,
  type WorldState,
  type WorldSite,
  type WorldSession,
} from "@client/hooks/useWorldSimulation";
import { deriveCommonIntervention, type InterventionStep } from "@client/lib/worldIntervention";

const REGIONS = ["north", "east", "south", "west"] as const;
const TOKEN_CAP = 24;
const JOURNAL_CAP = 30;

function pct(n: number | undefined): number {
  return Math.round((n ?? 0) * 100);
}
function round(n: number | undefined): number {
  return Math.round(n ?? 0);
}

// -- Durable causal chain, derived from the network.anomaly trace ------------

interface NetIntervention {
  trace: string;
  incidentSiteId: string | null;
  steps: InterventionStep[];
  reroutedSessionIds: string[];
}
function deriveIntervention(events: WorldEvent[]): NetIntervention | null {
  const common = deriveCommonIntervention(
    events,
    (e) => e.type === "sensor.tripped" && Boolean(((e.payload?.measurements as Record<string, unknown>) ?? {}).site_id),
    {
      pressureLabel: "Anomaly detected",
      pressureDetail: (e) => String(((e.payload?.measurements as Record<string, unknown>) ?? {}).site_id ?? ""),
    },
  );
  if (!common) return null;
  const { trace, traceEvents, steps } = common;

  const tripped = traceEvents.find((e) => e.type === "sensor.tripped");
  const trippedSiteId = tripped ? String(((tripped.payload?.measurements as Record<string, unknown>) ?? {}).site_id ?? "") : "";
  const incidentSiteId = trippedSiteId || null;

  // Scenario-specific tail: sessions rerouted away from the failed site, then
  // the site's eventual recovery.
  const reroutes = traceEvents.filter((e) => e.type === "session.rerouted");
  const reroutedSessionIds = reroutes.map((e) => e.actor_id).filter((id): id is string => Boolean(id));
  if (reroutedSessionIds.length > 0) {
    steps.push({ label: `${reroutedSessionIds.length} sessions rerouted`, eventId: reroutes[reroutes.length - 1].event_id });
  }
  const recovered = traceEvents.find((e) => e.type === "site.recovered");
  if (recovered) steps.push({ label: "Site recovered", eventId: recovered.event_id });

  return { trace, incidentSiteId, steps, reroutedSessionIds };
}

export default function TelcoWorld({
  state, events, loading, error, onFailSite,
}: {
  state: WorldState;
  events: WorldEvent[];
  loading: boolean;
  error: string | null;
  onFailSite: () => Promise<void>;
}) {
  const [busy, setBusy] = useState(false);
  const [selected, setSelected] = useState<string | null>(null);
  const toggle = (id: string | null) => setSelected((c) => (c === id ? null : id));
  const sites = state.sites ?? [];
  const sessions = state.sessions ?? [];
  const intervention = useMemo(() => deriveIntervention(events), [events]);
  // Persisted incident site from the journal (survives fast recovery), plus
  // its neighbours for the affected-relationship highlight.
  const incidentSiteId = useMemo(() => {
    let id: string | null = null;
    for (const e of events) if (e.type === "site.failed" && e.actor_id) id = e.actor_id;
    return id ?? intervention?.incidentSiteId ?? null;
  }, [events, intervention]);
  const incidentSite = sites.find((s) => s.id === incidentSiteId) ?? null;
  const neighborIds = useMemo(() => new Set(incidentSite?.neighbor_ids ?? []), [incidentSite]);
  const byStatus = (st: WorldSession["status"]) => sessions.filter((s) => s.status === st);
  const active = byStatus("active");
  const degraded = byStatus("degraded");
  const rerouted = byStatus("rerouted");
  const dropped = byStatus("dropped");
  const recentRefs = useMemo(() => {
    const map = new Map<string, number>();
    for (const e of events) {
      if (e.actor_id) map.set(e.actor_id, e.seq);
      if (e.target_id) map.set(e.target_id, e.seq);
    }
    return map;
  }, [events]);
  const journal = useMemo(() => {
    const src = selected
      ? events.filter((e) => e.actor_id === selected || e.target_id === selected || e.trace_id === selected)
      : events;
    return src.slice(-JOURNAL_CAP).reverse();
  }, [events, selected]);
  async function handleFail() {
    setBusy(true);
    try { await onFailSite(); } finally { setBusy(false); }
  }
  const lanes: Array<{ id: string; title: string; list: WorldSession[]; tone: string }> = [
    { id: "degraded", title: "Degraded", list: degraded, tone: "text-red-600 dark:text-red-400" },
    { id: "rerouted", title: "Rerouted", list: rerouted, tone: "text-emerald-600 dark:text-emerald-400" },
    { id: "dropped", title: "Dropped", list: dropped, tone: "text-slate-500" },
    { id: "active", title: "Active", list: active, tone: "text-slate-600 dark:text-slate-300" },
  ];

  return (
    <div data-testid="telco-world-route" className="flex-1 min-w-0 overflow-y-auto bg-slate-50 dark:bg-slate-950 p-6">
      <div className="max-w-[1400px] mx-auto space-y-4">
        <header className="flex flex-wrap items-center justify-between gap-3">
          <div className="flex items-center gap-3">
            <RadioTower size={20} className="text-blue-600 dark:text-blue-400" />
            <div>
              <h1 className="text-xl font-semibold text-slate-900 dark:text-slate-100">Network</h1>
              <div className="text-xs text-slate-500 dark:text-slate-400 flex flex-wrap gap-x-3 tabular-nums">
                <span>t = {round(state.sim_time)}m</span>
                <span>seed {state.seed ?? "—"}</span>
                <span>status {state.status ?? "—"}</span>
                <span data-testid="stat-sites">{sites.length} sites</span>
                <span data-testid="stat-sessions">{sessions.length} sessions</span>
                <span data-testid="stat-subscribers">{state.subscribers?.length ?? 0} subscribers</span>
              </div>
            </div>
          </div>
          <button
            type="button"
            data-testid="inject-site-failure"
            disabled={!state.enabled || busy}
            onClick={handleFail}
            className="text-xs px-3 py-1.5 rounded font-medium bg-red-600 text-white hover:bg-red-700 disabled:opacity-50 disabled:cursor-not-allowed flex items-center gap-1.5"
          ><Zap size={14} /> {busy ? "Failing…" : "Fail site"}</button>
        </header>
        {error && (
          <div data-testid="telco-error" className="flex items-center gap-2 text-xs px-3 py-2 rounded border border-red-300 dark:border-red-800 bg-red-50 dark:bg-red-950/40 text-red-700 dark:text-red-300">
            <AlertTriangle size={14} /> {error}
          </div>
        )}
        {intervention && (
          <section data-testid="telco-intervention" className="rounded-lg border border-emerald-300 dark:border-emerald-800 bg-emerald-50 dark:bg-emerald-950/30 p-3">
            <div className="flex items-center justify-between pb-2">
              <h2 className="text-[11px] font-semibold uppercase tracking-wide text-emerald-700 dark:text-emerald-400">Durable intervention</h2>
              <button type="button" onClick={() => toggle(intervention.trace)} className="text-[11px] font-mono text-emerald-700 dark:text-emerald-400 hover:underline">{intervention.trace}</button>
            </div>
            <ol className="flex flex-wrap items-center gap-x-1.5 gap-y-1 text-xs text-slate-700 dark:text-slate-200">
              {intervention.steps.map((step, i) => (
                <li key={step.eventId} className="flex items-center gap-1.5">
                  {i > 0 && <span className="text-emerald-500">→</span>}
                  <span className="font-medium">{step.label}</span>
                  {step.detail && <span className="font-mono text-[10px] text-slate-500 dark:text-slate-400">{step.detail}</span>}
                </li>
              ))}
            </ol>
          </section>
        )}
        <section data-testid="site-floor" className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-4 gap-3">
          {REGIONS.map((region) => (
            <div key={region} data-testid={`region-${region}`} className="rounded-lg border border-slate-200 dark:border-slate-800 bg-slate-100/60 dark:bg-slate-900/40 p-2">
              <div className="px-1 pb-2 text-[11px] font-semibold uppercase tracking-wide text-slate-500 dark:text-slate-400">{region}</div>
              <div className="space-y-1.5">
                {sites.filter((s) => s.region === region).sort((a, b) => a.id.localeCompare(b.id)).map((s) => (
                  <SiteCard
                    key={`${s.id}:${recentRefs.get(s.id) ?? 0}`}
                    site={s}
                    incident={s.id === incidentSiteId}
                    neighbor={neighborIds.has(s.id)}
                    selected={selected === s.id}
                    onClick={() => toggle(s.id)}
                  />
                ))}
              </div>
            </div>
          ))}
        </section>
        <section className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-4 gap-3">
          {lanes.map((lane) => (
            <div key={lane.id} data-testid={`session-lane-${lane.id}`} className="rounded-lg border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 p-2">
              <div className="flex items-baseline justify-between px-1 pb-2">
                <h2 className={`text-[11px] font-semibold uppercase tracking-wide ${lane.tone}`}>{lane.title}</h2>
                <span data-testid={`session-count-${lane.id}`} className="text-[11px] tabular-nums text-slate-500 dark:text-slate-400">{lane.list.length}</span>
              </div>
              <div className="flex flex-wrap gap-1">
                {lane.list.length === 0 ? (
                  <div className="text-[11px] text-slate-400 dark:text-slate-600 px-1 py-1">none</div>
                ) : lane.list.slice(0, TOKEN_CAP).map((s) => (
                  <button key={s.id} type="button" data-testid={`session-${s.id}`} onClick={() => toggle(s.id)}
                    title={`${s.id} · ${s.kind} · ${s.demand_mbps}mbps · ${s.site_id}`}
                    className={`text-[10px] font-mono px-1 py-0.5 rounded border ${s.kind === "voice" ? "border-blue-300 dark:border-blue-800" : "border-slate-200 dark:border-slate-700"} ${selected === s.id ? "bg-blue-100 dark:bg-blue-900/40" : "bg-slate-50 dark:bg-slate-800/40"}`}
                  >{s.id.replace("SESSION-", "S-")}</button>
                ))}
                {lane.list.length > TOKEN_CAP && (
                  <span className="text-[10px] text-slate-400 dark:text-slate-600 px-1 py-0.5">+{lane.list.length - TOKEN_CAP}</span>
                )}
              </div>
            </div>
          ))}
        </section>
        <section data-testid="telco-journal" className="rounded-lg border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 p-3">
          <div className="flex items-center justify-between pb-2">
            <h2 className="text-[11px] font-semibold uppercase tracking-wide text-slate-500 dark:text-slate-400">Recent events</h2>
            {selected && <button type="button" onClick={() => setSelected(null)} className="text-[11px] text-blue-600 dark:text-blue-400 hover:underline">filtering {selected} · clear</button>}
          </div>
          <ul className="divide-y divide-slate-100 dark:divide-slate-800 font-mono text-[11px]">
            {journal.length === 0 ? (
              <li className="py-2 text-slate-400 dark:text-slate-600">no events</li>
            ) : journal.map((e) => (
              <li key={e.seq} data-testid={`event-${e.seq}`} className="py-1 flex items-center gap-2">
                <span className="tabular-nums text-slate-400 dark:text-slate-500 w-12 shrink-0">{round(e.sim_time)}m</span>
                <span className="text-slate-700 dark:text-slate-200 w-44 shrink-0 truncate">{e.type}</span>
                {e.actor_id ? (
                  <button type="button" onClick={() => toggle(e.actor_id as string)} className={`shrink-0 hover:underline ${selected === e.actor_id ? "text-blue-600 dark:text-blue-400 font-semibold" : "text-slate-600 dark:text-slate-300"}`}>{e.actor_id}</button>
                ) : <span className="text-slate-400 dark:text-slate-600 shrink-0">—</span>}
                {e.cause_event_id && <span className="text-slate-400 dark:text-slate-500 truncate">← {e.cause_event_id}</span>}
              </li>
            ))}
          </ul>
        </section>
        {loading && sites.length === 0 && (
          <div data-testid="telco-loading" className="text-sm text-slate-500 dark:text-slate-400 py-6 text-center">Loading network…</div>
        )}
      </div>
    </div>
  );
}
function SiteCard({
  site, incident, neighbor, selected, onClick,
}: {
  site: WorldSite;
  incident: boolean;
  neighbor: boolean;
  selected: boolean;
  onClick: () => void;
}) {
  const failed = site.status === "failed";
  const util = pct(site.utilization);
  const ring = incident || failed
    ? "border-red-400 dark:border-red-700 bg-red-50 dark:bg-red-950/40"
    : neighbor
      ? "border-amber-300 dark:border-amber-800 bg-amber-50 dark:bg-amber-950/30"
      : "border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-900";
  return (
    <button
      type="button"
      data-testid={`site-${site.id}`}
      data-status={site.status}
      data-incident={incident ? "true" : "false"}
      onClick={onClick}
      className={`w-full text-left rounded border px-2 py-1.5 ${ring} ${selected ? "ring-2 ring-blue-400" : ""}`}
    >
      <div className="flex items-center justify-between">
        <span className="font-mono text-xs font-semibold text-slate-800 dark:text-slate-100">{site.id}</span>
        <span className={`text-[10px] font-semibold uppercase ${failed ? "text-red-600 dark:text-red-400" : "text-slate-400 dark:text-slate-500"}`}>{site.status}</span>
      </div>
      <div className="mt-1 h-1.5 rounded bg-slate-200 dark:bg-slate-800 overflow-hidden">
        <div data-testid={`site-util-${site.id}`} style={{ width: `${Math.min(100, util)}%` }}
          className={`h-full ${util > 90 ? "bg-red-500" : util > 70 ? "bg-amber-500" : "bg-emerald-500"}`} />
      </div>
      <div className="mt-1 flex justify-between text-[10px] tabular-nums text-slate-500 dark:text-slate-400">
        <span data-testid={`site-sessions-${site.id}`}>{site.session_count} sess</span>
        <span>{util}%</span>
        <span>{site.packet_loss_pct}% loss</span>
      </div>
    </button>
  );
}

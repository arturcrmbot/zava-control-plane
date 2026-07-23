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
  type TelcoScenarioName,
  type WorldState,
  type WorldSite,
  type WorldSession,
} from "@client/hooks/useWorldSimulation";
import { WorldInterventionStrip } from "@client/components/WorldInterventionStrip";
import { WorldObjectiveStrip } from "@client/components/WorldObjectiveStrip";
import { deriveCommonIntervention, type InterventionStep } from "@client/lib/worldIntervention";
import TelcoProcessLibrary from "@client/routes/TelcoProcessLibrary";

const REGIONS = ["north", "east", "south", "west"] as const;
const TOKEN_CAP = 24;
const JOURNAL_CAP = 30;
const SCENARIOS: Array<{ name: TelcoScenarioName; label: string }> = [
  { name: "storm-cascade", label: "Storm Cascade" },
  { name: "maintenance-save", label: "Maintenance Save" },
  { name: "capacity-revenue", label: "Capacity Revenue" },
  { name: "vulnerable-retention", label: "Vulnerable Retention" },
];

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
  state, events, loading, error, onFailSite, onRunScenario, onRunProcess,
}: {
  state: WorldState;
  events: WorldEvent[];
  loading: boolean;
  error: string | null;
  onFailSite: () => Promise<void>;
  onRunScenario: (name: TelcoScenarioName) => Promise<void>;
  onRunProcess: (workflowType: string) => Promise<void>;
}) {
  const [busy, setBusy] = useState(false);
  const [selected, setSelected] = useState<string | null>(null);
  const [lens, setLens] = useState<
    "Network" | "Process Library" | "Field Operations" | "Customer Impact" | "Orders" | "Control"
  >("Network");
  const toggle = (id: string | null) => setSelected((c) => (c === id ? null : id));
  const sites = state.sites ?? [];
  const sessions = state.sessions ?? [];
  const sessionCounts = state.session_counts ?? {};
  const sessionCount = Object.values(sessionCounts).reduce(
    (total, count) => total + (count ?? 0),
    0,
  ) || sessions.length;
  const subscriberCount = state.subscriber_count ?? state.subscribers?.length ?? 0;
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
  async function handleScenario(name: TelcoScenarioName) {
    setBusy(true);
    try { await onRunScenario(name); } finally { setBusy(false); }
  }
  const lanes: Array<{ id: WorldSession["status"]; title: string; list: WorldSession[]; count: number; tone: string }> = [
    { id: "degraded", title: "Degraded", list: degraded, count: sessionCounts.degraded ?? degraded.length, tone: "text-red-600 dark:text-red-400" },
    { id: "rerouted", title: "Rerouted", list: rerouted, count: sessionCounts.rerouted ?? rerouted.length, tone: "text-emerald-600 dark:text-emerald-400" },
    { id: "dropped", title: "Dropped", list: dropped, count: sessionCounts.dropped ?? dropped.length, tone: "text-slate-500" },
    { id: "active", title: "Active", list: active, count: sessionCounts.active ?? active.length, tone: "text-slate-600 dark:text-slate-300" },
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
                <span data-testid="stat-sessions">{sessionCount} sessions</span>
                <span data-testid="stat-subscribers">{subscriberCount} subscribers</span>
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
        <nav className="flex flex-wrap gap-2" aria-label="Telco lenses">
          {(["Network", "Process Library", "Field Operations", "Customer Impact", "Orders", "Control"] as const).map((item) => (
            <button
              key={item}
              type="button"
              onClick={() => setLens(item)}
              className={`rounded px-3 py-1.5 text-xs font-medium ${
                lens === item
                  ? "bg-blue-600 text-white"
                  : "bg-white text-slate-600 border border-slate-200 dark:bg-slate-900 dark:text-slate-300 dark:border-slate-700"
              }`}
            >
              {item}
            </button>
          ))}
        </nav>
        <section aria-label="Deterministic Telco scenarios" className="flex flex-wrap items-center gap-2">
          <span className="text-[11px] font-semibold uppercase tracking-wide text-slate-500">Stories</span>
          {SCENARIOS.map((scenario) => (
            <button
              key={scenario.name}
              type="button"
              disabled={busy}
              onClick={() => void handleScenario(scenario.name)}
              className="rounded border border-slate-300 bg-white px-2.5 py-1 text-xs text-slate-700 disabled:opacity-50 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-200"
            >
              {scenario.label}
            </button>
          ))}
        </section>
        {lens === "Network" && (
          <>
        <WorldObjectiveStrip testId="telco-objective" objectives={state?.objectives} />
        {intervention && (
          <WorldInterventionStrip
            testId="telco-intervention"
            trace={intervention.trace}
            steps={intervention.steps}
            onTrace={toggle}
          />
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
                <span data-testid={`session-count-${lane.id}`} className="text-[11px] tabular-nums text-slate-500 dark:text-slate-400">{lane.count}</span>
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
                {lane.count > Math.min(lane.list.length, TOKEN_CAP) && (
                  <span className="text-[10px] text-slate-400 dark:text-slate-600 px-1 py-0.5">+{lane.count - Math.min(lane.list.length, TOKEN_CAP)}</span>
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
          </>
        )}
        {lens === "Process Library" && (
          <TelcoProcessLibrary
            processes={state.process_library ?? []}
            cases={state.process_cases ?? []}
            onRun={onRunProcess}
          />
        )}
        {lens === "Field Operations" && <FieldOperationsLens state={state} />}
        {lens === "Customer Impact" && <CustomerImpactLens state={state} />}
        {lens === "Orders" && <OrderLens state={state} />}
        {lens === "Control" && <ControlLens state={state} events={events} />}
        {loading && sites.length === 0 && (
          <div data-testid="telco-loading" className="text-sm text-slate-500 dark:text-slate-400 py-6 text-center">Loading network…</div>
        )}
      </div>
    </div>
  );
}

function FieldOperationsLens({ state }: { state: WorldState }) {
  const assets = state.assets ?? [];
  const atRisk = assets.filter((asset) => (
    asset.risk_band !== "healthy" || asset.status !== "healthy"
  ));
  const visibleAssets = atRisk.length > 0 ? atRisk : assets.slice(0, 8);
  return (
    <section data-testid="field-operations-lens" className="grid gap-3 lg:grid-cols-2">
      <div className="rounded-lg border border-slate-200 bg-white p-3 dark:border-slate-800 dark:bg-slate-900">
        <h2 className="text-xs font-semibold uppercase tracking-wide text-slate-500">Assets at risk</h2>
        {visibleAssets.map((asset) => (
          <div key={asset.id} className="mt-2 border-t border-slate-100 pt-2 text-xs dark:border-slate-800">
            <div className="font-mono font-semibold">{asset.id}</div>
            <div className="text-slate-500">
              {asset.risk_band} · health {Math.round(asset.health * 100)}% · {asset.temperature_c}°C
            </div>
          </div>
        ))}
      </div>
      <div className="rounded-lg border border-slate-200 bg-white p-3 dark:border-slate-800 dark:bg-slate-900">
        <h2 className="text-xs font-semibold uppercase tracking-wide text-slate-500">Work orders</h2>
        {(state.work_orders ?? []).map((order) => (
          <div key={order.id} className="mt-2 border-t border-slate-100 pt-2 text-xs dark:border-slate-800">
            <div className="font-mono font-semibold">{order.id}</div>
            <div className="text-slate-500">{order.kind} · {order.asset_id} · {order.status}</div>
          </div>
        ))}
      </div>
      <div className="rounded-lg border border-slate-200 bg-white p-3 dark:border-slate-800 dark:bg-slate-900">
        <h2 className="text-xs font-semibold uppercase tracking-wide text-slate-500">Field technicians</h2>
        {(state.technicians ?? []).map((technician) => (
          <div key={technician.id} className="mt-2 flex justify-between border-t border-slate-100 pt-2 text-xs dark:border-slate-800">
            <span className="font-mono font-semibold">{technician.id}</span>
            <span className="text-slate-500">{technician.region} · {technician.status}</span>
          </div>
        ))}
      </div>
      <div className="rounded-lg border border-slate-200 bg-white p-3 dark:border-slate-800 dark:bg-slate-900">
        <h2 className="text-xs font-semibold uppercase tracking-wide text-slate-500">Spare stock</h2>
        {(state.spare_stocks ?? []).map((stock) => (
          <div key={stock.id} className="mt-2 flex justify-between border-t border-slate-100 pt-2 text-xs dark:border-slate-800">
            <span className="font-mono">{stock.id}</span>
            <span className={stock.quantity <= stock.reorder_point ? "font-semibold text-red-600" : "text-slate-500"}>
              {stock.quantity} available
            </span>
          </div>
        ))}
      </div>
    </section>
  );
}

function CustomerImpactLens({ state }: { state: WorldState }) {
  const impacted = new Set(state.customer_impact?.account_ids ?? []);
  const accounts = (state.accounts ?? []).filter((account) => impacted.has(account.id));
  const visibleAccounts = [...accounts]
    .sort((left, right) => {
      const score = (account: typeof left) => (
        Number(account.vulnerable) * 4
        + Number(account.notification_ids.length > 0) * 2
        + Number(account.credit_ids.length > 0)
      );
      return score(right) - score(left) || left.id.localeCompare(right.id);
    })
    .slice(0, 6);
  const impact = state.customer_impact;
  return (
    <section data-testid="customer-impact-lens" className="space-y-3">
      <div className="grid gap-3 sm:grid-cols-4">
        <ImpactMetric label="Affected" value={impact?.affected_account_count ?? accounts.length} />
        <ImpactMetric label="Notified" value={impact?.notified_account_count ?? 0} />
        <ImpactMetric label="Credited" value={impact?.credited_account_count ?? 0} />
        <div className="rounded-lg border border-slate-200 bg-white p-3 text-xs text-slate-500 dark:border-slate-800 dark:bg-slate-900">
          Showing {visibleAccounts.length} of {accounts.length} impacted accounts
        </div>
      </div>
      <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
        {visibleAccounts.map((account) => (
          <article key={account.id} data-testid="customer-account-card" className="rounded-lg border border-slate-200 bg-white p-3 dark:border-slate-800 dark:bg-slate-900">
            <div className="font-mono text-sm font-semibold">{account.id}</div>
            <div className="mt-1 text-xs text-slate-500">{account.segment} · {account.subscriber_id}</div>
            <div className="mt-2 text-xs">
              {account.notification_ids.length} notification · £{account.total_credits} credit
            </div>
          </article>
        ))}
      </div>
      <div className="grid gap-3 md:grid-cols-2">
        <div className="rounded-lg border border-slate-200 bg-white p-3 dark:border-slate-800 dark:bg-slate-900">
          <h2 className="text-xs font-semibold uppercase tracking-wide text-slate-500">Care tickets</h2>
          {(state.care_tickets ?? []).map((ticket) => (
            <div key={ticket.id} className="mt-2 border-t border-slate-100 pt-2 text-xs dark:border-slate-800">
              <div className="font-mono font-semibold">{ticket.id}</div>
              <div className="text-slate-500">{ticket.category} · {ticket.severity} · {ticket.status}</div>
            </div>
          ))}
        </div>
        <div className="rounded-lg border border-slate-200 bg-white p-3 dark:border-slate-800 dark:bg-slate-900">
          <h2 className="text-xs font-semibold uppercase tracking-wide text-slate-500">Retention offers</h2>
          {(state.retention_offers ?? []).map((offer) => (
            <div key={offer.id} className="mt-2 border-t border-slate-100 pt-2 text-xs dark:border-slate-800">
              <div className="font-mono font-semibold">{offer.id}</div>
              <div className="text-slate-500">{offer.offer_kind} · £{offer.value_gbp} · {offer.status}</div>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}

function ImpactMetric({ label, value }: { label: string; value: number }) {
  return (
    <div className="rounded-lg border border-slate-200 bg-white p-3 dark:border-slate-800 dark:bg-slate-900">
      <div className="text-[11px] font-semibold uppercase tracking-wide text-slate-500">{label}</div>
      <div className="mt-1 text-xl font-semibold tabular-nums">{value}</div>
    </div>
  );
}

function OrderLens({ state }: { state: WorldState }) {
  const [submitting, setSubmitting] = useState(false);
  const submitDemoOrder = async () => {
    const accountId = state.accounts?.[0]?.id ?? "ACC-00001";
    const siteId = state.sites?.find((site) => site.status === "healthy")?.id
      ?? "SITE-02";
    setSubmitting(true);
    try {
      await fetch("/api/world/service-orders", {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({
          account_id: accountId,
          product: "fiber-1gb",
          requested_site_id: siteId,
        }),
      });
    } finally {
      setSubmitting(false);
    }
  };
  return (
    <section data-testid="order-lens" className="space-y-3">
      <button
        type="button"
        disabled={submitting}
        onClick={submitDemoOrder}
        className="rounded bg-blue-600 px-3 py-1.5 text-xs font-medium text-white disabled:opacity-50"
      >
        {submitting ? "Submitting…" : "Submit demo order"}
      </button>
      <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
        {(state.orders ?? []).map((order) => (
          <article key={order.id} className="rounded-lg border border-slate-200 bg-white p-3 dark:border-slate-800 dark:bg-slate-900">
            <div className="font-mono text-sm font-semibold">{order.id}</div>
            <div className="mt-1 text-xs text-slate-500">{order.product} · {order.account_id}</div>
            <div className="mt-2 text-xs font-medium">{order.status} at {order.requested_site_id}</div>
          </article>
        ))}
      </div>
    </section>
  );
}

function ControlLens({ state, events }: { state: WorldState; events: WorldEvent[] }) {
  const evidence = events.filter((event) => (
    event.type.startsWith("objective.")
    || event.type.startsWith("evaluation.")
    || event.type === "site.recovered"
    || event.type === "care.completed"
  )).slice(-30).reverse();
  return (
    <section data-testid="control-lens" className="space-y-3">
      <WorldObjectiveStrip testId="telco-control-objectives" objectives={state.objectives} />
      <div className="rounded-lg border border-slate-200 bg-white p-3 dark:border-slate-800 dark:bg-slate-900">
        {evidence.map((event) => (
          <div key={event.event_id} className="flex gap-3 border-b border-slate-100 py-1 font-mono text-xs last:border-0 dark:border-slate-800">
            <span className="w-40">{event.type}</span>
            <span>{event.trace_id}</span>
          </div>
        ))}
      </div>
    </section>
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

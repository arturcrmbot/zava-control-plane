// web/client/routes/World.tsx
//
// The /world operational view: an actual-actor floor, not a KPI dashboard.
// Every card is a real ticket or worker from the /api/world snapshot; every
// pulse and the Durable intervention strip are driven by the causal journal.
// Backed entirely by useWorldSimulation — no chart lib, canvas or store.
import { useMemo, useState } from "react";
import { Globe2, Zap, AlertTriangle } from "lucide-react";
import {
  useWorldSimulation,
  type WorldEvent,
  type WorldTicket,
  type WorldWorker,
} from "@client/hooks/useWorldSimulation";
import { deriveCommonIntervention, type InterventionStep } from "@client/lib/worldIntervention";
import TelcoWorld from "@client/routes/TelcoWorld";

const WAITING_CAP = 40;
const IN_SERVICE_CAP = 40;
const TERMINAL_CAP = 20;
const JOURNAL_CAP = 30;

// Brief, journal-backed pulses. A card remounts (new React key) only when a
// newer event references its actor id, so the animation replays exactly once
// per genuine transition — never as decoration.
const PULSE_CSS = `
@keyframes worldPulse { 0% { box-shadow: 0 0 0 0 rgba(59,130,246,0.55); } 100% { box-shadow: 0 0 0 7px rgba(59,130,246,0); } }
@keyframes worldPulseGreen { 0% { box-shadow: 0 0 0 0 rgba(34,197,94,0.6); } 100% { box-shadow: 0 0 0 8px rgba(34,197,94,0); } }
.world-pulse { animation: worldPulse 0.9s ease-out; }
.world-pulse-green { animation: worldPulseGreen 1.3s ease-out; }
`;

const RESPONDER_TYPES = new Set([
  "responder.requested",
  "responder.decided",
  "responder.deferred",
  "responder.failed",
]);

function severityClasses(severity: string, breached: boolean): string {
  if (breached || severity === "high") {
    return "border-red-300 dark:border-red-800 bg-red-50 dark:bg-red-950/40";
  }
  if (severity === "medium") {
    return "border-amber-300 dark:border-amber-800 bg-amber-50 dark:bg-amber-950/30";
  }
  return "border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-900";
}

function round(n: number | undefined): number {
  return Math.round(n ?? 0);
}

export default function World() {
  const { state, events, loading, error, injectSurge, injectSiteFailure } = useWorldSimulation();
  const [selectedActor, setSelectedActor] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const toggleActor = (id: string | null) =>
    setSelectedActor((cur) => (cur === id ? null : id));

  const tickets = state?.tickets ?? [];
  const workers = state?.workers ?? [];

  // Latest seq that referenced each actor id — drives the one-shot pulse key.
  const recentRefs = useMemo(() => {
    const map = new Map<string, number>();
    for (const e of events) {
      if (e.actor_id) map.set(e.actor_id, e.seq);
      if (e.target_id) map.set(e.target_id, e.seq);
    }
    return map;
  }, [events]);

  // Worker ids named by worker.reallocated events pulse green.
  const reallocatedWorkers = useMemo(() => {
    const map = new Map<string, number>();
    for (const e of events) {
      if (e.type === "worker.reallocated" && e.actor_id) map.set(e.actor_id, e.seq);
    }
    return map;
  }, [events]);

  const waiting = useMemo(
    () => tickets.filter((t) => t.status === "queued").sort((a, b) => a.queued_at - b.queued_at),
    [tickets],
  );
  const inService = useMemo(
    () => tickets.filter((t) => t.status === "in_service").sort((a, b) => a.queued_at - b.queued_at),
    [tickets],
  );
  const resolved = useMemo(
    () =>
      tickets
        .filter((t) => t.status === "resolved")
        .sort((a, b) => (b.resolved_at ?? 0) - (a.resolved_at ?? 0)),
    [tickets],
  );
  const abandoned = useMemo(
    () =>
      tickets
        .filter((t) => t.status === "abandoned")
        .sort((a, b) => (b.abandoned_at ?? 0) - (a.abandoned_at ?? 0)),
    [tickets],
  );

  const supportWorkers = useMemo(
    () => workers.filter((w) => w.team_id === "TEAM-SUPPORT"),
    [workers],
  );
  const reserveWorkers = useMemo(
    () => workers.filter((w) => w.team_id === "TEAM-RESERVE"),
    [workers],
  );

  const intervention = useMemo(() => deriveIntervention(events), [events]);

  const journalEvents = useMemo(() => {
    const source = selectedActor
      ? events.filter(
        (e) =>
          e.actor_id === selectedActor ||
          e.target_id === selectedActor ||
          e.trace_id === selectedActor,
      )
      : events;
    return source.slice(-JOURNAL_CAP).reverse();
  }, [events, selectedActor]);

  const simTime = round(state?.sim_time);

  const lanes = [
    { testid: "lane-waiting", title: "Waiting", list: waiting, kind: "waiting" as const, cap: WAITING_CAP },
    { testid: "lane-in-service", title: "In service", list: inService, kind: "in_service" as const, cap: IN_SERVICE_CAP },
    { testid: "lane-resolved", title: "Resolved", list: resolved, kind: "resolved" as const, cap: TERMINAL_CAP },
    { testid: "lane-abandoned", title: "Abandoned", list: abandoned, kind: "abandoned" as const, cap: TERMINAL_CAP },
  ];

  async function handleSurge() {
    setBusy(true);
    try {
      await injectSurge();
    } finally {
      setBusy(false);
    }
  }

  const enabled = state?.enabled === true;

  // Scenario-aware surface: the telco pack renders a cell-site floor. All the
  // hooks above run unconditionally (support memos are cheap on empty lists),
  // so this branch respects the rules of hooks.
  if (state?.scenario === "telco") {
    return (
      <TelcoWorld
        state={state}
        events={events}
        loading={loading}
        error={error}
        onFailSite={injectSiteFailure}
      />
    );
  }

  return (
    <div
      data-testid="world-route"
      className="flex-1 min-w-0 overflow-y-auto bg-slate-50 dark:bg-slate-950 p-6"
    >
      <style>{PULSE_CSS}</style>
      <div className="max-w-[1400px] mx-auto space-y-4">
        <header className="flex flex-wrap items-center justify-between gap-3">
          <div className="flex items-center gap-3">
            <Globe2 size={20} className="text-blue-600 dark:text-blue-400" />
            <div>
              <h1 className="text-xl font-semibold text-slate-900 dark:text-slate-100">World</h1>
              <div className="text-xs text-slate-500 dark:text-slate-400 flex flex-wrap gap-x-3 tabular-nums">
                <span>t = {simTime}m</span>
                <span>seed {state?.seed ?? "—"}</span>
                <span>status {state?.status ?? "—"}</span>
                <span>{tickets.length} tickets</span>
                <span>{workers.length} workers</span>
                <span>{state?.customers?.length ?? 0} customers</span>
              </div>
            </div>
          </div>
          <button
            type="button"
            data-testid="inject-surge"
            disabled={!enabled || busy}
            onClick={handleSurge}
            className="text-xs px-3 py-1.5 rounded font-medium bg-blue-600 text-white hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed flex items-center gap-1.5"
          ><Zap size={14} /> {busy ? "Injecting…" : "Inject demand surge"}</button>
        </header>

        {error && (
          <div
            data-testid="world-error"
            className="flex items-center gap-2 text-xs px-3 py-2 rounded border border-red-300 dark:border-red-800 bg-red-50 dark:bg-red-950/40 text-red-700 dark:text-red-300"
          >
            <AlertTriangle size={14} /> {error}
          </div>
        )}

        {!state ? (
          <div data-testid="world-loading" className="text-sm text-slate-500 dark:text-slate-400 py-10 text-center">
            {loading ? "Loading world…" : "No world snapshot available."}
          </div>
        ) : !state.enabled ? (
          <div data-testid="world-disabled" className="text-sm text-slate-500 dark:text-slate-400 py-10 text-center">
            World simulator is disabled. Start the API with <code className="font-mono">ZAVA_WORLD=support</code>.
          </div>
        ) : (
          <>
            {intervention && (
              <InterventionStrip intervention={intervention} onActor={toggleActor} />
            )}

            <section className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-4 gap-3">
              {lanes.map((lane) => (
                <Lane key={lane.testid} testid={lane.testid} title={lane.title} total={lane.list.length}>
                  {lane.list.slice(0, lane.cap).map((t) => (
                    <TicketCard
                      key={`${t.id}:${recentRefs.get(t.id) ?? 0}`}
                      ticket={t}
                      kind={lane.kind}
                      simTime={simTime}
                      pulse={recentRefs.has(t.id)}
                      selected={selectedActor === t.id}
                      onClick={() => toggleActor(t.id)}
                    />
                  ))}
                </Lane>
              ))}
            </section>

            <section className="grid grid-cols-1 lg:grid-cols-2 gap-3">
              <WorkerGroup
                testid="workers-support"
                title="Support"
                workers={supportWorkers}
                reallocated={reallocatedWorkers}
                selectedActor={selectedActor}
                onActor={toggleActor}
              />
              <WorkerGroup
                testid="workers-reserve"
                title="Reserve"
                workers={reserveWorkers}
                reallocated={reallocatedWorkers}
                selectedActor={selectedActor}
                onActor={toggleActor}
              />
            </section>

            <Journal
              events={journalEvents}
              selectedActor={selectedActor}
              onActor={toggleActor}
              onClear={() => setSelectedActor(null)}
            />
          </>
        )}
      </div>
    </div>
  );
}

// -- ticket floor ------------------------------------------------------------

function Lane({
  testid, title, total, children,
}: {
  testid: string;
  title: string;
  total: number;
  children: React.ReactNode;
}) {
  const count = Array.isArray(children) ? children.length : children ? 1 : 0;
  return (
    <div
      data-testid={testid}
      className="rounded-lg border border-slate-200 dark:border-slate-800 bg-slate-100/60 dark:bg-slate-900/40 p-2 min-h-[120px]"
    >
      <div className="flex items-baseline justify-between px-1 pb-2">
        <h2 className="text-[11px] font-semibold uppercase tracking-wide text-slate-500 dark:text-slate-400">{title}</h2>
        <span className="text-[11px] tabular-nums text-slate-500 dark:text-slate-400">
          {count < total ? `${count} / ${total}` : total}
        </span>
      </div>
      <div className="space-y-1.5">
        {total === 0 ? (
          <div className="text-[11px] text-slate-400 dark:text-slate-600 px-1 py-2">none</div>
        ) : children}
      </div>
    </div>
  );
}

function TicketCard({
  ticket, kind, simTime, pulse, selected, onClick,
}: {
  ticket: WorldTicket;
  kind: "waiting" | "in_service" | "resolved" | "abandoned";
  simTime: number;
  pulse: boolean;
  selected: boolean;
  onClick: () => void;
}) {
  const wait = Math.max(0, simTime - ticket.queued_at);
  return (
    <button
      type="button"
      data-testid={`ticket-${ticket.id}`}
      onClick={onClick}
      className={`block w-full text-left rounded border px-2 py-1.5 text-xs transition ${severityClasses(
        ticket.severity, ticket.sla_breached,
      )} ${selected ? "ring-2 ring-blue-500" : ""} ${pulse ? "world-pulse" : ""}`}
    >
      <div className="flex items-center justify-between gap-2">
        <span className="font-mono font-semibold text-slate-800 dark:text-slate-100">{ticket.id}</span>
        <span
          className={`text-[10px] uppercase tracking-wide ${
            ticket.severity === "high" ? "text-red-600 dark:text-red-400"
              : ticket.severity === "medium" ? "text-amber-600 dark:text-amber-400"
                : "text-slate-500 dark:text-slate-400"
          }`}
        >{ticket.severity}</span>
      </div>
      <div className="mt-0.5 text-[11px] text-slate-500 dark:text-slate-400 flex flex-wrap gap-x-2">
        <span>{ticket.customer_id}</span>
        <span>{ticket.required_skill}</span>
      </div>
      {kind === "waiting" && (
        <div className="mt-0.5 text-[11px] tabular-nums flex items-center gap-1.5">
          <span className="text-slate-500 dark:text-slate-400">wait {round(wait)}m</span>
          {ticket.sla_breached && (
            <span className="text-red-600 dark:text-red-400 font-medium">SLA breached</span>
          )}
        </div>
      )}
      {kind === "in_service" && ticket.assigned_worker_id && (
        <div className="mt-0.5 text-[11px] text-slate-600 dark:text-slate-300">
          → <span className="font-mono">{ticket.assigned_worker_id}</span>
        </div>
      )}
    </button>
  );
}

// -- worker floor ------------------------------------------------------------

function WorkerGroup({
  testid, title, workers, reallocated, selectedActor, onActor,
}: {
  testid: string;
  title: string;
  workers: WorldWorker[];
  reallocated: Map<string, number>;
  selectedActor: string | null;
  onActor: (id: string) => void;
}) {
  return (
    <div
      data-testid={testid}
      className="rounded-lg border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 p-3"
    >
      <div className="flex items-baseline justify-between pb-2">
        <h2 className="text-[11px] font-semibold uppercase tracking-wide text-slate-500 dark:text-slate-400">
          {title} workers
        </h2>
        <span className="text-[11px] tabular-nums text-slate-500 dark:text-slate-400">{workers.length}</span>
      </div>
      <div className="flex flex-wrap gap-1.5">
        {workers.length === 0 ? (
          <div className="text-[11px] text-slate-400 dark:text-slate-600 py-1">none</div>
        ) : workers.map((w) => (
          <WorkerChip
            key={`${w.id}:${reallocated.get(w.id) ?? 0}`}
            worker={w}
            justMoved={reallocated.has(w.id)}
            selected={selectedActor === w.id}
            onClick={() => onActor(w.id)}
          />
        ))}
      </div>
    </div>
  );
}

function WorkerChip({
  worker, justMoved, selected, onClick,
}: {
  worker: WorldWorker;
  justMoved: boolean;
  selected: boolean;
  onClick: () => void;
}) {
  const busy = worker.status === "busy";
  return (
    <button
      type="button"
      data-testid={`worker-${worker.id}`}
      onClick={onClick}
      title={`${worker.id} · ${worker.status}`}
      className={`rounded border px-2 py-1 text-[11px] text-left transition ${
        busy
          ? "border-blue-300 dark:border-blue-800 bg-blue-50 dark:bg-blue-950/40"
          : "border-slate-200 dark:border-slate-700 bg-slate-50 dark:bg-slate-800/60"
      } ${selected ? "ring-2 ring-blue-500" : ""} ${justMoved ? "world-pulse-green" : ""}`}
    >
      <span className="font-mono font-medium text-slate-800 dark:text-slate-100">{worker.id}</span>
      <span className="ml-1.5 text-slate-500 dark:text-slate-400">{worker.status}</span>
      {busy && worker.current_ticket_id && (
        <span className="ml-1 font-mono text-blue-700 dark:text-blue-300">{worker.current_ticket_id}</span>
      )}
    </button>
  );
}

// -- Durable intervention ----------------------------------------------------

interface Intervention {
  trace: string;
  steps: InterventionStep[];
  reallocatedWorkerIds: string[];
}

function deriveIntervention(events: WorldEvent[]): Intervention | null {
  const common = deriveCommonIntervention(events, (e) => RESPONDER_TYPES.has(e.type));
  if (!common) return null;
  const { trace, traceEvents, steps } = common;

  // Scenario-specific tail: which workers a worker.reallocated command moved.
  const reallocations = traceEvents.filter((e) => e.type === "worker.reallocated");
  const reallocatedWorkerIds = reallocations.map((e) => e.actor_id).filter((id): id is string => Boolean(id));
  if (reallocatedWorkerIds.length > 0) {
    steps.push({
      label: `${reallocatedWorkerIds.join(", ")} reallocated`,
      eventId: reallocations[reallocations.length - 1].event_id,
    });
  }

  return { trace, steps, reallocatedWorkerIds };
}

function InterventionStrip({
  intervention, onActor,
}: {
  intervention: Intervention;
  onActor: (id: string) => void;
}) {
  return (
    <section
      data-testid="intervention"
      className="rounded-lg border border-emerald-300 dark:border-emerald-800 bg-emerald-50 dark:bg-emerald-950/30 p-3"
    >
      <div className="flex items-center justify-between pb-2">
        <h2 className="text-[11px] font-semibold uppercase tracking-wide text-emerald-700 dark:text-emerald-400">
          Durable intervention
        </h2>
        <button
          type="button"
          onClick={() => onActor(intervention.trace)}
          className="text-[11px] font-mono text-emerald-700 dark:text-emerald-400 hover:underline"
        >{intervention.trace}</button>
      </div>
      <ol className="flex flex-wrap items-center gap-x-1.5 gap-y-1 text-xs text-slate-700 dark:text-slate-200">
        {intervention.steps.map((step, i) => (
          <li key={step.eventId} className="flex items-center gap-1.5">
            {i > 0 && <span className="text-emerald-500">→</span>}
            <span className="font-medium">{step.label}</span>
            {step.detail && (
              <span className="font-mono text-[10px] text-slate-500 dark:text-slate-400">{step.detail}</span>
            )}
          </li>
        ))}
      </ol>
    </section>
  );
}

// -- recent event journal ----------------------------------------------------

function Journal({
  events, selectedActor, onActor, onClear,
}: {
  events: WorldEvent[];
  selectedActor: string | null;
  onActor: (id: string) => void;
  onClear: () => void;
}) {
  return (
    <section
      data-testid="event-journal"
      className="rounded-lg border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 p-3"
    >
      <div className="flex items-center justify-between pb-2">
        <h2 className="text-[11px] font-semibold uppercase tracking-wide text-slate-500 dark:text-slate-400">
          Recent events
        </h2>
        {selectedActor && (
          <button
            type="button"
            onClick={onClear}
            className="text-[11px] text-blue-600 dark:text-blue-400 hover:underline"
          >filtering {selectedActor} · clear</button>
        )}
      </div>
      <ul className="divide-y divide-slate-100 dark:divide-slate-800 font-mono text-[11px]">
        {events.length === 0 ? (
          <li className="py-2 text-slate-400 dark:text-slate-600">no events</li>
        ) : events.map((e) => (
          <li
            key={e.seq}
            data-testid={`event-${e.seq}`}
            className="py-1 flex items-center gap-2"
          >
            <span className="tabular-nums text-slate-400 dark:text-slate-500 w-12 shrink-0">{round(e.sim_time)}m</span>
            <span className="text-slate-700 dark:text-slate-200 w-44 shrink-0 truncate">{e.type}</span>
            {e.actor_id ? (
              <button
                type="button"
                onClick={() => onActor(e.actor_id as string)}
                className={`shrink-0 hover:underline ${
                  selectedActor === e.actor_id ? "text-blue-600 dark:text-blue-400 font-semibold" : "text-slate-600 dark:text-slate-300"
                }`}
              >{e.actor_id}</button>
            ) : (
              <span className="text-slate-400 dark:text-slate-600 shrink-0">—</span>
            )}
            {e.cause_event_id && (
              <span className="text-slate-400 dark:text-slate-500 truncate">← {e.cause_event_id}</span>
            )}
          </li>
        ))}
      </ul>
    </section>
  );
}

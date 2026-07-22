import { useMemo, useState } from "react";
import { AlertTriangle, Boxes, Play } from "lucide-react";
import {
  type WorldEvent,
  type WorldState,
} from "@client/hooks/useWorldSimulation";
import { WorldObjectiveStrip } from "@client/components/WorldObjectiveStrip";

const FASHION_WORKFLOWS = [
  "inventory-rebalancing",
  "demand-spike-response",
  "promotion-readiness",
  "markdown-governance",
  "supplier-delay-recovery",
  "fulfilment-exception-resolution",
  "marketplace-seller-exception",
  "returns-disposition",
] as const;

function count(value: unknown[] | undefined): number {
  return value?.length ?? 0;
}

export default function FashionWorld({
  state,
  events,
  error,
  onRunProcess,
}: {
  state: WorldState;
  events: WorldEvent[];
  error: string | null;
  onRunProcess: (workflowType: string) => Promise<void>;
}) {
  const [busy, setBusy] = useState(false);
  const cases = state.process_cases ?? [];
  const recentEvents = useMemo(() => events.slice(-30).reverse(), [events]);
  const openCases = cases.filter((item) => item.status === "open").length;
  const completedCases = cases.filter((item) => item.status === "completed").length;

  async function runPortfolio() {
    setBusy(true);
    try {
      for (const workflowType of FASHION_WORKFLOWS) {
        await onRunProcess(workflowType);
      }
    } finally {
      setBusy(false);
    }
  }

  return (
    <div
      data-testid="fashion-world-route"
      className="flex-1 min-w-0 overflow-y-auto bg-slate-50 p-6 dark:bg-slate-950"
    >
      <div className="mx-auto max-w-[1400px] space-y-4">
        <header className="flex flex-wrap items-center justify-between gap-3">
          <div className="flex items-center gap-3">
            <Boxes size={20} className="text-pink-600 dark:text-pink-400" />
            <div>
              <h1 className="text-xl font-semibold text-slate-900 dark:text-slate-100">
                Fashion Retail World
              </h1>
              <div className="flex flex-wrap gap-x-3 text-xs tabular-nums text-slate-500 dark:text-slate-400">
                <span>t = {Math.round(state.sim_time ?? 0)}m</span>
                <span>seed {state.seed ?? "—"}</span>
                <span>status {state.status ?? "—"}</span>
                <span>{count(state.stores)} stores</span>
                <span>{count(state.distribution_centres)} distribution centres</span>
                <span>{count(state.skus)} SKUs</span>
                <span>{count(state.inventory)} inventory positions</span>
              </div>
            </div>
          </div>
          <button
            type="button"
            disabled={!state.enabled || busy}
            onClick={() => void runPortfolio()}
            className="flex items-center gap-1.5 rounded bg-pink-600 px-3 py-1.5 text-xs font-medium text-white hover:bg-pink-700 disabled:cursor-not-allowed disabled:opacity-50"
          >
            <Play size={14} />
            {busy ? "Starting…" : "Run 8 Fashion processes"}
          </button>
        </header>

        {error && (
          <div className="flex items-center gap-2 rounded border border-red-300 bg-red-50 px-3 py-2 text-xs text-red-700 dark:border-red-800 dark:bg-red-950/40 dark:text-red-300">
            <AlertTriangle size={14} /> {error}
          </div>
        )}

        <WorldObjectiveStrip testId="objective" objectives={state.objectives} />

        <section className="grid grid-cols-2 gap-3 md:grid-cols-4 xl:grid-cols-8">
          {[
            ["Stores", count(state.stores)],
            ["Distribution centres", count(state.distribution_centres)],
            ["Brands", count(state.brands)],
            ["Styles", count(state.styles)],
            ["SKUs", count(state.skus)],
            ["Customers", count(state.customers)],
            ["Inventory positions", count(state.inventory)],
            ["Open processes", openCases],
          ].map(([label, value]) => (
            <div
              key={label}
              className="rounded-lg border border-slate-200 bg-white p-3 dark:border-slate-800 dark:bg-slate-900"
            >
              <div className="text-[10px] font-semibold uppercase tracking-wide text-slate-500 dark:text-slate-400">
                {label}
              </div>
              <div className="mt-1 text-2xl font-semibold tabular-nums text-slate-900 dark:text-slate-100">
                {value}
              </div>
            </div>
          ))}
        </section>

        <section className="rounded-lg border border-slate-200 bg-white dark:border-slate-800 dark:bg-slate-900">
          <header className="flex items-center justify-between border-b border-slate-200 px-4 py-3 dark:border-slate-800">
            <h2 className="text-sm font-semibold text-slate-900 dark:text-slate-100">
              Fashion processes
            </h2>
            <span className="text-xs tabular-nums text-slate-500 dark:text-slate-400">
              {openCases} open · {completedCases} completed
            </span>
          </header>
          <div className="grid gap-2 p-3 md:grid-cols-2 xl:grid-cols-4">
            {cases.length === 0 ? (
              <div className="col-span-full py-6 text-center text-xs text-slate-400">
                No process cases yet. Run the Fashion portfolio to start all eight.
              </div>
            ) : cases.map((item) => (
              <article
                key={item.id}
                className="rounded border border-slate-200 p-3 dark:border-slate-700"
              >
                <div className="flex items-start justify-between gap-2">
                  <div className="text-xs font-semibold text-slate-800 dark:text-slate-100">
                    {item.workflow_type}
                  </div>
                  <span className={`rounded px-1.5 py-0.5 text-[10px] font-semibold uppercase ${
                    item.status === "open"
                      ? "bg-amber-100 text-amber-700 dark:bg-amber-950/60 dark:text-amber-300"
                      : "bg-emerald-100 text-emerald-700 dark:bg-emerald-950/60 dark:text-emerald-300"
                  }`}>
                    {item.status}
                  </span>
                </div>
                <div className="mt-2 font-mono text-[10px] text-slate-500 dark:text-slate-400">
                  {item.id}
                </div>
                <div className="mt-1 text-[11px] text-slate-600 dark:text-slate-300">
                  {item.recommended_action ?? "Awaiting recommendation"}
                </div>
              </article>
            ))}
          </div>
        </section>

        <section className="rounded-lg border border-slate-200 bg-white p-3 dark:border-slate-800 dark:bg-slate-900">
          <h2 className="pb-2 text-[11px] font-semibold uppercase tracking-wide text-slate-500 dark:text-slate-400">
            Recent Fashion world events
          </h2>
          <ul className="divide-y divide-slate-100 font-mono text-[11px] dark:divide-slate-800">
            {recentEvents.length === 0 ? (
              <li className="py-2 text-slate-400">No world events yet.</li>
            ) : recentEvents.map((event) => (
              <li key={event.seq} className="flex items-center gap-2 py-1">
                <span className="w-12 shrink-0 tabular-nums text-slate-400">
                  {Math.round(event.sim_time)}m
                </span>
                <span className="w-52 shrink-0 truncate text-slate-700 dark:text-slate-200">
                  {event.type}
                </span>
                <span className="truncate text-slate-500 dark:text-slate-400">
                  {event.actor_id ?? event.target_id ?? "—"}
                </span>
              </li>
            ))}
          </ul>
        </section>
      </div>
    </div>
  );
}

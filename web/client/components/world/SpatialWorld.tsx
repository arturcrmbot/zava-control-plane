import { useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { Boxes, Network, RotateCcw, Sparkles, Store } from "lucide-react";

import type {
  WorldEvent,
  WorldState,
} from "@client/hooks/useWorldSimulation";


export interface SceneLocation {
  id: string;
  label: string;
  kind: string;
  country?: string;
  x: number;
  y: number;
  width: number;
  height: number;
}

export interface SceneLayer {
  state_key: string;
  kind: string;
  label: string;
  id_field: string;
  location_field: string;
  status_field: string;
  colour: string;
}

export interface SceneEventMapping {
  event_type: string;
  layer: string;
  animation: "move" | "pulse" | "appear" | "status" | string;
}

export interface WorldSceneContract {
  enabled: true;
  schema_version: 1;
  title: string;
  subtitle?: string;
  locations: SceneLocation[];
  layers: SceneLayer[];
  event_mappings: SceneEventMapping[];
  process_event_types?: string[];
  knowledge_relationship_label?: string;
  knowledge_actor_ids?: string[];
}

interface SpatialWorldProps {
  scene: WorldSceneContract;
  state: WorldState;
  events: WorldEvent[];
  error: string | null;
  onReset: () => Promise<void>;
}

type ActorRecord = Record<string, unknown>;
type KnowledgeRelationship = {
  workflow_id?: string;
  source_id?: string;
  relationship?: string;
  destination_id?: string;
};

const ACTORS_PER_LOCATION_PER_LAYER = 18;
const JOURNAL_LIMIT = 40;
const PROCESS_LIMIT = 8;

const ANIMATION_CSS = `
@keyframes scenePulse {
  0% { transform: scale(1); box-shadow: 0 0 0 0 rgba(244,63,94,.65); }
  55% { transform: scale(1.08); box-shadow: 0 0 0 9px rgba(244,63,94,0); }
  100% { transform: scale(1); }
}
.scene-event-pulse { animation: scenePulse 1.1s ease-out; }
`;


function text(value: unknown): string {
  return value == null ? "" : String(value);
}


function actorRecords(state: WorldState, layer: SceneLayer): ActorRecord[] {
  const records = state[layer.state_key];
  return Array.isArray(records)
    ? records.filter((record): record is ActorRecord => (
      typeof record === "object" && record !== null
    ))
    : [];
}


function stableOffset(id: string, modulus: number): number {
  let value = 0;
  for (let index = 0; index < id.length; index += 1) {
    value = ((value * 31) + id.charCodeAt(index)) >>> 0;
  }
  return value % modulus;
}


function recentEventByActor(events: WorldEvent[]): Map<string, WorldEvent> {
  const result = new Map<string, WorldEvent>();
  for (const event of events) {
    if (event.actor_id) result.set(event.actor_id, event);
    if (event.target_id) result.set(event.target_id, event);
  }
  return result;
}


function processEvents(
  events: WorldEvent[],
  configuredTypes: string[],
): Array<{ workflowId: string; workflowType: string; event: WorldEvent; sensor?: WorldEvent }> {
  const accepted = new Set(configuredTypes);
  const byWorkflow = new Map<string, WorldEvent>();
  for (const event of events) {
    if (accepted.size > 0 && !accepted.has(event.type)) continue;
    const workflowId = text(event.payload.workflow_id);
    if (workflowId) byWorkflow.set(workflowId, event);
  }
  return Array.from(byWorkflow.entries())
    .map(([workflowId, event]) => ({
      workflowId,
      workflowType: text(event.payload.workflow_type) || "workflow",
      event,
      sensor: events.find((candidate) => (
        candidate.trace_id === event.trace_id
        && candidate.type === "sensor.tripped"
      )),
    }))
    .slice(-PROCESS_LIMIT)
    .reverse();
}


function triggerSummary(sensor?: WorldEvent): string {
  if (!sensor) return "Trigger evidence is being correlated.";
  const measurements = sensor.payload.measurements;
  const values = typeof measurements === "object" && measurements !== null
    ? Object.entries(measurements as Record<string, unknown>)
      .slice(0, 4)
      .map(([key, value]) => `${key} ${text(value)}`)
      .join(" · ")
    : "";
  return `${sensor.actor_id ?? "sensor"} · ${values}`.trim();
}


export default function SpatialWorld({
  scene,
  state,
  events,
  error,
  onReset,
}: SpatialWorldProps) {
  const [selectedActor, setSelectedActor] = useState<string | null>(null);
  const [resetting, setResetting] = useState(false);
  const latestByActor = useMemo(() => recentEventByActor(events), [events]);
  const processes = useMemo(
    () => processEvents(events, scene.process_event_types ?? []),
    [events, scene.process_event_types],
  );
  const relationships = (
    Array.isArray(state.knowledge_relationships)
      ? state.knowledge_relationships
      : []
  ).filter((item): item is KnowledgeRelationship => (
    typeof item === "object" && item !== null
  ));
  const journal = useMemo(() => {
    const matching = selectedActor
      ? events.filter((event) => (
        event.actor_id === selectedActor
        || event.target_id === selectedActor
        || event.trace_id === selectedActor
      ))
      : events;
    return matching.slice(-JOURNAL_LIMIT).reverse();
  }, [events, selectedActor]);

  async function reset() {
    setResetting(true);
    try {
      await onReset();
      setSelectedActor(null);
    } finally {
      setResetting(false);
    }
  }

  return (
    <div
      data-testid="spatial-world-route"
      className="flex-1 min-w-0 overflow-y-auto bg-stone-100 dark:bg-slate-950 p-4 lg:p-6"
    >
      <style>{ANIMATION_CSS}</style>
      <div className="mx-auto max-w-[1600px] space-y-4">
        <header className="flex flex-wrap items-start justify-between gap-3">
          <div className="flex items-start gap-3">
            <Store className="mt-1 text-rose-700 dark:text-rose-300" size={22} />
            <div>
              <h1 className="text-xl font-semibold text-slate-950 dark:text-white">
                {scene.title}
              </h1>
              {scene.subtitle && (
                <p className="text-sm text-slate-600 dark:text-slate-300">
                  {scene.subtitle}
                </p>
              )}
              <div className="mt-1 flex flex-wrap gap-x-3 text-xs tabular-nums text-slate-500 dark:text-slate-400">
                <span>simulation {Math.round(Number(state.sim_time ?? 0))}m</span>
                <span>seed {text(state.seed) || "—"}</span>
                <span>{text(state.status) || "unknown"}</span>
                <span>{Number(state.ordinary_activity_count ?? 0)} ordinary orders</span>
              </div>
            </div>
          </div>
          <button
            type="button"
            onClick={() => void reset()}
            disabled={resetting}
            className="inline-flex items-center gap-1.5 rounded border border-slate-300 bg-white px-3 py-1.5 text-xs font-medium text-slate-700 hover:bg-slate-50 disabled:opacity-50 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-200"
          >
            <RotateCcw size={13} />
            {resetting ? "Resetting…" : `Reset seed ${text(state.seed) || "42"}`}
          </button>
        </header>

        {error && (
          <div role="alert" className="rounded border border-rose-300 bg-rose-50 px-3 py-2 text-xs text-rose-800">
            {error}
          </div>
        )}

        <section className="grid gap-4 xl:grid-cols-[minmax(0,1fr)_360px]">
          <div
            data-testid="spatial-map"
            className="relative min-h-[680px] overflow-hidden rounded-xl border border-stone-300 bg-[radial-gradient(circle_at_top,_#fff7ed,_#f5f5f4_55%,_#e7e5e4)] shadow-sm dark:border-slate-700 dark:bg-[radial-gradient(circle_at_top,_#172033,_#0f172a_60%,_#020617)]"
          >
            <div className="absolute left-3 top-3 z-20 flex flex-wrap gap-2 rounded bg-white/90 px-2 py-1.5 text-[10px] shadow-sm backdrop-blur dark:bg-slate-900/90">
              {scene.layers.map((layer) => (
                <span key={layer.state_key} className="inline-flex items-center gap-1">
                  <span className="h-2 w-2 rounded-full" style={{ backgroundColor: layer.colour }} />
                  {layer.label}
                </span>
              ))}
            </div>

            {scene.locations.map((location) => (
              <div
                key={location.id}
                data-testid={`location-${location.id}`}
                className="absolute rounded-lg border border-stone-300 bg-white/75 p-2 shadow-sm backdrop-blur-sm dark:border-slate-700 dark:bg-slate-900/75"
                style={{
                  left: `${location.x}%`,
                  top: `${location.y}%`,
                  width: `${location.width}%`,
                  height: `${location.height}%`,
                }}
              >
                <div className="pointer-events-none flex items-start justify-between gap-2">
                  <div>
                    <div className="text-[11px] font-semibold text-slate-800 dark:text-slate-100">
                      {location.label}
                    </div>
                    <div className="font-mono text-[9px] text-slate-500">
                      {location.id}
                    </div>
                  </div>
                  <span className="text-[9px] uppercase tracking-wide text-slate-400">
                    {location.kind}
                  </span>
                </div>
              </div>
            ))}

            {scene.layers.flatMap((layer) => (
              scene.locations.flatMap((location) => (
                actorRecords(state, layer)
                  .filter((actor) => text(actor[layer.location_field]) === location.id)
                  .slice(0, ACTORS_PER_LOCATION_PER_LAYER)
                  .map((actor, index) => {
                    const actorId = text(actor[layer.id_field]);
                    const status = text(actor[layer.status_field]);
                    const recent = latestByActor.get(actorId);
                    const columns = 6;
                    const slot = stableOffset(actorId, 17) + index;
                    const left = location.x + 1.2 + ((slot % columns) * Math.max(2.5, (location.width - 4) / columns));
                    const top = location.y + 8 + ((Math.floor(slot / columns) % 5) * 4.4);
                    return (
                      <button
                        key={`${layer.state_key}:${actorId}`}
                        type="button"
                        data-testid={`actor-${actorId}`}
                        data-event-id={recent?.event_id}
                        title={`${layer.kind} ${actorId} · ${status}`}
                        onClick={() => setSelectedActor((current) => current === actorId ? null : actorId)}
                        className={
                          "absolute z-10 max-w-[180px] truncate rounded-full border bg-white px-1.5 py-0.5 font-mono text-[8px] shadow-sm transition-all duration-700 dark:bg-slate-950 " +
                          (selectedActor === actorId ? "ring-2 ring-slate-900 dark:ring-white " : "") +
                          (recent ? "scene-event-pulse" : "")
                        }
                        style={{
                          left: `${left}%`,
                          top: `${top}%`,
                          borderColor: layer.colour,
                          color: layer.colour,
                        }}
                      >
                        <span>{actorId}</span>
                        {status && <span className="ml-1 opacity-75">· {status}</span>}
                      </button>
                    );
                  })
              ))
            ))}
          </div>

          <aside className="space-y-3">
            <ThresholdCard state={state} />
            <ProcessCards processes={processes} />
            <KnowledgeOutcome
              relationships={relationships}
              label={scene.knowledge_relationship_label}
              expectedActorIds={scene.knowledge_actor_ids ?? []}
            />
          </aside>
        </section>

        <section className="rounded-lg border border-slate-200 bg-white p-3 dark:border-slate-800 dark:bg-slate-900">
          <div className="mb-2 flex items-center justify-between">
            <h2 className="flex items-center gap-1.5 text-xs font-semibold uppercase tracking-wide text-slate-500">
              <Sparkles size={13} /> Causal journal
            </h2>
            {selectedActor && (
              <button
                type="button"
                onClick={() => setSelectedActor(null)}
                className="text-xs text-blue-600 hover:underline dark:text-blue-400"
              >
                filtering {selectedActor} · clear
              </button>
            )}
          </div>
          <ul className="divide-y divide-slate-100 text-[11px] dark:divide-slate-800">
            {journal.length === 0 ? (
              <li className="py-2 text-slate-400">No matching journal events.</li>
            ) : journal.map((event) => (
              <li key={event.seq} className="grid grid-cols-[80px_180px_1fr] gap-2 py-1 font-mono">
                <span className="text-slate-400">{event.event_id}</span>
                <span className="text-slate-700 dark:text-slate-200">{event.type}</span>
                <span className="truncate text-slate-500">
                  {event.actor_id ?? "—"} → {event.target_id ?? "—"}
                </span>
              </li>
            ))}
          </ul>
        </section>
      </div>
    </div>
  );
}


function ThresholdCard({ state }: { state: WorldState }) {
  const threshold = (
    typeof state.threshold_state === "object" && state.threshold_state !== null
      ? state.threshold_state as Record<string, unknown>
      : {}
  );
  const measurements = (
    typeof threshold.measurements === "object" && threshold.measurements !== null
      ? threshold.measurements as Record<string, unknown>
      : {}
  );
  return (
    <section className="rounded-lg border border-amber-200 bg-amber-50 p-3 dark:border-amber-900 dark:bg-amber-950/30">
      <h2 className="flex items-center gap-1.5 text-xs font-semibold uppercase tracking-wide text-amber-800 dark:text-amber-300">
        <Boxes size={13} /> State-derived trigger
      </h2>
      <div className="mt-1 font-mono text-[10px] text-amber-900 dark:text-amber-200">
        {text(threshold.sensor_id) || "No sensor"} · {threshold.active ? "threshold crossed" : "watching live state"}
      </div>
      <div className="mt-2 flex flex-wrap gap-1">
        {Object.entries(measurements).slice(0, 6).map(([key, value]) => (
          <span key={key} className="rounded bg-white/80 px-1.5 py-0.5 text-[9px] text-slate-600 dark:bg-slate-900/70 dark:text-slate-300">
            {key} {text(value)}
          </span>
        ))}
      </div>
    </section>
  );
}


function ProcessCards({
  processes,
}: {
  processes: ReturnType<typeof processEvents>;
}) {
  return (
    <section className="rounded-lg border border-slate-200 bg-white p-3 dark:border-slate-800 dark:bg-slate-900">
      <h2 className="flex items-center gap-1.5 text-xs font-semibold uppercase tracking-wide text-slate-500">
        <Network size={13} /> Automatic workflows
      </h2>
      <div className="mt-2 space-y-2">
        {processes.length === 0 ? (
          <p className="text-[11px] text-slate-400">Waiting for a state threshold.</p>
        ) : processes.map(({ workflowId, workflowType, event, sensor }) => (
          <article key={workflowId} className="rounded border border-slate-200 p-2 dark:border-slate-700">
            <div className="text-xs font-semibold text-slate-800 dark:text-slate-100">
              {workflowType}
            </div>
            <div className="font-mono text-[9px] text-slate-500">{workflowId}</div>
            <p className="mt-1 text-[10px] text-slate-600 dark:text-slate-300">
              {triggerSummary(sensor)}
            </p>
            <div className="mt-1 text-[9px] text-slate-400">
              latest evidence {event.type} · {event.event_id}
            </div>
            <Link
              to={`/workflows/${encodeURIComponent(workflowId)}`}
              className="mt-2 inline-flex text-[10px] font-medium text-blue-700 hover:underline dark:text-blue-300"
            >
              Inspect workflow {workflowId}
            </Link>
          </article>
        ))}
      </div>
    </section>
  );
}


function KnowledgeOutcome({
  relationships,
  label,
  expectedActorIds,
}: {
  relationships: KnowledgeRelationship[];
  label?: string;
  expectedActorIds: string[];
}) {
  return (
    <section className="rounded-lg border border-emerald-200 bg-emerald-50 p-3 dark:border-emerald-900 dark:bg-emerald-950/30">
      <h2 className="text-xs font-semibold uppercase tracking-wide text-emerald-800 dark:text-emerald-300">
        World + Knowledge outcome
      </h2>
      <p className="mt-1 text-[10px] text-emerald-900 dark:text-emerald-200">
        {label ?? "Journal-backed relationships appear here after execution."}
      </p>
      {relationships.map((relationship, index) => (
        <div key={`${relationship.workflow_id}:${index}`} className="mt-2 rounded bg-white/80 p-2 font-mono text-[9px] text-slate-700 dark:bg-slate-900/70 dark:text-slate-200">
          <div>{relationship.workflow_id}</div>
          <div className="mt-0.5 break-all">
            {relationship.source_id} {relationship.relationship} {relationship.destination_id}
          </div>
        </div>
      ))}
      {relationships.length === 0 && expectedActorIds.length > 0 && (
        <div className="mt-2 break-all font-mono text-[9px] text-emerald-700 dark:text-emerald-300">
          watching {expectedActorIds.join(" · ")}
        </div>
      )}
      <Link to="/knowledge" className="mt-2 inline-flex text-[10px] font-medium text-emerald-800 hover:underline dark:text-emerald-200">
        Open Knowledge
      </Link>
    </section>
  );
}

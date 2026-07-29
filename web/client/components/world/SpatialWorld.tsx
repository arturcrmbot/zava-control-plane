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

interface SpatialWorldDomain {
  workflow_type: string;
  display_name: string;
}

interface SpatialWorldProps {
  scene: WorldSceneContract;
  state: WorldState;
  events: WorldEvent[];
  error: string | null;
  onReset: () => Promise<void>;
  domains?: SpatialWorldDomain[];
  onRunProcess?: (workflowType: string) => Promise<void>;
}

type ActorRecord = Record<string, unknown>;
type KnowledgeRelationship = {
  workflow_id?: string;
  source_id?: string;
  relationship?: string;
  destination_id?: string;
};

const ACTORS_PER_LOCATION: Record<string, number> = {
  customers: 2,
  staff: 2,
  orders: 2,
  inventory_tokens: 2,
  deliveries: 1,
  returns: 1,
};
const JOURNAL_LIMIT = 40;
const PROCESS_LIMIT = 8;
const KPI_LIMIT = 6;

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


/** Capitalises a scene layer's `kind` (e.g. "customer" -> "Customer"). */
function capitalize(value: string): string {
  return value ? value.charAt(0).toUpperCase() + value.slice(1) : value;
}


/** Turns a hyphen/underscore identifier into a readable label, e.g.
 * "demand-spike-response" -> "Demand spike response",
 * "average_wait_minutes" -> "Average wait minutes". Pack-neutral: it only
 * reformats whatever identifier the scene/story payload provides. */
function readableLabel(value: string): string {
  const spaced = value.replace(/[-_]/g, " ").trim();
  return spaced ? spaced.charAt(0).toUpperCase() + spaced.slice(1) : spaced;
}


function actorRecords(state: WorldState, layer: SceneLayer): ActorRecord[] {
  const records = state[layer.state_key];
  return Array.isArray(records)
    ? records.filter((record): record is ActorRecord => (
      typeof record === "object" && record !== null
    )).sort((left, right) => (
      text(right.last_event_id ?? right[layer.id_field])
        .localeCompare(text(left.last_event_id ?? left[layer.id_field]))
    ))
    : [];
}


interface LocationLayerCount {
  layer: SceneLayer;
  count: number;
}


/** Full (uncapped) per-layer actor counts at a location, derived from the
 * real snapshot arrays — distinct from the capped sample of tokens rendered
 * on the map, so a dense world reads at a glance. */
function locationLayerCounts(
  state: WorldState,
  layers: SceneLayer[],
  locationId: string,
): LocationLayerCount[] {
  return layers
    .map((layer) => ({
      layer,
      count: actorRecords(state, layer).filter((actor) => (
        text(actor[layer.location_field]) === locationId
      )).length,
    }))
    .filter((entry) => entry.count > 0);
}


function recentEventByActor(events: WorldEvent[]): Map<string, WorldEvent> {
  const result = new Map<string, WorldEvent>();
  for (const event of events) {
    if (event.actor_id) result.set(event.actor_id, event);
    if (event.target_id) result.set(event.target_id, event);
  }
  return result;
}


interface ProcessItem {
  workflowId: string;
  workflowType: string;
  event?: WorldEvent;
  sensor?: WorldEvent;
  storyStatus?: string;
}


interface StoryStageView {
  workflowType: string;
  displayName: string;
  functionId: string;
  commandType: string;
  successEvent: string;
  skills: string[];
  phases: Array<{ name: string; kind: string }>;
  hitlPersona: string;
  dependencyIds: string[];
  status: string;
  workflowId: string | null;
  autonomy: string;
  reason: string | null;
}


interface StoryView {
  title: string;
  status: string;
  traceId: string;
  stages: StoryStageView[];
  kpis: Record<string, { before: unknown; after: unknown }>;
  failure: { reason: string; workflowType: string } | null;
}


/** Reads only the existing pack-neutral story shape produced by
 * world/packs/*_shock.py's TradingShockState.view(): title, status,
 * trace_id, stages[] and kpis{}. No pack-specific fields are assumed. */
function parseStory(state: WorldState): StoryView | null {
  if (typeof state.story !== "object" || state.story === null) return null;
  const story = state.story as Record<string, unknown>;
  const rawStages = Array.isArray(story.stages)
    ? story.stages.filter((stage): stage is Record<string, unknown> => (
      typeof stage === "object" && stage !== null
    ))
    : [];
  const stages: StoryStageView[] = rawStages.map((stage) => ({
    workflowType: text(stage.workflow_type),
    displayName: text(stage.display_name) || readableLabel(text(stage.workflow_type)),
    functionId: text(stage.function),
    commandType: text(stage.command_type),
    successEvent: text(stage.success_event),
    skills: Array.isArray(stage.skills)
      ? stage.skills.map((skill) => text(skill))
      : [],
    phases: Array.isArray(stage.phases)
      ? stage.phases.flatMap((phase) => {
        if (typeof phase !== "object" || phase === null) return [];
        const value = phase as Record<string, unknown>;
        return [{ name: text(value.name), kind: text(value.kind) }];
      })
      : [],
    hitlPersona: text(stage.hitl_persona),
    dependencyIds: Array.isArray(stage.dependency_ids)
      ? stage.dependency_ids.map((id) => text(id))
      : [],
    status: text(stage.status) || "waiting",
    workflowId: stage.workflow_id != null ? text(stage.workflow_id) : null,
    autonomy: text(stage.autonomy),
    reason: stage.reason != null ? text(stage.reason) : null,
  }));
  const rawKpis = (
    typeof story.kpis === "object" && story.kpis !== null
      ? story.kpis as Record<string, unknown>
      : {}
  );
  const kpis: Record<string, { before: unknown; after: unknown }> = {};
  for (const [metric, value] of Object.entries(rawKpis)) {
    if (typeof value !== "object" || value === null) continue;
    const entry = value as Record<string, unknown>;
    kpis[metric] = { before: entry.before, after: entry.after };
  }
  const rawFailure = (
    typeof story.failure === "object" && story.failure !== null
      ? story.failure as Record<string, unknown>
      : null
  );
  return {
    title: text(story.title),
    status: text(story.status) || "unknown",
    traceId: text(story.trace_id),
    stages,
    kpis,
    failure: rawFailure
      ? {
        reason: text(rawFailure.reason),
        workflowType: text(rawFailure.workflow_type),
      }
      : null,
  };
}


function processEvents(
  events: WorldEvent[],
  configuredTypes: string[],
  state: WorldState,
): ProcessItem[] {
  const accepted = new Set(configuredTypes);
  const byWorkflow = new Map<string, WorldEvent>();
  for (const event of events) {
    if (accepted.size > 0 && !accepted.has(event.type)) continue;
    const workflowId = text(event.payload.workflow_id);
    if (workflowId) byWorkflow.set(workflowId, event);
  }
  const story = (
    typeof state.story === "object" && state.story !== null
      ? state.story as Record<string, unknown>
      : {}
  );
  const stages = Array.isArray(story.stages)
    ? story.stages.filter((stage): stage is Record<string, unknown> => (
      typeof stage === "object" && stage !== null
    ))
    : [];
  const storyProcesses = stages.flatMap((stage): ProcessItem[] => {
    const workflowId = text(stage.workflow_id);
    if (!workflowId) return [];
    const event = byWorkflow.get(workflowId);
    return [{
      workflowId,
      workflowType: text(stage.workflow_type) || "workflow",
      event,
      sensor: event
        ? events.find((candidate) => (
          candidate.trace_id === event.trace_id
          && candidate.type === "sensor.tripped"
        ))
        : undefined,
      storyStatus: text(stage.status),
    }];
  });
  if (storyProcesses.length > 0) {
    return storyProcesses.slice(0, PROCESS_LIMIT);
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
  domains,
  onRunProcess,
}: SpatialWorldProps) {
  const [selectedActor, setSelectedActor] = useState<string | null>(null);
  const [resetting, setResetting] = useState(false);
  const [runningProcess, setRunningProcess] = useState<string | null>(null);
  const latestByActor = useMemo(() => recentEventByActor(events), [events]);
  const processes = useMemo(
    () => processEvents(events, scene.process_event_types ?? [], state),
    [events, scene.process_event_types, state],
  );
  const story = useMemo(() => parseStory(state), [state]);
  const totalActorCount = useMemo(
    () => scene.layers.reduce(
      (sum, layer) => sum + actorRecords(state, layer).length,
      0,
    ),
    [scene.layers, state],
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

  async function runProcess(workflowType: string) {
    if (!onRunProcess) return;
    setRunningProcess(workflowType);
    try {
      await onRunProcess(workflowType);
    } finally {
      setRunningProcess(null);
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
                <span>{scene.locations.length} locations</span>
                <span>{totalActorCount} actors</span>
                <span>{story?.stages.length ?? processes.length} processes</span>
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

        {onRunProcess && domains && domains.length > 0 && (
          <section
            aria-label="Story scenarios"
            data-testid="spatial-story-bar"
            className="flex flex-wrap items-center gap-2 rounded border border-slate-200 bg-white px-3 py-2.5 dark:border-slate-700 dark:bg-slate-900"
          >
            <span className="text-xs font-semibold text-slate-700 dark:text-slate-200">
              Run scenario
            </span>
            {domains.map((domain) => (
              <button
                key={domain.workflow_type}
                type="button"
                data-testid={`run-process-${domain.workflow_type}`}
                onClick={() => void runProcess(domain.workflow_type)}
                disabled={runningProcess !== null}
                className="rounded border border-sky-300 bg-sky-50 px-2.5 py-1.5 text-xs font-medium text-sky-800 hover:bg-sky-100 disabled:opacity-50 dark:border-sky-800 dark:bg-sky-950/40 dark:text-sky-300"
              >
                {runningProcess === domain.workflow_type
                  ? "Running…"
                  : domain.display_name}
              </button>
            ))}
          </section>
        )}

        {error && (
          <div role="alert" className="rounded border border-rose-300 bg-rose-50 px-3 py-2 text-xs text-rose-800">
            {error}
          </div>
        )}

        {story && <StoryControl story={story} />}

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

            {scene.locations.map((location) => {
              const visibleActors = scene.layers.flatMap((layer) => (
                actorRecords(state, layer)
                  .filter((actor) => text(actor[layer.location_field]) === location.id)
                  .slice(0, ACTORS_PER_LOCATION[layer.state_key] ?? 2)
                  .map((actor) => ({ actor, layer }))
              ));
              return (
                <div
                  key={location.id}
                  data-testid={`location-${location.id}`}
                  className="absolute overflow-hidden rounded-lg border border-stone-300 bg-white/75 p-2 shadow-sm backdrop-blur-sm dark:border-slate-700 dark:bg-slate-900/75"
                  style={{
                    left: `${location.x}%`,
                    top: `${location.y}%`,
                    width: `${location.width}%`,
                    height: `${location.height}%`,
                  }}
                >
                  <div className="pointer-events-none flex items-start justify-between gap-2">
                    <div className="min-w-0">
                      <div className="truncate text-[11px] font-semibold text-slate-800 dark:text-slate-100">
                        {location.label}
                      </div>
                      <div className="truncate font-mono text-[9px] text-slate-500">
                        {location.id}
                      </div>
                    </div>
                    <span className="shrink-0 text-right text-[9px] uppercase tracking-wide text-slate-400">
                      {location.kind}
                    </span>
                  </div>
                  {(() => {
                    const counts = locationLayerCounts(state, scene.layers, location.id);
                    return counts.length > 0 ? (
                      <div
                        data-testid={`location-counts-${location.id}`}
                        className="pointer-events-none mt-1 flex flex-wrap gap-x-2 gap-y-0.5 text-[8px] text-slate-500 dark:text-slate-400"
                      >
                        {counts.map(({ layer, count }) => (
                          <span key={layer.state_key}>{layer.label} {count}</span>
                        ))}
                      </div>
                    ) : null;
                  })()}
                  <div className="mt-3 grid grid-cols-2 gap-1">
                    {visibleActors.map(({ actor, layer }) => {
                      const actorId = text(actor[layer.id_field]);
                      const status = text(actor[layer.status_field]);
                      const recent = latestByActor.get(actorId);
                      return (
                        <button
                          key={`${layer.state_key}:${actorId}`}
                          type="button"
                          data-testid={`actor-${actorId}`}
                          data-event-id={recent?.event_id}
                          title={`${layer.kind} ${actorId} · ${status}`}
                          onClick={() => setSelectedActor((current) => (
                            current === actorId ? null : actorId
                          ))}
                          className={
                            "flex min-w-0 items-center gap-1 overflow-hidden rounded border bg-white px-1.5 py-0.5 text-left font-mono text-[8px] shadow-sm dark:bg-slate-950 " +
                            (selectedActor === actorId ? "ring-2 ring-slate-900 dark:ring-white " : "") +
                            (recent ? "scene-event-pulse" : "")
                          }
                          style={{
                            borderColor: layer.colour,
                            color: layer.colour,
                          }}
                        >
                          <span
                            aria-hidden="true"
                            className="h-1.5 w-1.5 shrink-0 rounded-full"
                            style={{ backgroundColor: layer.colour }}
                          />
                          <span className="sr-only">{actorId} · </span>
                          <span className="truncate">
                            {capitalize(layer.kind) || layer.label} · {status || "active"}
                          </span>
                        </button>
                      );
                    })}
                  </div>
                </div>
              );
            })}
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


/** Tailwind-only status color coding, shared by the story badge and stage
 * badges — no new dependency, just semantic color grouping of whatever
 * status string the pack's story/stage view provides. */
function statusBadgeClasses(status: string): string {
  switch (status) {
    case "completed":
      return "border-emerald-300 bg-emerald-50 text-emerald-800 dark:border-emerald-800 dark:bg-emerald-950/40 dark:text-emerald-200";
    case "failed":
      return "border-rose-300 bg-rose-50 text-rose-800 dark:border-rose-800 dark:bg-rose-950/40 dark:text-rose-200";
    case "active":
    case "triggered":
      return "border-blue-300 bg-blue-50 text-blue-800 dark:border-blue-800 dark:bg-blue-950/40 dark:text-blue-200";
    default:
      return "border-slate-300 bg-slate-50 text-slate-600 dark:border-slate-600 dark:bg-slate-800 dark:text-slate-300";
  }
}


/** Pack-neutral operations strip: reads only the existing story shape
 * (title, status, stages, kpis, failure, trace_id) so it works for any
 * pack's *_shock.py story without a new schema version or framework. */
function StoryControl({ story }: { story: StoryView }) {
  const total = story.stages.length;
  const completed = story.stages.filter((stage) => stage.status === "completed").length;
  const progressPct = total > 0 ? Math.round((completed / total) * 100) : 0;

  return (
    <section
      data-testid="story-control"
      className="rounded-lg border border-slate-200 bg-white p-3 dark:border-slate-800 dark:bg-slate-900"
    >
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h2 className="text-sm font-semibold text-slate-900 dark:text-white">
          {story.title || "Live operations story"}
        </h2>
        <span
          data-testid="story-status"
          className={`rounded-full border px-2 py-0.5 text-[10px] font-medium uppercase tracking-wide ${statusBadgeClasses(story.status)}`}
        >
          {story.status}
        </span>
      </div>

      {story.failure && (
        <div
          role="alert"
          data-testid="story-failure"
          className="mt-2 rounded border border-rose-300 bg-rose-50 px-2 py-1.5 text-[11px] text-rose-800 dark:border-rose-900 dark:bg-rose-950/30 dark:text-rose-200"
        >
          {readableLabel(story.failure.workflowType)} failed: {story.failure.reason}
        </div>
      )}

      {total > 0 && (
        <div className="mt-2">
          <div className="flex items-center justify-between text-[11px] text-slate-500 dark:text-slate-400">
            <span>{completed} of {total} processes complete</span>
            <span>{progressPct}%</span>
          </div>
          <div
            role="progressbar"
            aria-valuenow={completed}
            aria-valuemin={0}
            aria-valuemax={total}
            className="mt-1 h-1.5 w-full overflow-hidden rounded bg-slate-200 dark:bg-slate-800"
          >
            <div
              className="h-1.5 rounded bg-emerald-500 transition-all"
              style={{ width: `${progressPct}%` }}
            />
          </div>
        </div>
      )}

      {total > 0 && (
        <div className="mt-3 grid grid-cols-2 gap-2 lg:grid-cols-4">
          {story.stages.map((stage) => (
            <StoryStageCard key={stage.workflowType} stage={stage} />
          ))}
        </div>
      )}

      <StoryKpis kpis={story.kpis} />
    </section>
  );
}


function StoryStageCard({
  stage,
}: {
  stage: StoryStageView;
}) {
  const dependencyLabels = stage.dependencyIds.map((id) => readableLabel(id));
  const dependencyText = dependencyLabels.length === 0
    ? "No dependencies"
    : `${dependencyLabels.length} ${dependencyLabels.length === 1 ? "dependency" : "dependencies"}: ${dependencyLabels.join(", ")}`;

  const body = (
    <>
      <div className="flex items-center justify-between gap-1">
        <span className="text-[11px] font-semibold text-slate-800 dark:text-slate-100">
          {stage.displayName}
        </span>
        <span className={`shrink-0 rounded border px-1.5 py-0.5 text-[9px] uppercase tracking-wide ${statusBadgeClasses(stage.status)}`}>
          {stage.status}
        </span>
      </div>
      <div className="mt-1 text-[9px] text-slate-500 dark:text-slate-400">
        autonomy: {stage.autonomy || "unknown"}
      </div>
      <div className="mt-1 text-[9px] text-slate-500 dark:text-slate-400">
        {dependencyText}
      </div>
      {stage.status === "failed" && stage.reason && (
        <div className="mt-1 text-[9px] text-rose-700 dark:text-rose-300">
          {stage.reason}
        </div>
      )}
      <div className="mt-2 border-t border-slate-100 pt-1.5 text-[9px] text-slate-500 dark:border-slate-800 dark:text-slate-400">
        <div>{stage.phases.length} phases · {stage.skills.length} AI skill{stage.skills.length === 1 ? "" : "s"}</div>
        {stage.commandType && <div className="mt-0.5 font-mono">{stage.commandType} → {stage.successEvent}</div>}
        {stage.hitlPersona && <div className="mt-0.5">HITL · {readableLabel(stage.hitlPersona)}</div>}
      </div>
      <div className="mt-2 text-[10px] font-medium text-blue-700 dark:text-blue-300">
        {stage.workflowId ? "Open workflow →" : "Waiting for trigger"}
      </div>
    </>
  );

  return (
    <div
      data-testid={`story-stage-${stage.workflowType}`}
      className="rounded border border-slate-200 p-2 dark:border-slate-700"
    >
      {stage.workflowId ? (
        <Link
          data-testid={`story-stage-link-${stage.workflowType}`}
          to={`/workflows/${encodeURIComponent(stage.workflowId)}`}
          className="block transition-colors hover:text-blue-700 focus:outline-none focus:ring-2 focus:ring-blue-500 dark:hover:text-blue-300"
        >
          {body}
        </Link>
      ) : body}
    </div>
  );
}


function StoryKpis({
  kpis,
}: {
  kpis: Record<string, { before: unknown; after: unknown }>;
}) {
  const entries = Object.entries(kpis).slice(0, KPI_LIMIT);
  if (entries.length === 0) return null;

  return (
    <div
      data-testid="story-kpis"
      className="mt-3 grid grid-cols-2 gap-2 lg:grid-cols-3"
    >
      {entries.map(([metric, { before, after }]) => (
        <div
          key={metric}
          data-testid={`story-kpi-${metric}`}
          className="rounded border border-slate-200 bg-slate-50 p-2 text-[10px] dark:border-slate-700 dark:bg-slate-800/60"
        >
          <div className="text-[9px] uppercase tracking-wide text-slate-500 dark:text-slate-400">
            {readableLabel(metric)}
          </div>
          <div className="mt-0.5 font-mono text-slate-700 dark:text-slate-200">
            {before == null ? "—" : text(before)} → {after == null ? "Pending" : text(after)}
          </div>
        </div>
      ))}
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
        ) : processes.map(({
          workflowId,
          workflowType,
          event,
          sensor,
          storyStatus,
        }) => (
          <Link
            key={workflowId}
            to={`/workflows/${encodeURIComponent(workflowId)}`}
            data-testid={`workflow-card-${workflowId}`}
            className="block rounded border border-slate-200 p-2 transition-colors hover:border-blue-400 hover:bg-blue-50/60 focus:outline-none focus:ring-2 focus:ring-blue-500 dark:border-slate-700 dark:hover:border-blue-500 dark:hover:bg-blue-950/30"
          >
            <div className="text-xs font-semibold text-slate-800 dark:text-slate-100">
              {workflowType}
            </div>
            <div className="font-mono text-[9px] text-slate-500">{workflowId}</div>
            <p className="mt-1 text-[10px] text-slate-600 dark:text-slate-300">
              {triggerSummary(sensor)}
            </p>
            <div className="mt-1 text-[9px] text-slate-400">
              {event
                ? `latest evidence ${event.type} · ${event.event_id}`
                : `story stage ${storyStatus || "active"}`}
            </div>
            <span className="mt-2 inline-flex text-[10px] font-medium text-blue-700 dark:text-blue-300">
              Inspect workflow {workflowId}
            </span>
          </Link>
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
        {relationships.length > 0
          ? (label ?? "Journal-backed relationships appear here after execution.")
          : "Awaiting journal-backed outcome."}
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

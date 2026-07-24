import { useEffect, useMemo, useState } from "react";
import { useLocation } from "react-router-dom";
import type { WorldSceneMetadata } from "@shared/runtime";
import {
  mapWorldScene,
  type SceneActorToken,
  type SceneJournalEvent,
} from "@shared/worldScene";

interface WorkflowDetail {
  activeException?: {
    id?: string;
    workflowId?: string;
    summary?: string;
    recommendation?: string;
  } | null;
  packDetail?: Record<string, unknown> | null;
  workflow?: { id?: string; status?: string };
}

function workflowIdFromEvent(event: SceneJournalEvent): string | undefined {
  const payload = event.payload ?? {};
  const value = payload.workflow_id ?? payload.workflowId;
  return typeof value === "string" ? value : undefined;
}

function labelFor(key: string): string {
  return key.replace(/([A-Z])/g, " $1").replace(/_/g, " ").trim();
}

function DetailValue({ value }: { value: unknown }) {
  if (value == null) return <span>—</span>;
  if (Array.isArray(value)) {
    return <ul className="list-disc pl-4">{value.map((item, index) => <li key={index}><DetailValue value={item} /></li>)}</ul>;
  }
  if (typeof value === "object") {
    return (
      <dl className="grid grid-cols-[auto_1fr] gap-x-2 gap-y-1">
        {Object.entries(value as Record<string, unknown>).map(([key, item]) => (
          <div key={key} className="contents">
            <dt className="text-slate-500 dark:text-slate-400">{labelFor(key)}</dt>
            <dd><DetailValue value={item} /></dd>
          </div>
        ))}
      </dl>
    );
  }
  return <span>{String(value)}</span>;
}

function ActorToken({
  actor, animation, selected, onSelect,
}: {
  actor: SceneActorToken;
  animation?: string;
  selected: boolean;
  onSelect: () => void;
}) {
  const facts = Object.entries(actor.attributes)
    .filter(([key, value]) => key !== "id" && typeof value !== "object")
    .slice(0, 4);
  return (
    <button
      type="button"
      data-testid={`scene-actor-${actor.id}`}
      data-animation={animation}
      data-position={`${actor.x},${actor.y}`}
      onClick={onSelect}
      style={{ left: `${actor.x * 100}%`, top: `${actor.y * 100}%` }}
      className={`absolute -translate-x-1/2 -translate-y-1/2 max-w-36 rounded border px-2 py-1 text-left text-[10px] shadow-sm ${selected ? "ring-2 ring-blue-500" : "bg-white dark:bg-slate-900 border-slate-300 dark:border-slate-700"}`}
    >
      <span className="block font-mono font-semibold">{actor.id}</span>
      <span className="block truncate">{actor.label}</span>
      <span className="block text-slate-500 dark:text-slate-400">{actor.kind} · {actor.state}</span>
      {facts.map(([key, value]) => <span key={key} className="block text-slate-500 dark:text-slate-400">{labelFor(key)}: {String(value)}</span>)}
    </button>
  );
}

export default function SpatialWorld({
  scene,
  snapshot,
  events,
}: {
  scene: WorldSceneMetadata;
  snapshot: Record<string, unknown>;
  events: SceneJournalEvent[];
}) {
  const mapped = useMemo(() => mapWorldScene(scene, snapshot, events), [scene, snapshot, events]);
  const [selectedActor, setSelectedActor] = useState<string | null>(null);
  const location = useLocation();
  const requestedWorkflowId = useMemo(() => {
    const value = new URLSearchParams(location.search).get("workflow_id")?.trim();
    return value || undefined;
  }, [location.search]);
  const workflowIdFromJournal = useMemo(
    () => [...events].reverse().map(workflowIdFromEvent).find((id): id is string => Boolean(id)),
    [events],
  );
  const workflowId = requestedWorkflowId ?? workflowIdFromJournal;
  const [detail, setDetail] = useState<WorkflowDetail | null>(null);

  useEffect(() => {
    if (!workflowId) {
      setDetail(null);
      return;
    }
    const controller = new AbortController();
    void fetch(`/api/workflows/${encodeURIComponent(workflowId)}`, { signal: controller.signal })
      .then(async (response) => response.ok ? response.json() as Promise<WorkflowDetail> : null)
      .then((value) => { if (!controller.signal.aborted) setDetail(value); })
      .catch(() => { if (!controller.signal.aborted) setDetail(null); });
    return () => controller.abort();
  }, [workflowId]);

  const animationByActor = useMemo(
    () => new Map(mapped.animations.map((animation) => [animation.actorId, animation.animation])),
    [mapped.animations],
  );
  const journal = selectedActor
    ? events.filter((event) => event.actor_id === selectedActor || event.target_id === selectedActor)
    : events;
  const hitl = detail?.packDetail?.hitl;
  const pendingGate = Boolean(
    detail?.workflow?.status === "awaiting_hitl"
      && detail?.activeException?.id,
  ) && (
    hitl == null
    || (
      typeof hitl === "object"
      && (hitl as Record<string, unknown>).required === true
      && (hitl as Record<string, unknown>).outcome === "pending"
    )
  );

  async function resolveGate(resolution: "approve" | "reject") {
    const exceptionId = detail?.activeException?.id;
    if (!exceptionId || !workflowId) return;
    const response = await fetch(`/api/exceptions/${encodeURIComponent(exceptionId)}/resolve`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ resolution, resolvedBy: "world-operator" }),
    });
    if (!response.ok) return;
    const refreshed = await fetch(`/api/workflows/${encodeURIComponent(workflowId)}`);
    if (refreshed.ok) setDetail(await refreshed.json() as WorkflowDetail);
  }

  return (
    <div data-testid="spatial-world-route" className="flex-1 min-w-0 overflow-y-auto bg-slate-50 dark:bg-slate-950 p-6">
      <div className="max-w-[1400px] mx-auto space-y-4">
        <header>
          <h1 className="text-xl font-semibold text-slate-900 dark:text-slate-100">{scene.title}</h1>
          <p className="text-xs text-slate-500 dark:text-slate-400">Live spatial state from the actor world and causal journal.</p>
        </header>
        <section aria-label="Spatial actor map" className="relative min-h-[500px] overflow-hidden rounded-lg border border-slate-200 dark:border-slate-700 bg-slate-100 dark:bg-slate-900">
          {mapped.locations.map((location) => (
            <div
              key={location.id}
              data-testid={`scene-location-${location.id}`}
              style={{ left: `${location.x * 100}%`, top: `${location.y * 100}%` }}
              className="absolute -translate-x-1/2 -translate-y-1/2 text-xs font-medium text-slate-600 dark:text-slate-300"
            >{location.label}</div>
          ))}
          {mapped.actors.map((actor) => (
            <ActorToken
              key={`${actor.id}:${animationByActor.get(actor.id) ?? "still"}`}
              actor={actor}
              animation={animationByActor.get(actor.id)}
              selected={selectedActor === actor.id}
              onSelect={() => setSelectedActor((current) => current === actor.id ? null : actor.id)}
            />
          ))}
        </section>
        <section aria-label="Causal journal" className="rounded-lg border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-900 p-3">
          <h2 className="text-xs font-semibold uppercase tracking-wide text-slate-500 dark:text-slate-400">
            Causal journal{selectedActor ? ` · ${selectedActor}` : ""}
          </h2>
          <ul className="mt-2 space-y-1 font-mono text-xs">
            {journal.map((event) => <li key={event.seq} data-testid={`scene-event-${event.event_id}`}>{event.event_id} · {event.type} · {event.actor_id ?? event.target_id ?? "—"}</li>)}
          </ul>
        </section>
        {detail?.packDetail && (
          <section aria-label="Workflow detail" className="rounded-lg border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-900 p-3 text-xs">
            <h2 className="font-mono font-semibold text-slate-900 dark:text-slate-100">{detail.workflow?.id ?? workflowId}</h2>
            <div data-testid="workflow-detail-status" className="mt-1 text-slate-500 dark:text-slate-400">
              Workflow status: {detail.workflow?.status ?? "—"}
            </div>
            <div className="mt-2"><DetailValue value={detail.packDetail} /></div>
            {pendingGate && (
              <section aria-label="HITL gate audit" className="mt-3 rounded border border-amber-300 bg-amber-50 p-2 text-slate-800 dark:border-amber-800 dark:bg-amber-950/40 dark:text-slate-100">
                <h3 className="font-semibold">HITL gate audit</h3>
                <dl className="mt-1 grid grid-cols-[auto_1fr] gap-x-2 gap-y-1">
                  <dt className="text-slate-500 dark:text-slate-400">State</dt>
                  <dd>{detail.workflow?.status}</dd>
                  <dt className="text-slate-500 dark:text-slate-400">Exception ID</dt>
                  <dd>{detail.activeException?.id}</dd>
                  <dt className="text-slate-500 dark:text-slate-400">Workflow ID</dt>
                  <dd>{detail.activeException?.workflowId ?? detail.workflow?.id ?? workflowId}</dd>
                  {detail.activeException?.summary && (
                    <>
                      <dt className="text-slate-500 dark:text-slate-400">Summary</dt>
                      <dd>{detail.activeException.summary}</dd>
                    </>
                  )}
                  {detail.activeException?.recommendation && (
                    <>
                      <dt className="text-slate-500 dark:text-slate-400">Recommendation</dt>
                      <dd>{detail.activeException.recommendation}</dd>
                    </>
                  )}
                </dl>
                <div className="mt-3 flex gap-2">
                  <button type="button" onClick={() => void resolveGate("approve")} className="btn-primary">Approve</button>
                  <button type="button" onClick={() => void resolveGate("reject")} className="btn-secondary">Decline</button>
                </div>
              </section>
            )}
          </section>
        )}
      </div>
    </div>
  );
}

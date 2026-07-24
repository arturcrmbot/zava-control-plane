import type { WorldSceneMetadata } from "./runtime";

export interface SceneActorToken {
  id: string;
  label: string;
  kind: string;
  state: string;
  locationId?: string;
  route?: string[];
  progress?: number;
  attributes: SceneRecord;
  x: number;
  y: number;
}

export interface SceneAnimation {
  eventId: string;
  actorId: string;
  animation: string;
  seq: number;
}

export interface SceneJournalEvent {
  seq: number;
  event_id: string;
  type: string;
  actor_id?: string | null;
  target_id?: string | null;
  payload?: Record<string, unknown>;
}

export interface WorldSceneMap {
  locations: WorldSceneMetadata["locations"];
  actors: SceneActorToken[];
  animations: SceneAnimation[];
}

type SceneRecord = Record<string, unknown>;

function stringAt(record: SceneRecord, field: string | undefined): string | undefined {
  const value = field ? record[field] : undefined;
  return typeof value === "string" ? value : undefined;
}

function numberAt(record: SceneRecord, field: string | undefined): number | undefined {
  const value = field ? record[field] : undefined;
  return typeof value === "number" && Number.isFinite(value) ? value : undefined;
}

function eventValue(event: SceneJournalEvent, path: string | undefined): string | undefined {
  if (!path) return undefined;
  const root: SceneRecord = { ...event, payload: event.payload ?? {} };
  const value = path.split(".").reduce<unknown>(
    (current, key) => current && typeof current === "object"
      ? (current as SceneRecord)[key]
      : undefined,
    root,
  );
  return typeof value === "string" ? value : undefined;
}

function actorLabel(record: SceneRecord, id: string): string {
  return stringAt(record, "label") ?? stringAt(record, "name") ?? id;
}

function routeAt(record: SceneRecord, field: string | undefined): string[] | undefined {
  const value = field ? record[field] : undefined;
  return Array.isArray(value) && value.every((item) => typeof item === "string") ? value : undefined;
}

function coordinate(value: number): number {
  return Number(value.toFixed(6));
}

function separateCoLocatedActors(actors: SceneActorToken[]): SceneActorToken[] {
  const groups = new Map<string, number[]>();
  actors.forEach((actor, index) => {
    const key = `${actor.x},${actor.y}`;
    const group = groups.get(key) ?? [];
    group.push(index);
    groups.set(key, group);
  });

  const positions = new Map<number, { x: number; y: number }>();
  for (const indices of groups.values()) {
    if (indices.length < 2) continue;
    const anchor = actors[indices[0]];
    const ordered = [...indices].sort((left, right) => (
      actors[left].id.localeCompare(actors[right].id) || left - right
    ));
    const columns = Math.ceil(Math.sqrt(ordered.length));
    const rows = Math.ceil(ordered.length / columns);
    const horizontalDirection = anchor.x <= 0.5 ? 1 : -1;
    const verticalDirection = anchor.y <= 0.5 ? 1 : -1;
    const horizontalRoom = horizontalDirection > 0 ? 0.98 - anchor.x : anchor.x - 0.02;
    const verticalRoom = verticalDirection > 0 ? 0.98 - anchor.y : anchor.y - 0.02;
    const horizontalGap = Math.min(0.105, horizontalRoom / Math.max(columns - 1, 1));
    const verticalGap = Math.min(0.17, verticalRoom / Math.max(rows - 1, 1));

    ordered.forEach((actorIndex, offset) => {
      const column = offset % columns;
      const row = Math.floor(offset / columns);
      positions.set(actorIndex, {
        x: coordinate(anchor.x + (horizontalDirection * column * horizontalGap)),
        y: coordinate(anchor.y + (verticalDirection * row * verticalGap)),
      });
    });
  }

  return actors.map((actor, index) => {
    const position = positions.get(index);
    return position ? { ...actor, ...position } : actor;
  });
}

export function mapWorldScene(
  scene: WorldSceneMetadata,
  snapshot: Record<string, unknown>,
  events: SceneJournalEvent[],
): WorldSceneMap {
  const locations = new Map(scene.locations.map((location) => [location.id, location]));
  const actors = scene.actor_bindings.flatMap((binding) => {
    const collection = snapshot[binding.collection];
    if (!Array.isArray(collection)) return [];
    return collection.flatMap((item): SceneActorToken[] => {
      if (!item || typeof item !== "object") return [];
      const record = item as SceneRecord;
      const id = stringAt(record, binding.id_field);
      if (!id) return [];
      const locationId = stringAt(record, binding.position.location_field);
      const location = locationId ? locations.get(locationId) : undefined;
      const route = routeAt(record, binding.position.route_field);
      const progress = numberAt(record, binding.position.progress_field);
      const start = route?.[0] ? locations.get(route[0]) : undefined;
      const end = route?.at(-1) ? locations.get(route.at(-1)!) : undefined;
      const ratio = Math.max(0, Math.min(1, progress ?? 0));
      const x = numberAt(record, binding.position.x_field)
        ?? (start && end ? start.x + ((end.x - start.x) * ratio) : location?.x ?? 0.5);
      const y = numberAt(record, binding.position.y_field)
        ?? (start && end ? start.y + ((end.y - start.y) * ratio) : location?.y ?? 0.5);
      return [{
        id,
        label: actorLabel(record, id),
        kind: binding.kind,
        state: stringAt(record, binding.state_field) ?? "unknown",
        locationId,
        route,
        progress,
        attributes: record,
        x: coordinate(x),
        y: coordinate(y),
      }];
    });
  });
  const positionedActors = separateCoLocatedActors(actors);
  const actorIds = new Set(positionedActors.map((actor) => actor.id));
  const animations = events.flatMap((event): SceneAnimation[] => {
    const mapping = scene.event_mappings.find((candidate) => candidate.event_type === event.type);
    const actorId = eventValue(event, mapping?.actor_id_field)
      ?? (mapping?.actor_id ? event.actor_id ?? undefined : undefined)
      ?? (mapping?.target_id ? event.target_id ?? undefined : undefined);
    if (!mapping || !actorId || !actorIds.has(actorId)) return [];
    return [{ eventId: event.event_id, actorId, animation: mapping.animation_type, seq: event.seq }];
  });
  return { locations: scene.locations, actors: positionedActors, animations };
}

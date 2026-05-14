/**
 * Cosmic Lens v2 — entity-city aggregation + level-of-detail.
 *
 * Pure helpers that take the raw city list (as returned by `/api/cities`)
 * and condense it for the renderer. Two independent reductions:
 *
 * 1. **Aggregation** (`aggregateCities`) — when many cities share a
 *    conceptual subgroup (e.g. all `Person` rows with `department='Finance'`)
 *    they collapse into one synthetic city labelled e.g. "Finance Team (15)".
 *    The synthetic city carries `aggregated: true` and `members[]` so the
 *    renderer can expand it on click/hover.
 *
 * 2. **Level of detail** (`applyLod`) — when the camera is zoomed out, only
 *    the top-N most-recently-active cities are kept; everything else is
 *    dropped from the frame. Sprite-count is the laptop-safe demo budget.
 *
 * Both functions are pure and side-effect-free so they're trivially
 * unit-testable without rendering the R3F scene.
 */
import type { CityMeta } from "./types";

/** Maximum number of entities of one kind+subgroup before we collapse them.
 *  Set very high (effectively off) so every individual is visible by default
 *  at the current ~3k-entity scale. The aggregation code is kept for the
 *  future case where the dataset grows past laptop-renderable. */
export const AGGREGATION_THRESHOLD = 9999;

/** When the camera distance to the hub origin exceeds this, LOD kicks in.
 *  Set above the OrbitControls maxDistance (45) so LOD never triggers at the
 *  current dataset size. The mechanism is kept for future scale. */
export const LOD_DISTANCE_THRESHOLD = 9999;

/** When LOD is active, this many top-active cities are rendered per frame. */
export const LOD_TOP_N = 50;

/** Optional fields the aggregator/LOD reads off raw cities. CityMeta itself
 *  doesn't declare them yet (the API hasn't started emitting per-entity rows
 *  in the cities endpoint), but the contract is locked here so when entity
 *  rows do land we don't need to revisit the call sites. */
export interface AggregatableCity extends CityMeta {
  /** For Person rows. */
  department?: string | null;
  /** Subkind for Organisation ("vendor"/"client"/"agency") and Money
   *  ("invoice"/"po"/"contract"). */
  subkind?: string | null;
  /** ISO timestamp or epoch ms — used by LOD to pick the most-active cities. */
  last_seen_at?: string | number | null;
}

/** Synthetic city returned by `aggregateCities` when a subgroup is collapsed. */
export interface AggregatedCity extends AggregatableCity {
  aggregated: true;
  members: AggregatableCity[];
}

/** Aggregation rules per `kind` (the entity-graph kind, not the city.kind
 *  bucket). Returning `null` opts the kind out of aggregation. */
function aggregationKey(c: AggregatableCity): string | null {
  // We aggregate on the *entity kind* the city represents. For entity-type
  // cities the kind is on `id` ("Person", "Organisation", "Money"); for
  // hypothetical per-row cities a `kind` field on the row is canonical. We
  // accept either.
  const entityKind = (c.kind === "entity_type" ? c.id : (c as { entity_kind?: string }).entity_kind) || c.id;
  switch (entityKind) {
    case "Person":
      return c.department ? `Person/${c.department}` : null;
    case "Organisation":
      return c.subkind ? `Organisation/${c.subkind}` : null;
    case "Money":
      return c.subkind ? `Money/${c.subkind}` : null;
    default:
      return null; // Asset / Decision / Place / Period / Workflow — no subgroup yet
  }
}

/** Human-readable label for an aggregated subgroup. Department names are
 *  preserved verbatim so "Finance" → "Finance Team"; subkind names get a
 *  pluralising suffix appropriate to the kind. */
function aggregatedLabel(key: string, count: number): string {
  const [kind, sub] = key.split("/", 2);
  if (kind === "Person") {
    return `${sub} Team (${count})`;
  }
  if (kind === "Organisation") {
    const plural = sub.endsWith("y") ? sub.slice(0, -1) + "ies" : sub + "s";
    return `${capitalise(plural)} (${count})`;
  }
  if (kind === "Money") {
    const plural = sub === "po" ? "POs" : sub + "s";
    return `${capitalise(plural)} (${count})`;
  }
  return `${kind} ${sub} (${count})`;
}

function capitalise(s: string): string {
  return s.length === 0 ? s : s[0].toUpperCase() + s.slice(1);
}

/**
 * Collapse subgroups that exceed `AGGREGATION_THRESHOLD` into a single
 * synthetic city per subgroup. Cities without a subgroup key (or in
 * subgroups under the threshold) pass through unchanged.
 */
export function aggregateCities<T extends AggregatableCity>(
  cities: readonly T[],
): (T | AggregatedCity)[] {
  const buckets = new Map<string, T[]>();
  const passthrough: T[] = [];
  for (const c of cities) {
    const key = aggregationKey(c);
    if (!key) {
      passthrough.push(c);
      continue;
    }
    const arr = buckets.get(key);
    if (arr) arr.push(c);
    else buckets.set(key, [c]);
  }

  const out: (T | AggregatedCity)[] = [...passthrough];
  for (const [key, members] of buckets) {
    if (members.length > AGGREGATION_THRESHOLD) {
      out.push({
        id: `agg:${key}`,
        kind: members[0].kind,
        label: aggregatedLabel(key, members.length),
        category: members[0].category,
        count: members.length,
        active: members.some((m) => m.active),
        aggregated: true,
        members,
      } as AggregatedCity);
    } else {
      // Subgroup didn't trigger aggregation — emit individuals.
      out.push(...members);
    }
  }
  return out;
}

/** Parse a `last_seen_at` value into ms since epoch. Returns 0 for null. */
function lastSeenMs(v: string | number | null | undefined): number {
  if (v == null) return 0;
  if (typeof v === "number") return v;
  const t = Date.parse(v);
  return Number.isFinite(t) ? t : 0;
}

/**
 * Drop everything except the top-N most-recently-active cities when the
 * camera is far enough out that individual sprites are sub-pixel anyway.
 * Falls back to `recent_activity_per_min` and finally `count` so the LOD
 * still produces a stable ordering when `last_seen_at` is missing — which
 * it currently is on the entity-type roster (only per-row cities will have
 * it once aggregation is wired end-to-end).
 *
 * `cameraDistance` is the distance from the camera to the hub origin in
 * world units. When ≤ `LOD_DISTANCE_THRESHOLD` everything passes through;
 * above it we keep at most `LOD_TOP_N` cities.
 */
export function applyLod<T extends AggregatableCity>(
  cities: readonly T[],
  cameraDistance: number,
  topN: number = LOD_TOP_N,
  threshold: number = LOD_DISTANCE_THRESHOLD,
): T[] {
  if (cameraDistance <= threshold) return [...cities];
  if (cities.length <= topN) return [...cities];
  const scored = cities.map((c) => ({
    c,
    score:
      lastSeenMs(c.last_seen_at) ||
      (c.recent_activity_per_min ?? 0) * 1e6 ||
      (c.count ?? 0),
  }));
  scored.sort((a, b) => b.score - a.score);
  return scored.slice(0, topN).map((s) => s.c);
}

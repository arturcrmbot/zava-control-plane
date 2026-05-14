/**
 * Cosmic Lens v2 — Plain-TS registries.
 *
 * Pub/sub via simple "version" counter that hooks watch with useFrame.
 * No React state to avoid render thrashing on high-frequency events.
 */

import type { CityMeta, FunctionMeta, Rocket, TrailSample, WorkflowMoonData } from "./types";

class Registry<T> {
  protected items = new Map<string, T>();
  /** Bump this any time items mutate so consumers can detect change. */
  version = 0;

  get(id: string): T | undefined {
    return this.items.get(id);
  }
  has(id: string): boolean {
    return this.items.has(id);
  }
  size(): number {
    return this.items.size;
  }
  values(): T[] {
    return Array.from(this.items.values());
  }
  set(id: string, item: T): void {
    this.items.set(id, item);
    this.version++;
  }
  delete(id: string): boolean {
    const ok = this.items.delete(id);
    if (ok) this.version++;
    return ok;
  }
  clear(): void {
    if (this.items.size === 0) return;
    this.items.clear();
    this.version++;
  }
}

export class FunctionRegistry extends Registry<FunctionMeta> {
  /** Compute a 2π-spaced orbit slot for each function. Stable on order. */
  slotFor(key: string): { angle: number; radius: number } {
    const keys = Array.from(this.items.keys()).sort();
    const idx = keys.indexOf(key);
    const total = Math.max(1, keys.length);
    if (idx < 0) {
      // unknown function — park it at angle 0
      return { angle: 0, radius: 13 };
    }
    return { angle: (idx * 2 * Math.PI) / total, radius: 13 };
  }
}

export class CityRegistry extends Registry<CityMeta> {
  /** Position cache keyed by city id. Filled by force layout. */
  positions = new Map<string, [number, number, number]>();

  setPositions(positions: Map<string, [number, number, number]>): void {
    this.positions = positions;
    this.version++;
  }

  positionOf(id: string): [number, number, number] | undefined {
    return this.positions.get(id);
  }
}

export class MoonRegistry extends Registry<WorkflowMoonData> {
  /** Stable per-workflow angular offset for orbit slot. djb2 hash. */
  private offsetCache = new Map<string, number>();

  offsetFor(workflowId: string): number {
    let cached = this.offsetCache.get(workflowId);
    if (cached !== undefined) return cached;
    let hash = 5381;
    for (let i = 0; i < workflowId.length; i++) {
      hash = ((hash << 5) + hash + workflowId.charCodeAt(i)) | 0;
    }
    cached = (Math.abs(hash) % 1000) / 1000; // 0..1
    this.offsetCache.set(workflowId, cached);
    return cached;
  }
}

export class RocketRegistry extends Registry<Rocket> {
  /** Per-workflow chronological list of cities the workflow has parked at.
   *  Used by HoveredWorkflowPath to draw the "where I've been" history
   *  polyline. Bounded to last MAX_HISTORY visits per workflow. */
  private cityHistory = new Map<string, { city_id: string; ts: number }[]>();
  private static readonly MAX_HISTORY = 24;

  /** Get or create the rocket for a workflow. The factory is invoked only
   *  on first creation so spawn-time fields (color, spawned_at) stay stable
   *  across the workflow's lifetime. */
  upsertForWorkflow(workflowId: string, factory: () => Rocket): Rocket {
    const existing = this.items.get(workflowId);
    if (existing) return existing;
    const created = factory();
    this.items.set(workflowId, created);
    this.version++;
    return created;
  }

  /** Returns the rocket for a workflow, or undefined if none. */
  forWorkflow(workflowId: string): Rocket | undefined {
    return this.items.get(workflowId);
  }

  /** Append a city visit for a workflow's history. Idempotent w.r.t.
   *  consecutive identical city_ids. */
  recordVisit(workflowId: string, cityId: string, ts: number): void {
    const arr = this.cityHistory.get(workflowId) ?? [];
    const last = arr[arr.length - 1];
    if (last && last.city_id === cityId) return;
    arr.push({ city_id: cityId, ts });
    if (arr.length > RocketRegistry.MAX_HISTORY) {
      arr.splice(0, arr.length - RocketRegistry.MAX_HISTORY);
    }
    this.cityHistory.set(workflowId, arr);
    // Bump version so reactive consumers (e.g. HoveredWorkflowPath's
    // historyPoints useMemo) re-compute when a new visit is recorded.
    this.version++;
  }

  /** Returns chronological city visits for a workflow, oldest first. */
  historyFor(workflowId: string): { city_id: string; ts: number }[] {
    return this.cityHistory.get(workflowId) ?? [];
  }

  /** Returns rockets currently parked (idle) at a given city. */
  atCity(cityId: string): Rocket[] {
    const out: Rocket[] = [];
    for (const r of this.items.values()) {
      if (r.current_city_id === cityId && r.phase === "idle") out.push(r);
    }
    return out;
  }

  /** Returns the rocket for a given workflow if alive (non-done), else undefined. */
  fromWorkflow(workflowId: string): Rocket[] {
    const r = this.items.get(workflowId);
    if (!r || r.phase === "done") return [];
    return [r];
  }

  /** Drop rockets whose phase has reached the terminal "done" state.
   *  Cheap to call every frame — no time gating required because rockets
   *  only reach "done" after the burst animation has finished. */
  pruneCompleted(): void {
    const to_delete: string[] = [];
    for (const [id, r] of this.items.entries()) {
      if (r.phase === "done") to_delete.push(id);
    }
    for (const id of to_delete) this.delete(id);
    if (to_delete.length > 0) {
      // version already bumped by delete() per id, but ensure consumers
      // see at least one bump even if to_delete was empty pre-call.
    }
  }

  /** Backwards-compat alias for the old name. The 2-arg form is ignored.
   *  Some legacy callers may still pass (now, maxAgeMs). */
  latestForWorkflow(workflowId: string): Rocket | undefined {
    return this.forWorkflow(workflowId);
  }
}

export class TrailRegistry {
  private samples: TrailSample[] = [];
  private cap: number;
  version = 0;

  constructor(cap = 500) {
    this.cap = cap;
  }

  push(sample: TrailSample): void {
    this.samples.push(sample);
    if (this.samples.length > this.cap) {
      this.samples.shift();
    }
    this.version++;
  }

  /** Returns visible samples with computed alpha based on age. */
  visible(now: number, decayMs = 60_000): { sample: TrailSample; alpha: number }[] {
    const out: { sample: TrailSample; alpha: number }[] = [];
    for (const s of this.samples) {
      const age = now - s.emitted_at;
      if (age >= decayMs) continue;
      out.push({ sample: s, alpha: 1 - age / decayMs });
    }
    return out;
  }

  size(): number {
    return this.samples.length;
  }

  clear(): void {
    if (this.samples.length === 0) return;
    this.samples = [];
    this.version++;
  }
}

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
  /** Returns rockets currently parked at a given city. */
  atCity(cityId: string): Rocket[] {
    const out: Rocket[] = [];
    for (const r of this.items.values()) {
      if (r.city_id === cityId && r.phase === "parked") out.push(r);
    }
    return out;
  }

  /** Returns rockets dispatched from a given workflow that are still alive. */
  fromWorkflow(workflowId: string): Rocket[] {
    const out: Rocket[] = [];
    for (const r of this.items.values()) {
      if (r.origin_workflow_id === workflowId && r.phase !== "done") out.push(r);
    }
    return out;
  }

  /** Drop rockets older than `maxAgeMs` in `done` state. */
  pruneCompleted(now: number, maxAgeMs = 5000): void {
    const to_delete: string[] = [];
    for (const [id, r] of this.items.entries()) {
      if (r.phase === "done" && r.returned_at !== undefined && now - r.returned_at > maxAgeMs) {
        to_delete.push(id);
      }
    }
    for (const id of to_delete) this.delete(id);
  }

  /** Find the most recent live rocket for a workflow (used to detect "completion" signals). */
  latestForWorkflow(workflowId: string): Rocket | undefined {
    let latest: Rocket | undefined;
    for (const r of this.items.values()) {
      if (r.origin_workflow_id !== workflowId) continue;
      if (r.phase === "done") continue;
      if (!latest || r.dispatched_at > latest.dispatched_at) latest = r;
    }
    return latest;
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

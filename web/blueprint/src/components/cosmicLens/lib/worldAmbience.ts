/**
 * World ambience: how busy each function is running the business, with or
 * without a workflow in flight. Fed by `world.activity` flashes, which the
 * relay coalesces (at most one per function per second, carrying `count`).
 */
import { useEffect, useState } from "react";
import type { CosmicFlash } from "./types";

export const AMBIENCE_WINDOW_MS = 60_000;
/** Shortest observation span used for a rate, so the first seconds after
 *  mount don't extrapolate one flash into a huge per-minute figure. */
const MIN_SPAN_MS = 10_000;

export interface AmbientSample {
  at: number;
  fn: string;
  count: number;
}

export function ambientSamples(flashes: CosmicFlash[], at: number): AmbientSample[] {
  const samples: AmbientSample[] = [];
  for (const f of flashes) {
    if (f.type !== "world.activity" || !f.function) continue;
    samples.push({ at, fn: f.function, count: Math.max(1, f.count ?? 1) });
  }
  return samples;
}

/** World events per minute for each function over the trailing window. */
export function ambientRates(
  samples: AmbientSample[],
  now: number,
  observedSince: number,
  windowMs: number = AMBIENCE_WINDOW_MS,
): Map<string, number> {
  const cutoff = now - windowMs;
  const totals = new Map<string, number>();
  for (const s of samples) {
    if (s.at < cutoff || s.at > now) continue;
    totals.set(s.fn, (totals.get(s.fn) ?? 0) + s.count);
  }
  const spanMs = Math.min(windowMs, Math.max(MIN_SPAN_MS, now - observedSince));
  const rates = new Map<string, number>();
  for (const [fn, total] of totals) {
    rates.set(fn, Math.max(1, Math.round((total / spanMs) * 60_000)));
  }
  return rates;
}

function sameRates(a: Map<string, number>, b: Map<string, number>): boolean {
  if (a.size !== b.size) return false;
  for (const [fn, rate] of a) if (b.get(fn) !== rate) return false;
  return true;
}

export function useWorldAmbience(
  flashesRef: React.MutableRefObject<{ buffer: CosmicFlash[]; version: number }>,
): Map<string, number> {
  const [rates, setRates] = useState<Map<string, number>>(() => new Map());
  useEffect(() => {
    const observedSince = Date.now();
    let lastVersion = flashesRef.current.version;
    let samples: AmbientSample[] = [];
    const interval = window.setInterval(() => {
      const ref = flashesRef.current;
      const now = Date.now();
      const delta = ref.version - lastVersion;
      if (delta > 0) {
        const fresh = ref.buffer.slice(Math.max(0, ref.buffer.length - delta));
        samples.push(...ambientSamples(fresh, now));
        lastVersion = ref.version;
      }
      samples = samples.filter((s) => s.at >= now - AMBIENCE_WINDOW_MS);
      const next = ambientRates(samples, now, observedSince);
      setRates((prev) => (sameRates(prev, next) ? prev : next));
    }, 1000);
    return () => window.clearInterval(interval);
  }, [flashesRef]);
  return rates;
}

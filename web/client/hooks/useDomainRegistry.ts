// web/client/hooks/useDomainRegistry.ts
//
// Single source of truth for everything the Control Plane needs to know
// about live workflow types: their display name, ordered phase list, and
// HITL phase kinds. Sourced from /api/blueprint/composition (which itself
// auto-derives from api.shared.domains.DOMAINS) so a newly graduated
// domain auto-appears in every UI surface without per-domain hardcoding.
//
// Replaces the dozen-plus `*_PHASE_ORDER` constants that used to live in
// web/shared/types.ts and the matching switch statements in
// PhaseTimeline.tsx / PhaseRibbon.tsx / Feed.tsx KNOWN_DOMAINS.

import { useEffect, useState } from "react";

export type DomainPhase = { name: string; kind: "deterministic" | "agent" | "hitl" };

export type DomainRegistryEntry = {
  workflow_type: string;
  name: string;
  status: "live" | "aspirational";
  phases: DomainPhase[];
};

export type DomainRegistry = {
  byType: Map<string, DomainRegistryEntry>;
  loaded: boolean;
};

let _cache: DomainRegistry | null = null;
let _inflight: Promise<DomainRegistry> | null = null;
const _subscribers = new Set<(reg: DomainRegistry) => void>();

async function _load(): Promise<DomainRegistry> {
  if (_cache) return _cache;
  if (_inflight) return _inflight;
  _inflight = (async () => {
    try {
      const res = await fetch("/api/blueprint/composition");
      const data = await res.json();
      const domains: DomainRegistryEntry[] = data?.domains ?? [];
      const byType = new Map<string, DomainRegistryEntry>();
      for (const d of domains) {
        if (d.workflow_type) byType.set(d.workflow_type, d);
      }
      _cache = { byType, loaded: true };
    } catch {
      _cache = { byType: new Map(), loaded: true };
    }
    _subscribers.forEach((cb) => cb(_cache!));
    _inflight = null;
    return _cache!;
  })();
  return _inflight;
}

export function useDomainRegistry(): DomainRegistry {
  const [reg, setReg] = useState<DomainRegistry>(_cache ?? { byType: new Map(), loaded: false });
  useEffect(() => {
    let cancelled = false;
    if (_cache) {
      setReg(_cache);
    } else {
      _load().then((r) => { if (!cancelled) setReg(r); });
    }
    _subscribers.add(setReg);
    return () => { cancelled = true; _subscribers.delete(setReg); };
  }, []);
  return reg;
}

/** Convenience: ordered phase display names for a workflow_type. Empty array if unknown / not loaded. */
export function usePhaseOrderFor(workflowType: string | undefined): string[] {
  const reg = useDomainRegistry();
  if (!workflowType) return [];
  return reg.byType.get(workflowType)?.phases?.map((p) => p.name) ?? [];
}

/** Convenience: sorted list of live workflow_types, for filter chips. */
export function useLiveWorkflowTypes(): string[] {
  const reg = useDomainRegistry();
  const out: string[] = [];
  reg.byType.forEach((entry, wt) => {
    if (entry.status === "live") out.push(wt);
  });
  return out.sort();
}

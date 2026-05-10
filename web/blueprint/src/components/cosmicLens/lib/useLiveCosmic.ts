/**
 * Cosmic Lens v2 — Single source of truth.
 *
 * Polls the v2 endpoints, subscribes to /api/blueprint/stream for SSE,
 * and exposes:
 *   - inFlight, personas, functions, cities (state, refreshed periodically)
 *   - flashesRef: ref to a circular buffer of recent flash events for
 *     useFrame consumers (animation primitives) — NOT React state, so
 *     high-frequency events don't trigger re-renders.
 *   - mode + setMode for capability/entity toggling
 *   - status: "connecting" | "watching" | "offline"
 *
 * One hook, one connection. Components mount it once at the scene root
 * and pass the result down via props (or, for animation-only consumers,
 * subscribe to flashesRef directly).
 */

import { useCallback, useEffect, useRef, useState } from "react";
import {
  ENDPOINTS,
  type CityMeta,
  type CosmicFlash,
  type CosmicMode,
  type FunctionMeta,
  type PersonaState,
  type WorkflowMoonData,
} from "./types";

export type CosmicStatus = "connecting" | "watching" | "offline";

const FLASH_BUFFER_SIZE = 200;
const POLL_MS = 3000;
const CITIES_POLL_MS = 30_000;

interface FlashRefValue {
  /** Circular buffer of recent flashes. Most recent at end. */
  buffer: CosmicFlash[];
  /** Bumped every push; useFrame consumers compare to detect new entries. */
  version: number;
}

export interface UseLiveCosmicResult {
  inFlight: WorkflowMoonData[];
  personas: PersonaState[];
  functions: FunctionMeta[];
  cities: CityMeta[];
  flashesRef: React.MutableRefObject<FlashRefValue>;
  mode: CosmicMode;
  setMode: (mode: CosmicMode) => void;
  status: CosmicStatus;
  injectBurst: (n?: number) => Promise<void>;
  seedKpis: () => Promise<void>;
}

/** Helper: array safety wrappers because backends sometimes return {workflows:[...]} or [...]. */
function unwrapArray<T>(data: unknown, key: string): T[] {
  if (Array.isArray(data)) return data as T[];
  if (data && typeof data === "object") {
    const obj = data as Record<string, unknown>;
    if (Array.isArray(obj[key])) return obj[key] as T[];
  }
  return [];
}

export function useLiveCosmic(): UseLiveCosmicResult {
  const [inFlight, setInFlight] = useState<WorkflowMoonData[]>([]);
  const [personas, setPersonas] = useState<PersonaState[]>([]);
  const [functions, setFunctions] = useState<FunctionMeta[]>([]);
  const [cities, setCities] = useState<CityMeta[]>([]);
  const [mode, setMode] = useState<CosmicMode>("capabilities");
  const [status, setStatus] = useState<CosmicStatus>("connecting");

  const flashesRef = useRef<FlashRefValue>({ buffer: [], version: 0 });

  // ---- Polling ----
  useEffect(() => {
    let cancelled = false;
    let timer: number | undefined;

    async function pollOnce() {
      if (cancelled) return;
      try {
        const [wfRes, personaRes, fnRes] = await Promise.all([
          fetch(ENDPOINTS.inFlight).then((r) => r.json()),
          fetch(ENDPOINTS.personas).then((r) => r.json()),
          fetch(ENDPOINTS.functions).then((r) => r.json()),
        ]);
        if (cancelled) return;
        setInFlight(unwrapArray<WorkflowMoonData>(wfRes, "workflows"));
        setPersonas(unwrapArray<PersonaState>(personaRes, "personas"));
        setFunctions(unwrapArray<FunctionMeta>(fnRes, "functions"));
      } catch (err) {
        // soft-fail; SSE may still be working
        console.warn("[useLiveCosmic] poll error", err);
      } finally {
        if (!cancelled) {
          timer = window.setTimeout(pollOnce, POLL_MS);
        }
      }
    }

    pollOnce();
    return () => {
      cancelled = true;
      if (timer) clearTimeout(timer);
    };
  }, []);

  // ---- Cities polling (slower) ----
  useEffect(() => {
    let cancelled = false;
    let timer: number | undefined;

    async function pollCities() {
      if (cancelled) return;
      try {
        const url = `${ENDPOINTS.cities}?mode=${mode}`;
        const res = await fetch(url);
        if (!res.ok) {
          // endpoint not yet implemented in Phase A — soft fail
          if (!cancelled) timer = window.setTimeout(pollCities, CITIES_POLL_MS);
          return;
        }
        const data = await res.json();
        if (cancelled) return;
        setCities(unwrapArray<CityMeta>(data, "cities"));
      } catch (err) {
        // ignore — Phase A may not have this endpoint yet
      } finally {
        if (!cancelled) timer = window.setTimeout(pollCities, CITIES_POLL_MS);
      }
    }

    pollCities();
    return () => {
      cancelled = true;
      if (timer) clearTimeout(timer);
    };
  }, [mode]);

  // ---- SSE ----
  useEffect(() => {
    let cancelled = false;
    let es: EventSource | null = null;
    let reconnectTimer: number | undefined;

    function connect() {
      if (cancelled) return;
      setStatus("connecting");
      es = new EventSource(ENDPOINTS.observatorySse);

      es.addEventListener("hello", () => {
        if (cancelled) return;
        setStatus("watching");
      });

      es.addEventListener("event", (raw) => {
        if (cancelled) return;
        try {
          const data = JSON.parse((raw as MessageEvent).data) as Partial<CosmicFlash>;
          if (!data || typeof data.type !== "string") return;
          const flash: CosmicFlash = {
            type: data.type,
            ts: typeof data.ts === "number" ? data.ts : Date.now() / 1000,
            workflow_id: data.workflow_id,
            caller_workflow_id: data.caller_workflow_id,
            persona: data.persona,
            agent_name: data.agent_name,
            tool_name: (data as Record<string, unknown>).tool_name as string | undefined,
            entity_kind: data.entity_kind,
            entity_id: data.entity_id,
            verb: data.verb,
            reason: data.reason,
            phase_name: data.phase_name,
            decision_id: data.decision_id,
            function: (data as Record<string, unknown>).function as string | undefined,
          };
          const ref = flashesRef.current;
          ref.buffer.push(flash);
          if (ref.buffer.length > FLASH_BUFFER_SIZE) {
            ref.buffer.splice(0, ref.buffer.length - FLASH_BUFFER_SIZE);
          }
          ref.version++;
        } catch (err) {
          // skip malformed events silently
        }
      });

      es.onerror = () => {
        if (cancelled) return;
        setStatus("offline");
        es?.close();
        es = null;
        reconnectTimer = window.setTimeout(connect, 3000);
      };
    }

    connect();
    return () => {
      cancelled = true;
      if (reconnectTimer) clearTimeout(reconnectTimer);
      es?.close();
    };
  }, []);

  // ---- Actions ----
  const injectBurst = useCallback(async (n = 8) => {
    try {
      await fetch(ENDPOINTS.injectBurst(n), { method: "POST" });
    } catch (err) {
      console.warn("[useLiveCosmic] injectBurst error", err);
    }
  }, []);

  const seedKpis = useCallback(async () => {
    try {
      await fetch(ENDPOINTS.seedKpis, { method: "POST" });
    } catch (err) {
      console.warn("[useLiveCosmic] seedKpis error", err);
    }
  }, []);

  return {
    inFlight,
    personas,
    functions,
    cities,
    flashesRef,
    mode,
    setMode,
    status,
    injectBurst,
    seedKpis,
  };
}

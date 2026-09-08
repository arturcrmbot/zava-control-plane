// web/client/hooks/useResolutionStore.tsx
//
// React context for optimistic resolutions. When a card's inline action
// fires, schedule() owns its pending operation and pre-dispatch Undo.
// record() remains for local-only actions such as snoozing. Only confirmed
// history is persisted; pending operations and Undo never survive reload.
//
// Persistence: the map is mirrored to localStorage under a day-keyed slot
// (`fleetctl.resolutions.<YYYY-MM-DD>`) so the operator's "All my decisions
// today" view survives reloads. Yesterday's slot is left in place but never
// hydrated, so it self-prunes naturally and we don't blow up storage.
import {
  createContext, useCallback, useContext, useEffect, useMemo, useRef, useState,
} from "react";
import type { ReactNode } from "react";

export interface Resolution {
  verb: string;
  actor: string;
  actedAt: number;        // seconds since epoch
  undoable: boolean;
  pending?: boolean;
}

type ResolutionDetails = Pick<Resolution, "verb" | "actor" | "actedAt">;
export const RESOLUTION_GRACE_MS = 5_000;

interface PendingAction {
  dispatched: boolean;
  cancel(): void;
}

interface ResolutionAPI {
  get(id: string): Resolution | undefined;
  record(id: string, r: ResolutionDetails): void;
  schedule(id: string, r: ResolutionDetails, operation: () => Promise<void>, delayMs?: number): Promise<boolean>;
  undo(id: string): boolean;
  revert(id: string): void;
  all(): Record<string, Resolution>;
}

const Ctx = createContext<ResolutionAPI | null>(null);

function todayKey(): string {
  const d = new Date();
  const y = d.getFullYear();
  const m = String(d.getMonth() + 1).padStart(2, "0");
  const day = String(d.getDate()).padStart(2, "0");
  return `fleetctl.resolutions.${y}-${m}-${day}`;
}

function readPersisted(): Record<string, Resolution> {
  if (typeof window === "undefined") return {};
  try {
    const raw = window.localStorage.getItem(todayKey());
    if (!raw) return {};
    const parsed = JSON.parse(raw) as Record<string, Resolution>;
    if (!parsed || typeof parsed !== "object" || Array.isArray(parsed)) return {};
    return Object.fromEntries(
      Object.entries(parsed)
        .filter(([, value]) => value && typeof value === "object" && !value.pending)
        .map(([id, value]) => [id, { ...value, undoable: false }]),
    );
  } catch {
    return {};
  }
}

function writePersisted(map: Record<string, Resolution>): void {
  if (typeof window === "undefined") return;
  try {
    const confirmed = Object.fromEntries(
      Object.entries(map)
        .filter(([, value]) => !value.pending)
        .map(([id, value]) => [id, { ...value, undoable: false }]),
    );
    window.localStorage.setItem(todayKey(), JSON.stringify(confirmed));
  } catch {
    // Quota or privacy-mode: in-memory state still works.
  }
}

export function ResolutionProvider({
  children, undoTtlMs = 30_000,
}: { children: ReactNode; undoTtlMs?: number }) {
  const [map, setMap] = useState<Record<string, Resolution>>(() => readPersisted());
  const timersRef = useRef<Record<string, ReturnType<typeof setTimeout>>>({});
  const pendingRef = useRef<Record<string, PendingAction>>({});

  const mountedRef = useRef(true);
  useEffect(() => {
    mountedRef.current = true;
    return () => {
      mountedRef.current = false;
      for (const t of Object.values(timersRef.current)) clearTimeout(t);
      timersRef.current = {};
      for (const pending of Object.values(pendingRef.current)) pending.cancel();
    };
  }, []);

  // A reload must not turn an unsent action into completed history.
  useEffect(() => {
    writePersisted(map);
  }, [map]);

  const get = useCallback((id: string) => map[id], [map]);
  const all = useCallback(() => map, [map]);

  const record = useCallback(
    (id: string, r: ResolutionDetails) => {
      setMap((prev) => ({ ...prev, [id]: { ...r, undoable: true } }));
      const existing = timersRef.current[id];
      if (existing) clearTimeout(existing);
      timersRef.current[id] = setTimeout(() => {
        if (!mountedRef.current) return;
        setMap((prev) =>
          prev[id] ? { ...prev, [id]: { ...prev[id], undoable: false } } : prev,
        );
        delete timersRef.current[id];
      }, undoTtlMs);
    },
    [undoTtlMs],
  );

  const removeRecord = useCallback((id: string) => {
    if (mountedRef.current) {
      setMap((prev) => {
        const next = { ...prev };
        delete next[id];
        return next;
      });
    }
    const t = timersRef.current[id];
    if (t) {
      clearTimeout(t);
      delete timersRef.current[id];
    }
  }, []);

  const revert = useCallback((id: string) => {
    const pending = pendingRef.current[id];
    if (pending && !pending.dispatched) {
      pending.cancel();
      return;
    }
    removeRecord(id);
  }, [removeRecord]);

  const schedule = useCallback(
    (id: string, r: ResolutionDetails, operation: () => Promise<void>, delayMs = RESOLUTION_GRACE_MS) => {
      if (!mountedRef.current || pendingRef.current[id]) {
        return Promise.reject(new Error("This resolution cannot be scheduled while unavailable or pending"));
      }
      const oldTimer = timersRef.current[id];
      if (oldTimer !== undefined) {
        clearTimeout(oldTimer);
        delete timersRef.current[id];
      }
      setMap((prev) => ({ ...prev, [id]: { ...r, pending: true, undoable: delayMs > 0 } }));
      return new Promise<boolean>((resolve, reject) => {
        let timer: ReturnType<typeof setTimeout> | undefined;
        const pending: PendingAction = {
          dispatched: false,
          cancel() {
            if (pending.dispatched || pendingRef.current[id] !== pending) return;
            if (timer !== undefined) clearTimeout(timer);
            delete pendingRef.current[id];
            removeRecord(id);
            resolve(false);
          },
        };
        pendingRef.current[id] = pending;
        const dispatch = async () => {
          pending.dispatched = true;
          setMap((prev) => prev[id] ? { ...prev, [id]: { ...prev[id], undoable: false } } : prev);
          try {
            await operation();
            if (mountedRef.current) {
              setMap((prev) => ({
                ...prev, [id]: { ...r, pending: false, undoable: false },
              }));
            }
            resolve(true);
          } catch (error) {
            removeRecord(id);
            reject(error);
          } finally {
            delete pendingRef.current[id];
          }
        };
        if (delayMs > 0) timer = setTimeout(() => { void dispatch(); }, delayMs);
        else void dispatch();
      });
    },
    [removeRecord],
  );

  const undo = useCallback((id: string): boolean => {
    const pending = pendingRef.current[id];
    if (pending) {
      if (pending.dispatched) return false;
      pending.cancel();
      return true;
    }
    // Toasts retain callbacks across renders; the live timer owns local Undo.
    if (timersRef.current[id] === undefined) return false;
    revert(id);
    return true;
  }, [revert]);

  const api = useMemo<ResolutionAPI>(
    () => ({ get, record, schedule, undo, revert, all }),
    [get, record, schedule, undo, revert, all],
  );

  return <Ctx.Provider value={api}>{children}</Ctx.Provider>;
}

export function useResolutionStore(): ResolutionAPI {
  const v = useContext(Ctx);
  if (!v) throw new Error("useResolutionStore must be used inside <ResolutionProvider>");
  return v;
}

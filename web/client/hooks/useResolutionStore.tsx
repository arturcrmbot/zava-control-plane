// web/client/hooks/useResolutionStore.tsx
//
// React context for optimistic resolutions. When a card's inline action
// fires, the caller `record()`s a resolution against the card's id; that
// flips the card to ResolvedCard in place. The store keeps `undoable=true`
// for `undoTtlMs` (default 30s); after that the undo button hides. revert()
// rolls back (used on backend failure or explicit undo click).
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
}

interface ResolutionAPI {
  get(id: string): Resolution | undefined;
  record(id: string, r: Omit<Resolution, "undoable">): void;
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
    return parsed && typeof parsed === "object" ? parsed : {};
  } catch {
    return {};
  }
}

function writePersisted(map: Record<string, Resolution>): void {
  if (typeof window === "undefined") return;
  try {
    window.localStorage.setItem(todayKey(), JSON.stringify(map));
  } catch {
    // Quota or privacy-mode: in-memory state still works.
  }
}

export function ResolutionProvider({
  children, undoTtlMs = 30_000,
}: { children: ReactNode; undoTtlMs?: number }) {
  const [map, setMap] = useState<Record<string, Resolution>>(() => readPersisted());
  const timersRef = useRef<Record<string, ReturnType<typeof setTimeout>>>({});

  const mountedRef = useRef(true);
  useEffect(() => {
    return () => {
      mountedRef.current = false;
      for (const t of Object.values(timersRef.current)) clearTimeout(t);
    };
  }, []);

  // Mirror every change to localStorage so "All my decisions today" survives
  // a reload. Hydrated rows arrive with `undoable: true` but the undo timer
  // is not restarted — past-the-grace-period undo would be confusing.
  useEffect(() => {
    writePersisted(map);
  }, [map]);

  const get = useCallback((id: string) => map[id], [map]);
  const all = useCallback(() => map, [map]);

  const record = useCallback(
    (id: string, r: Omit<Resolution, "undoable">) => {
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

  const revert = useCallback((id: string) => {
    setMap((prev) => {
      const next = { ...prev };
      delete next[id];
      return next;
    });
    const t = timersRef.current[id];
    if (t) {
      clearTimeout(t);
      delete timersRef.current[id];
    }
  }, []);

  const api = useMemo<ResolutionAPI>(
    () => ({ get, record, revert, all }),
    [get, record, revert, all],
  );

  return <Ctx.Provider value={api}>{children}</Ctx.Provider>;
}

export function useResolutionStore(): ResolutionAPI {
  const v = useContext(Ctx);
  if (!v) throw new Error("useResolutionStore must be used inside <ResolutionProvider>");
  return v;
}

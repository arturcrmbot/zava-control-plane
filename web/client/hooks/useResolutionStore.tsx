// web/client/hooks/useResolutionStore.tsx
//
// React context for optimistic resolutions. When a card's inline action
// fires, the caller `record()`s a resolution against the card's id; that
// flips the card to ResolvedCard in place. The store keeps `undoable=true`
// for `undoTtlMs` (default 30s); after that the undo button hides. revert()
// rolls back (used on backend failure or explicit undo click).
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

export function ResolutionProvider({
  children, undoTtlMs = 30_000,
}: { children: ReactNode; undoTtlMs?: number }) {
  const [map, setMap] = useState<Record<string, Resolution>>({});
  const timersRef = useRef<Record<string, ReturnType<typeof setTimeout>>>({});

  useEffect(() => {
    return () => {
      for (const t of Object.values(timersRef.current)) clearTimeout(t);
    };
  }, []);

  const get = useCallback((id: string) => map[id], [map]);
  const all = useCallback(() => map, [map]);

  const record = useCallback(
    (id: string, r: Omit<Resolution, "undoable">) => {
      setMap((prev) => ({ ...prev, [id]: { ...r, undoable: true } }));
      const existing = timersRef.current[id];
      if (existing) clearTimeout(existing);
      timersRef.current[id] = setTimeout(() => {
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

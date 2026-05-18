// web/client/components/feed/Toast.tsx
//
// Minimal in-app toast. One queue, top-right, auto-dismissed after TTL.
// Used by HITLCard/ExceptionCard failure paths ("Couldn't resolve — try
// again").
import { createContext, useCallback, useContext, useEffect, useState } from "react";
import type { ReactNode } from "react";

interface ToastEntry { id: number; msg: string; }

interface API {
  show(msg: string, ttlMs?: number): void;
}

const Ctx = createContext<API | null>(null);

export function ToastProvider({ children }: { children: ReactNode }) {
  const [items, setItems] = useState<ToastEntry[]>([]);

  const show = useCallback((msg: string, ttlMs = 4_000) => {
    const id = Date.now() + Math.random();
    setItems((prev) => [...prev, { id, msg }]);
    setTimeout(() => {
      setItems((prev) => prev.filter((i) => i.id !== id));
    }, ttlMs);
  }, []);

  useEffect(() => () => setItems([]), []);

  return (
    <Ctx.Provider value={{ show }}>
      {children}
      <div className="fixed top-3 right-3 z-50 space-y-2 pointer-events-none">
        {items.map((i) => (
          <div
            key={i.id}
            role="status"
            className="pointer-events-auto bg-slate-900 text-white text-xs px-3 py-2 rounded shadow"
          >{i.msg}</div>
        ))}
      </div>
    </Ctx.Provider>
  );
}

export function useToast(): API {
  const v = useContext(Ctx);
  if (!v) throw new Error("useToast must be used inside <ToastProvider>");
  return v;
}

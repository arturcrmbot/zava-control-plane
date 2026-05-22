// web/client/components/feed/Toast.tsx
//
// Minimal in-app toast. One queue, top-right, auto-dismissed after TTL.
// Used by HITLCard/ExceptionCard failure paths ("Couldn't resolve — try
// again") and by successful resolutions ("Approved — Undo", with an action
// button that calls back into the caller to revert before the server is
// hit).
import { createContext, useCallback, useContext, useEffect, useState } from "react";
import type { ReactNode } from "react";
import { REPLAY_BLOCKED_EVENT } from "@client/lib/api";
import type { ReplayBlockedDetail } from "@client/lib/api";

interface ToastAction {
  label: string;
  onAction: () => void;
}

interface ToastEntry {
  id: number;
  msg: string;
  action?: ToastAction;
  intent: "neutral" | "danger";
}

interface API {
  show(msg: string, ttlMs?: number): void;
  showInfo(msg: string, ttlMs?: number): void;
  showWithAction(opts: { msg: string; action: ToastAction; ttlMs?: number; intent?: "neutral" | "danger" }): void;
}

const Ctx = createContext<API | null>(null);

export function ToastProvider({ children }: { children: ReactNode }) {
  const [items, setItems] = useState<ToastEntry[]>([]);

  const dismiss = useCallback((id: number) => {
    setItems((prev) => prev.filter((i) => i.id !== id));
  }, []);

  const show = useCallback((msg: string, ttlMs = 4_000) => {
    const id = Date.now() + Math.random();
    setItems((prev) => [...prev, { id, msg, intent: "danger" }]);
    setTimeout(() => dismiss(id), ttlMs);
  }, [dismiss]);

  const showInfo = useCallback((msg: string, ttlMs = 5_000) => {
    const id = Date.now() + Math.random();
    setItems((prev) => [...prev, { id, msg, intent: "neutral" }]);
    setTimeout(() => dismiss(id), ttlMs);
  }, [dismiss]);

  const showWithAction = useCallback(
    (opts: { msg: string; action: ToastAction; ttlMs?: number; intent?: "neutral" | "danger" }) => {
      const id = Date.now() + Math.random();
      setItems((prev) => [...prev, { id, msg: opts.msg, action: opts.action, intent: opts.intent ?? "neutral" }]);
      setTimeout(() => dismiss(id), opts.ttlMs ?? 5_000);
    },
    [dismiss],
  );

  useEffect(() => {
    const onReplayBlocked = (event: Event) => {
      const detail = (event as CustomEvent<ReplayBlockedDetail>).detail;
      if (detail?.message) showInfo(detail.message);
    };

    window.addEventListener(REPLAY_BLOCKED_EVENT, onReplayBlocked);
    return () => {
      window.removeEventListener(REPLAY_BLOCKED_EVENT, onReplayBlocked);
      setItems([]);
    };
  }, [showInfo]);

  return (
    <Ctx.Provider value={{ show, showInfo, showWithAction }}>
      {children}
      <div className="fixed top-3 right-3 z-50 space-y-2 pointer-events-none">
        {items.map((i) => (
          <div
            key={i.id}
            role="status"
            className={`pointer-events-auto text-xs px-3 py-2 rounded shadow flex items-center gap-3 ${
              i.intent === "danger"
                ? "bg-red-600 text-white dark:bg-red-700"
                : "bg-slate-900 text-white dark:bg-slate-800 dark:border dark:border-slate-700"
            }`}
          >
            <span>{i.msg}</span>
            {i.action && (
              <button
                type="button"
                onClick={() => {
                  i.action!.onAction();
                  dismiss(i.id);
                }}
                className="ml-1 px-2 py-0.5 rounded bg-white/15 hover:bg-white/25 font-medium uppercase tracking-wide text-[10px]"
              >{i.action.label}</button>
            )}
          </div>
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

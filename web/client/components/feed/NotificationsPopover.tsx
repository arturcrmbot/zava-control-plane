import { useState, useRef, useEffect, useMemo } from "react";
import { Bell } from "lucide-react";
import type { FeedItem } from "@shared/feedItems";
import { useNotificationState } from "@client/hooks/useNotificationState";

export default function NotificationsPopover({
  roleId, items, onJumpTo,
}: {
  roleId: string;
  items: FeedItem[];
  onJumpTo: (itemId: string) => void;
}) {
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement | null>(null);
  const { unread, markSeen, clearAll } = useNotificationState(roleId);

  useEffect(() => {
    const onDoc = (e: MouseEvent) => {
      if (!ref.current?.contains(e.target as Node)) setOpen(false);
    };
    document.addEventListener("mousedown", onDoc);
    return () => document.removeEventListener("mousedown", onDoc);
  }, []);

  // Re-derive on every render so SSE-driven changes to `items` flow through.
  const unreadItems = useMemo(() => unread(items), [unread, items]);
  const count = unreadItems.length;

  return (
    <div ref={ref} className="relative">
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        aria-label={`${count} unread`}
        className="relative text-slate-500 dark:text-slate-400 hover:text-slate-800 px-1"
      >
        <Bell size={16} />
        {count > 0 && (
          <span className="absolute -top-1 -right-1 bg-red-500 text-white text-[10px] rounded-full px-1 min-w-[16px] text-center">
            {count}
          </span>
        )}
      </button>
      {open && (
        <div className="absolute right-0 top-full mt-1 bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-700 rounded-md shadow-lg w-80 max-h-96 overflow-auto py-1 z-50">
          <div className="flex items-center justify-between px-3 py-1.5 border-b border-slate-100 dark:border-slate-800 sticky top-0 bg-white dark:bg-slate-900">
            <span className="text-[11px] uppercase tracking-wide text-slate-500 dark:text-slate-400">
              Notifications {count > 0 && <span className="text-slate-700 dark:text-slate-200">({count})</span>}
            </span>
            <button
              type="button"
              onClick={() => { clearAll(); setOpen(false); }}
              disabled={count === 0}
              className="text-[11px] text-blue-600 hover:underline disabled:text-slate-400 disabled:no-underline disabled:cursor-default dark:text-blue-400 dark:disabled:text-slate-600"
            >
              Clear all
            </button>
          </div>
          {count === 0 && (
            <div className="text-xs text-slate-500 dark:text-slate-400 px-3 py-4 italic text-center">
              You're all caught up ✓
            </div>
          )}
          {unreadItems.map((it) => (
            <button
              key={it.id}
              type="button"
              onClick={() => {
                markSeen(it.id);
                onJumpTo(it.id);
                setOpen(false);
              }}
              className="w-full text-left text-xs px-3 py-2 hover:bg-slate-50 dark:hover:bg-slate-800 border-b border-slate-100 dark:border-slate-800 last:border-b-0"
            >
              <div className="font-mono text-slate-700 dark:text-slate-200">{it.workflowId ?? it.id}</div>
              <div className="text-[11px] text-slate-500 dark:text-slate-400">{it.type} · {it.severity ?? "-"}</div>
            </button>
          ))}
        </div>
      )}
    </div>
  );
}

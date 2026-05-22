import { useEffect, useState } from "react";

export default function MemoryTiles() {
  const [count, setCount] = useState<number | null>(null);

  useEffect(() => {
    let cancelled = false;
    async function refresh() {
      try {
        const r = await fetch("/api/memory/v2/memories?domain=hiring");
        if (!r.ok) return;
        const body = await r.json();
        if (cancelled) return;
        setCount(body.count || 0);
      } catch {
        /* tolerated */
      }
    }
    void refresh();
    const iv = window.setInterval(() => {
      void refresh();
    }, 30_000);
    return () => {
      cancelled = true;
      window.clearInterval(iv);
    };
  }, []);

  // Hide entirely until we know we have memories — a zero tile on
  // the dashboard is just noise. The /memory page still surfaces
  // the same number contextually.
  if (count == null || count === 0) return null;

  return (
    <div className="grid grid-cols-2 md:grid-cols-3 gap-3">
      <div className="bg-white border border-slate-200 rounded-lg p-4 dark:bg-slate-900 dark:border-slate-700">
        <div className="text-[11px] uppercase tracking-wide text-slate-500 dark:text-slate-400">Memories</div>
        <div className="text-2xl font-semibold text-slate-900 dark:text-slate-100 tabular-nums">{count}</div>
        <div className="text-xs text-slate-500 dark:text-slate-400 mt-0.5">in hiring</div>
      </div>
    </div>
  );
}

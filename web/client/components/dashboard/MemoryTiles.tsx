import { useEffect, useState } from "react";


export default function MemoryTiles() {
  const [active, setActive] = useState<number>(0);

  useEffect(() => {
    let cancelled = false;
    async function refresh() {
      try {
        const r = await fetch("/api/memory/lessons/active");
        if (!r.ok) return;
        const body = await r.json();
        if (cancelled) return;
        setActive((body.items || []).length);
      } catch {
        /* tolerated */
      }
    }
    refresh();
    const iv = window.setInterval(refresh, 30_000);
    return () => {
      cancelled = true;
      window.clearInterval(iv);
    };
  }, []);

  return (
    <div className="grid grid-cols-2 md:grid-cols-3 gap-3">
      <div className="bg-white border border-slate-200 rounded-lg p-4 dark:bg-slate-900 dark:border-slate-700">
        <div className="text-[11px] uppercase tracking-wide text-slate-500 dark:text-slate-400">Lessons active</div>
        <div className="text-2xl font-semibold text-slate-900 dark:text-slate-100 tabular-nums">{active}</div>
        <div className="text-xs text-slate-500 dark:text-slate-400 mt-0.5">across all domains</div>
      </div>
    </div>
  );
}

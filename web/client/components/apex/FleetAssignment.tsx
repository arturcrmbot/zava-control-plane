// web/client/components/apex/FleetAssignment.tsx
import type { OtelSpan } from "@shared/types";

export default function FleetAssignment({ spans }: { spans: OtelSpan[] }) {
  const byExecutor = new Map<string, { type: string; status: "ok" | "error"; count: number }>();
  for (const s of spans) {
    const name = String(s.attributes["executor.name"] ?? s.name);
    const type = String(s.attributes["executor.type"] ?? "unknown");
    const cur = byExecutor.get(name) ?? { type, status: "ok" as const, count: 0 };
    cur.count += 1;
    if (s.status === "error") cur.status = "error";
    byExecutor.set(name, cur);
  }
  const rows = [...byExecutor.entries()];
  return (
    <div className="panel" data-testid="fleet-assignment">
      <div className="panel-header">Fleet Assignment</div>
      <div className="panel-body space-y-1.5">
        {rows.length === 0 && <div className="text-xs text-slate-500">no executors fired yet</div>}
        {rows.map(([name, info]) => (
          <div key={name} className="flex items-center gap-2 text-sm min-w-0">
            <span className={`shrink-0 w-2 h-2 rounded-full ${info.status === "error" ? "bg-red-500" : "bg-emerald-500"}`} />
            <span className="text-slate-800 truncate flex-1 min-w-0" title={name}>{name}</span>
            <span className="shrink-0 text-[10px] text-slate-500 uppercase tracking-wide">{info.type.slice(0, 3)}</span>
            <span className="shrink-0 text-[11px] text-slate-500 tabular-nums">×{info.count}</span>
          </div>
        ))}
      </div>
    </div>
  );
}

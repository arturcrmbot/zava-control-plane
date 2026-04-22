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
          <div key={name} className="flex items-center justify-between text-sm">
            <span className="flex items-center gap-2">
              <span className={`w-2 h-2 rounded-full ${info.status === "error" ? "bg-red-500" : "bg-emerald-500"}`} />
              <span className="text-slate-800">{name}</span>
              <span className="text-[10px] text-slate-500 uppercase">{info.type}</span>
            </span>
            <span className="text-[11px] text-slate-500">{info.count} call{info.count === 1 ? "" : "s"}</span>
          </div>
        ))}
      </div>
    </div>
  );
}

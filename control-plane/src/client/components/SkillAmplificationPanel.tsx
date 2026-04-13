// src/client/components/SkillAmplificationPanel.tsx
import type { SkillAmplification } from "@shared/types";

export default function SkillAmplificationPanel({ items }: { items: SkillAmplification[] }) {
  if (items.length === 0) return <div className="text-xs text-slate-500">No skill amplification for this workflow yet.</div>;
  return (
    <div className="space-y-2">
      {items.map(a => (
        <div key={a.id} className="border border-slate-800 rounded p-2 bg-slate-900/30 text-xs">
          <div className="text-emerald-300 font-medium">→ {a.recommendedApproach}</div>
          {a.policyContext.map((p, i) => (
            <div key={i} className="mt-1">
              <div className="font-medium text-slate-200">{p.title}</div>
              <div className="text-slate-400">{p.snippet}</div>
            </div>
          ))}
          {a.precedents.length > 0 && (
            <div className="mt-1">
              <div className="text-[10px] uppercase text-slate-500">Precedents</div>
              {a.precedents.map((p, i) => (
                <div key={i} className="text-slate-400">· {p.workflowId} → {p.outcome}: {p.rationale}</div>
              ))}
            </div>
          )}
        </div>
      ))}
    </div>
  );
}

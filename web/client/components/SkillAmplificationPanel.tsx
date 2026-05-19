// src/client/components/SkillAmplificationPanel.tsx
import type { SkillAmplification } from "@shared/types";

export default function SkillAmplificationPanel({ items }: { items: SkillAmplification[] }) {
  if (items.length === 0) return <div className="text-xs text-slate-500 dark:text-slate-400">No skill amplification for this workflow yet.</div>;
  return (
    <div className="space-y-2">
      {items.map(a => (
        <div key={a.id} className="panel panel-body text-xs space-y-2">
          <div className="text-emerald-700 dark:text-emerald-400 font-medium">→ {a.recommendedApproach}</div>
          {a.policyContext.map((p, i) => (
            <div key={i}>
              <div className="font-medium text-slate-800 dark:text-slate-100">{p.title}</div>
              <div className="text-slate-500 dark:text-slate-400">{p.snippet}</div>
            </div>
          ))}
          {a.precedents.length > 0 && (
            <div>
              <div className="text-[10px] uppercase tracking-wide text-slate-500 dark:text-slate-400">Precedents</div>
              {a.precedents.map((p, i) => (
                <div key={i} className="text-slate-600 dark:text-slate-300">· {p.workflowId} → {p.outcome}: {p.rationale}</div>
              ))}
            </div>
          )}
        </div>
      ))}
    </div>
  );
}

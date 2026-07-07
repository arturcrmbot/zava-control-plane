import { useState } from "react";

export function BriefReviewPanel({
  brief, onDecision,
}: {
  brief: { request_id: string; yaml: string };
  onDecision: (request_id: string, approved: boolean, yaml: string) => void;
}) {
  const [yaml, setYaml] = useState(brief.yaml);
  return (
    <div className="rounded-xl border border-sky-500/50 bg-slate-900 p-5 shadow-xl" role="dialog" aria-label="Brief review">
      <p className="text-sm text-sky-300">Here's what I understood — edit anything, then approve.</p>
      <textarea className="mt-2 h-64 w-full rounded-md bg-slate-950 p-3 font-mono text-xs text-slate-100"
        value={yaml} onChange={(e) => setYaml(e.target.value)} aria-label="Brief YAML" />
      <div className="mt-3 flex justify-end gap-2">
        <button className="rounded-md border border-slate-600 px-3 py-1.5 text-sm hover:bg-slate-800"
          onClick={() => onDecision(brief.request_id, false, yaml)}>Revise</button>
        <button className="rounded-md bg-emerald-600 px-3 py-1.5 text-sm font-medium"
          onClick={() => onDecision(brief.request_id, true, yaml)}>Approve &amp; compose</button>
      </div>
    </div>
  );
}

// web/client/components/apex/ExceptionAnalysisCard.tsx
import type { Narrative } from "@shared/types";

function highlight(text: string): React.ReactNode {
  // Highlight money amounts, GL codes, PO numbers, all-caps IDs.
  const parts = text.split(/(\b[A-Z]{2,}-[A-Z0-9-]+|\$?\d[\d,]*\.?\d*|\bGL-\d+)/);
  return parts.map((p, i) => (
    /^([A-Z]{2,}-[A-Z0-9-]+|\$?\d[\d,]*\.?\d*|GL-\d+)$/.test(p)
      ? <span key={i} className="bg-amber-100 text-amber-900 rounded px-1">{p}</span>
      : <span key={i}>{p}</span>
  ));
}

export default function ExceptionAnalysisCard({ narrative }: { narrative: Narrative }) {
  return (
    <div className="panel" data-testid="exception-analysis">
      <div className="panel-header flex items-center gap-2">
        <span className="text-red-600">⚠</span>
        <span>Exception Analysis</span>
      </div>
      <div className="panel-body space-y-4 text-sm">
        <div>
          <div className="text-[10px] uppercase tracking-wide text-slate-500 mb-1">What Happened</div>
          <p className="text-slate-800">{highlight(narrative.whatHappened)}</p>
        </div>
        <div>
          <div className="text-[10px] uppercase tracking-wide text-slate-500 mb-1">What the Agent Tried</div>
          <ul className="list-disc pl-5 space-y-1 text-slate-700">
            {narrative.whatAgentTried.map((b, i) => <li key={i}>{b}</li>)}
          </ul>
        </div>
        <div className="bg-emerald-50 border border-emerald-200 rounded p-3">
          <div className="text-[10px] uppercase tracking-wide text-emerald-700 mb-1">Agent Recommendation</div>
          <p className="text-emerald-900">{narrative.agentRecommendation}</p>
        </div>
      </div>
    </div>
  );
}

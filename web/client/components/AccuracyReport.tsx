import { useEffect, useState } from "react";

type CMRow = { green: number; amber: number; red: number };
type Report = {
  run_id: string;
  n: number;
  overall_accuracy: number;
  per_category: Record<string, { n: number; accuracy: number }>;
  confusion_matrix: { green: CMRow; amber: CMRow; red: CMRow };
  per_claim: Array<{
    claim_id: string;
    gold_label: string;
    predicted_label: string;
    correct: boolean;
    gold_reasoning: string;
    predicted_reasoning: string;
    policy_clause: string;
  }>;
};

export function AccuracyReport() {
  const [report, setReport] = useState<Report | null>(null);
  const [loading, setLoading] = useState(true);
  const [running, setRunning] = useState(false);
  const [progress, setProgress] = useState<{ index: number; total: number } | null>(null);
  const [drillCell, setDrillCell] = useState<{ gold: string; pred: string } | null>(null);

  useEffect(() => {
    fetch("/api/accuracy/last")
      .then((r) => (r.ok ? r.json() : null))
      .then((data) => setReport(data))
      .finally(() => setLoading(false));
  }, []);

  useEffect(() => {
    if (!running) return;
    const sse = new EventSource("/api/stream/fleet");
    sse.addEventListener("message", (ev) => {
      let data: any = {};
      try {
        data = JSON.parse((ev as MessageEvent).data || "{}");
      } catch {
        return;
      }
      if (data.type === "accuracy.progress") {
        setProgress({ index: data.index, total: data.total });
      } else if (data.type === "accuracy.complete") {
        fetch("/api/accuracy/last").then((r) => r.json()).then(setReport);
        setRunning(false);
        setProgress(null);
      }
    });
    return () => sse.close();
  }, [running]);

  async function startRun() {
    setRunning(true);
    await fetch("/api/accuracy/run", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({}),
    });
  }

  if (loading) return <div className="p-4">Loading…</div>;
  const labels = ["green", "amber", "red"] as const;
  const drillRows =
    drillCell && report
      ? report.per_claim.filter(
          (c) => c.gold_label === drillCell.gold && c.predicted_label === drillCell.pred,
        )
      : [];

  return (
    <div className="space-y-3">
      <div>
        <div className="text-lg font-semibold text-slate-900">R/A/G Classifier Accuracy</div>
        <div className="text-xs text-slate-500 mt-0.5">
          {report ? `${report.n} claims · run ${report.run_id}` : "no run yet"}
        </div>
      </div>
      <div className="flex items-center gap-3">
        <button
          className="px-3 py-1.5 rounded bg-blue-600 text-white text-sm disabled:opacity-50"
          onClick={startRun}
          disabled={running}
        >
          {running ? "Running…" : "Run accuracy harness"}
        </button>
        {progress && (
          <span className="text-xs text-slate-500">
            {progress.index + 1} / {progress.total}
          </span>
        )}
      </div>

      {!report ? (
        <div className="panel panel-body text-xs text-slate-500 italic">No completed run yet.</div>
      ) : (
        <>
          <div className="panel panel-body">
            <div className="text-[11px] uppercase tracking-wide text-slate-500">Overall accuracy</div>
            <div className="text-3xl font-semibold text-slate-900 mt-1">
              {(report.overall_accuracy * 100).toFixed(1)}%
            </div>
          </div>

          <div className="panel">
            <div className="panel-header">Confusion matrix</div>
            <table className="w-full text-xs border-collapse">
              <thead>
                <tr>
                  <th></th>
                  {labels.map((l) => (
                    <th key={l} className="px-3 py-1 capitalize text-slate-500 font-normal">
                      predicted {l}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {labels.map((row) => (
                  <tr key={row}>
                    <th className="px-3 py-1 text-right capitalize text-slate-500 font-normal">
                      gold {row}
                    </th>
                    {labels.map((col) => {
                      const v = report.confusion_matrix[row][col];
                      const isDiagonal = row === col;
                      return (
                        <td
                          key={col}
                          className={`px-3 py-1 text-center cursor-pointer font-mono ${
                            isDiagonal ? "bg-emerald-50" : v > 0 ? "bg-rose-50" : ""
                          }`}
                          onClick={() => setDrillCell({ gold: row, pred: col })}
                        >
                          {v}
                        </td>
                      );
                    })}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          <div className="panel panel-body text-xs flex flex-wrap gap-x-4 gap-y-1">
            {Object.entries(report.per_category).map(([cat, s]) => (
              <span key={cat}>
                <span className="capitalize font-medium text-slate-800">{cat}</span>
                <span className="text-slate-500"> · {(s.accuracy * 100).toFixed(1)}% ({s.n})</span>
              </span>
            ))}
          </div>

          {drillCell && (
            <div className="panel panel-body text-xs">
              <div className="flex justify-between items-center">
                <strong>
                  Gold {drillCell.gold} × Predicted {drillCell.pred} ({drillRows.length} claim
                  {drillRows.length === 1 ? "" : "s"})
                </strong>
                <button
                  className="text-slate-500 hover:text-slate-800"
                  onClick={() => setDrillCell(null)}
                  aria-label="close"
                >
                  ×
                </button>
              </div>
              {drillRows.length === 0 && (
                <div className="text-slate-500 mt-2">No claims in this cell.</div>
              )}
              {drillRows.slice(0, 20).map((r) => (
                <div key={r.claim_id} className="mt-2 space-y-0.5">
                  <div className="font-mono text-slate-800">
                    {r.claim_id} — {r.policy_clause}
                  </div>
                  <div className="text-slate-600">Predicted: {r.predicted_reasoning}</div>
                  <div className="text-slate-600">Gold: {r.gold_reasoning}</div>
                </div>
              ))}
            </div>
          )}
        </>
      )}
    </div>
  );
}

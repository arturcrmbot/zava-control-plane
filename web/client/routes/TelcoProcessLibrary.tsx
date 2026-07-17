import { useMemo, useState } from "react";

import type {
  TelcoProcessCase,
  TelcoProcessSummary,
} from "@client/hooks/useWorldSimulation";


export default function TelcoProcessLibrary({
  processes,
  cases,
  onRun,
}: {
  processes: TelcoProcessSummary[];
  cases: TelcoProcessCase[];
  onRun: (workflowType: string) => Promise<void>;
}) {
  const [catalogue, setCatalogue] = useState("all");
  const [maturity, setMaturity] = useState("all");
  const [busy, setBusy] = useState<string | null>(null);
  const casesByWorkflow = useMemo(
    () => new Map(cases.map((item) => [item.workflow_type, item])),
    [cases],
  );
  const filtered = processes.filter((process) => (
    (catalogue === "all" || process.source_id.startsWith(catalogue))
    && (maturity === "all" || process.maturity === maturity)
  ));
  const heroCount = processes.filter((item) => item.maturity === "hero").length;
  const standardCount = processes.length - heroCount;

  async function run(process: TelcoProcessSummary) {
    setBusy(process.workflow_type);
    try {
      await onRun(process.workflow_type);
    } finally {
      setBusy(null);
    }
  }

  return (
    <section data-testid="telco-process-library" className="space-y-3">
      <div className="flex flex-wrap items-center justify-between gap-3 rounded-lg border border-slate-200 bg-white p-3 dark:border-slate-800 dark:bg-slate-900">
        <div>
          <h2 className="text-sm font-semibold">Telco Process Library</h2>
          <p className="text-xs text-slate-500">
            {heroCount} hero · {standardCount} standard
          </p>
        </div>
        <div className="flex gap-2">
          <label className="text-xs text-slate-500">
            Catalogue
            <select
              aria-label="Catalogue"
              value={catalogue}
              onChange={(event) => setCatalogue(event.target.value)}
              className="ml-2 rounded border border-slate-300 bg-white px-2 py-1 dark:border-slate-700 dark:bg-slate-950"
            >
              <option value="all">All</option>
              <option value="OSS">OSS</option>
              <option value="BSS">BSS</option>
            </select>
          </label>
          <label className="text-xs text-slate-500">
            Maturity
            <select
              aria-label="Maturity"
              value={maturity}
              onChange={(event) => setMaturity(event.target.value)}
              className="ml-2 rounded border border-slate-300 bg-white px-2 py-1 dark:border-slate-700 dark:bg-slate-950"
            >
              <option value="all">All</option>
              <option value="hero">Hero</option>
              <option value="standard">Standard</option>
            </select>
          </label>
        </div>
      </div>
      <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
        {filtered.map((process) => {
          const processCase = casesByWorkflow.get(process.workflow_type);
          return (
            <article
              key={process.workflow_type}
              data-testid="telco-process-card"
              className="rounded-lg border border-slate-200 bg-white p-3 dark:border-slate-800 dark:bg-slate-900"
            >
              <div className="flex items-start justify-between gap-2">
                <div>
                  <div className="font-mono text-[11px] text-slate-500">
                    {process.source_id}
                  </div>
                  <h3 className="text-sm font-semibold">{process.display_name}</h3>
                </div>
                <span className="rounded bg-slate-100 px-2 py-0.5 text-[10px] font-semibold uppercase dark:bg-slate-800">
                  {process.maturity}
                </span>
              </div>
              <div className="mt-2 text-xs text-slate-500">
                {process.function} · {process.engine}
              </div>
              {process.skills.length > 0 && (
                <div className="mt-2 text-[11px] text-slate-500">
                  Skills: {process.skills.join(", ")}
                </div>
              )}
              {process.mcp_packs.length > 0 && (
                <div className="mt-1 text-[11px] text-slate-500">
                  MCP: {process.mcp_packs.join(", ")}
                </div>
              )}
              {processCase && (
                <div className="mt-2 rounded bg-slate-50 px-2 py-1 font-mono text-[11px] dark:bg-slate-950">
                  {processCase.id} · {processCase.status}
                </div>
              )}
              {process.maturity === "standard" && (
                <button
                  type="button"
                  disabled={busy !== null}
                  onClick={() => void run(process)}
                  className="mt-3 rounded bg-blue-600 px-2.5 py-1 text-xs font-medium text-white disabled:opacity-50"
                >
                  {busy === process.workflow_type
                    ? "Starting…"
                    : `Run ${process.display_name}`}
                </button>
              )}
            </article>
          );
        })}
      </div>
    </section>
  );
}

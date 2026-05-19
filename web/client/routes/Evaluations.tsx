// src/client/routes/Evaluations.tsx
import { useEffect, useState } from "react";
import { AccuracyReport } from "../components/AccuracyReport";

interface TileBody {
  value: number;
  n_evals: number;
  n_agents: number;
  evaluators: string[];
}

interface Summary {
  configured: boolean;
  reason?: string;
  window_minutes?: number;
  tiles?: { task_adherence: TileBody; safety: TileBody; tool_accuracy: TileBody };
  by_agent?: { agent_label: string; n: number; scores: Record<string, number> }[];
  n_completed?: number;
  n_errored?: number;
  queue?: { pending: number; completed: number; errored: number };
}

interface Row {
  id: string;
  kind: string;
  agent_label: string;
  workflow_id: string | null;
  ts: number;
  status: string;
  scores: Record<string, number | string>;
  foundry_run_url: string | null;
  error_text?: string | null;
}

interface RowsEnvelope {
  configured: boolean;
  reason?: string;
  rows?: Row[];
}

export default function Evaluations() {
  const [summary, setSummary] = useState<Summary | null>(null);
  const [rowsEnv, setRowsEnv] = useState<RowsEnvelope | null>(null);

  useEffect(() => {
    const tick = async () => {
      try {
        const [s, r] = await Promise.all([
          fetch("/api/evals/summary").then(x => x.json()),
          fetch("/api/evals/").then(x => x.json()),
        ]);
        setSummary(s);
        setRowsEnv(r);
      } catch {
        // network blip — leave previous state.
      }
    };
    void tick();
    const i = setInterval(tick, 5000);
    return () => clearInterval(i);
  }, []);

  if (summary && summary.configured === false) {
    return (
      <div className="space-y-4">
        <div>
          <div className="text-lg font-semibold text-slate-900 dark:text-slate-100">Continuous Evaluation</div>
        </div>
        <div className="panel panel-body">
          <div className="text-sm font-semibold text-slate-900 dark:text-slate-100 mb-1">Foundry evaluation is not configured.</div>
          <div className="text-xs text-slate-600 dark:text-slate-300">
            Set <code className="text-xs">AZURE_FOUNDRY_PROJECT_ENDPOINT</code> and{" "}
            <code className="text-xs">AZURE_FOUNDRY_JUDGE_MODEL_DEPLOYMENT</code> to enable.
          </div>
          {summary.reason ? <div className="text-xs text-slate-500 dark:text-slate-400 mt-2">{summary.reason}</div> : null}
        </div>
        <AccuracyReport />
      </div>
    );
  }

  const tiles = summary?.tiles;
  const byAgent = summary?.by_agent ?? [];
  // Keep only primary score keys; drop SDK metadata noise like
  // `*_prompt_tokens`, `*_completion_tokens`, `*_threshold`,
  // `*_total_tokens`, `gpt_*`, and `*_finish_reason`.
  const _META_SUFFIXES = ["_prompt_tokens", "_completion_tokens", "_total_tokens",
                          "_threshold", "_finish_reason", "_model", "_sample_input",
                          "_sample_output", "_pass", "_result"];
  const _isMetaKey = (k: string) =>
    k.startsWith("gpt_") || _META_SUFFIXES.some(s => k.endsWith(s));
  const rows = rowsEnv?.rows ?? [];

  // POC2 hiring agents — added 2026-05-05 per
  // plan/feature-foundry-credibility-friday-1.md TASK-021. The split lets
  // each table show only its domain-relevant evaluator columns instead of
  // a sparse union table.
  const _HIRING_AGENTS = new Set([
    "cv-crystalliser", "auto-shortlister", "jurisdiction-router",
    "betrvg-checker", "voice-screener", "interview-recommender",
    "offer-personaliser",
  ]);
  const hiringAgents = byAgent.filter(a => _HIRING_AGENTS.has(a.agent_label));
  const financeAgents = byAgent.filter(a => !_HIRING_AGENTS.has(a.agent_label));
  const _evalNamesFor = (group: typeof byAgent) => Array.from(
    new Set(group.flatMap(a => Object.keys(a.scores).filter(k => !_isMetaKey(k))))
  ).sort();

  const _primaryScores = (s: Record<string, number | string>) =>
    Object.entries(s)
      .filter(([k, v]) => typeof v === "number" && !_isMetaKey(k))
      .slice(0, 3);

  return (
    <div className="space-y-4">
      <div>
        <div className="text-lg font-semibold text-slate-900 dark:text-slate-100">Continuous Evaluation</div>
        <div className="text-xs text-slate-500 dark:text-slate-400 mt-0.5">
          {summary
            ? `${summary.n_completed ?? 0} evals scored · ${summary.n_errored ?? 0} errored · last ${summary.window_minutes ?? 60}min`
            : "loading…"}
        </div>
      </div>

      <div className="grid grid-cols-3 gap-3">
        <Tile label="Task adherence" tile={tiles?.task_adherence} />
        <Tile label="Safety" tile={tiles?.safety} />
        <Tile label="Tool accuracy" tile={tiles?.tool_accuracy} />
      </div>

      {byAgent.length > 0 ? (
        <div className="space-y-3">
          {financeAgents.length > 0 ? (
            <ByAgentTable label="Finance (POC1)" agents={financeAgents}
                          evalNames={_evalNamesFor(financeAgents)} />
          ) : null}
          {hiringAgents.length > 0 ? (
            <ByAgentTable label="Hiring (POC2)" agents={hiringAgents}
                          evalNames={_evalNamesFor(hiringAgents)} />
          ) : null}
        </div>
      ) : null}

      <div className="panel">
        <div className="panel-header">Recent runs</div>
        <div className="divide-y divide-slate-200 dark:divide-slate-700">
          {rows.length === 0 ? (
            <div className="p-3 text-xs text-slate-500 dark:text-slate-400 italic">No evaluations yet.</div>
          ) : null}
          {rows.slice(0, 20).map(r => (
            <div key={r.id} className="flex items-center gap-3 px-3 py-2 text-xs min-w-0">
              <a href={`/workflows/${r.workflow_id ?? ""}`}
                 className="text-blue-700 dark:text-blue-300 hover:underline font-mono shrink-0">
                {r.agent_label}
              </a>
              <span className="text-slate-400 dark:text-slate-500 shrink-0">{new Date(r.ts * 1000).toLocaleTimeString()}</span>
              <StatusBadge status={r.status} />
              <span className="ml-auto text-slate-600 dark:text-slate-300 font-mono truncate min-w-0 max-w-[60%] text-right">
                {r.status === "completed"
                  ? _primaryScores(r.scores).map(([k, v]) => `${k}=${(v as number).toFixed(2)}`).join(" · ")
                  : r.status === "error"
                    ? <span className="text-rose-600" title={r.error_text || "error"}>{(r.error_text || "error").slice(0, 80)}{((r.error_text || "").length > 80) ? "…" : ""}</span>
                    : <span className="text-slate-400 dark:text-slate-500 italic">scoring…</span>}
              </span>
              {r.foundry_run_url ? (
                <a className="text-blue-700 dark:text-blue-300 hover:underline shrink-0" href={r.foundry_run_url} target="_blank" rel="noreferrer">
                  portal →
                </a>
              ) : null}
            </div>
          ))}
        </div>
      </div>

      <AccuracyReport />
    </div>
  );
}

function StatusBadge({ status }: { status: string }) {
  const cls = status === "completed" ? "bg-emerald-100 text-emerald-800"
            : status === "error"     ? "bg-rose-100 text-rose-800"
            : status === "pending"   ? "bg-amber-100 text-amber-800"
            :                          "bg-slate-100 dark:bg-slate-800 text-slate-700 dark:text-slate-200";
  return <span className={`text-[10px] px-1.5 py-0.5 rounded ${cls}`}>{status}</span>;
}

function ByAgentTable({
  label, agents, evalNames,
}: {
  label: string;
  agents: { agent_label: string; n: number; scores: Record<string, number> }[];
  evalNames: string[];
}) {
  return (
    <div className="panel">
      <div className="panel-header">{label} \u2014 by agent</div>
      <table className="text-xs w-full">
        <thead>
          <tr className="text-slate-500 dark:text-slate-400">
            <th className="text-left px-3 py-2">agent</th>
            <th className="text-right px-3 py-2">n</th>
            {evalNames.map(n => (
              <th key={n} className="text-right px-3 py-2">{n}</th>
            ))}
          </tr>
        </thead>
        <tbody className="divide-y divide-slate-200 dark:divide-slate-700">
          {agents.map(a => (
            <tr key={a.agent_label}>
              <td className="px-3 py-2 font-mono">{a.agent_label}</td>
              <td className="px-3 py-2 text-right">{a.n}</td>
              {evalNames.map(n => {
                const v = a.scores[n];
                return (
                  <td key={n} className="px-3 py-2 text-right">
                    {typeof v === "number" ? v.toFixed(2) : "—"}
                  </td>
                );
              })}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function Tile({ label, tile }: { label: string; tile?: TileBody }) {
  const value = tile?.value ?? 0;
  return (
    <div className="panel panel-body">
      <div className="text-[11px] uppercase tracking-wide text-slate-500 dark:text-slate-400">{label}</div>
      <div className="text-2xl font-semibold text-slate-900 dark:text-slate-100 mt-1">
        {tile?.n_evals === 0 ? "—" : `${(value * 100).toFixed(1)}%`}
      </div>
      <div className="text-[10px] text-slate-500 dark:text-slate-400 mt-1">
        {tile ? `${tile.n_evals} evals · ${tile.n_agents} agents` : ""}
      </div>
    </div>
  );
}

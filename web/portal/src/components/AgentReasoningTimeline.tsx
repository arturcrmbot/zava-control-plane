// Recruiter-side timeline of every agent run that has happened on this
// candidate, newest-first. Replaces the cv_crystalliser-only panel so the
// recruiter can see the interview_recommender, compliance, etc. reasoning
// the AI did, not just the CV extraction.
import type { AgentReasoning } from "../lib/api";

const AGENT_LABEL: Record<string, string> = {
  cv_crystalliser:        "CV crystalliser",
  interview_recommender:  "Interview recommender",
  hiring_compliance:      "Compliance check",
  hiring_screening:       "Screening verdict",
  voice_screen_judge:     "Voice screening judge",
};

function prettyAgent(label?: string): string {
  if (!label) return "Agent";
  return AGENT_LABEL[label] ?? label;
}

export default function AgentReasoningTimeline({ runs }: { runs: AgentReasoning[] }) {
  if (!runs.length) {
    return (
      <div className="panel">
        <div className="panel-header"><span>Agent reasoning</span></div>
        <div className="panel-body">
          <p className="text-sm text-slate-500 italic">
            No agent has finished yet — this fills in as triage, screening,
            interview-recommender, compliance, etc. complete.
          </p>
        </div>
      </div>
    );
  }
  // Group by agent_label, newest run-per-agent first.
  const byAgent = new Map<string, AgentReasoning[]>();
  for (const r of runs) {
    const key = r.agent_label ?? "unknown";
    if (!byAgent.has(key)) byAgent.set(key, []);
    byAgent.get(key)!.push(r);
  }
  // Sort each agent's runs by timestamp-ish — we don't have a started_at on
  // every entry, so reverse insertion order which is FIFO.
  const groups = Array.from(byAgent.entries()).map(([label, entries]) => ({
    label,
    runs: [...entries].reverse(),
  }));

  return (
    <div className="panel-elevated">
      <div className="panel-header">
        <span>Agent reasoning timeline</span>
        <span className="chip-info">{runs.length} run(s) · {groups.length} agent(s)</span>
      </div>
      <div className="panel-body space-y-4">
        {groups.map((g) => (
          <AgentBlock key={g.label} label={g.label} runs={g.runs} />
        ))}
      </div>
    </div>
  );
}

function AgentBlock({ label, runs }: { label: string; runs: AgentReasoning[] }) {
  const latest = runs[0];
  const earlier = runs.slice(1);
  return (
    <div className="border border-slate-200 rounded-lg bg-white">
      <div className="px-4 py-2.5 flex items-center justify-between border-b border-slate-200 bg-slate-50 rounded-t-lg">
        <span className="font-medium text-slate-800">
          {prettyAgent(label)}
          {runs.length > 1 && (
            <span className="text-xs text-slate-500 ml-2">· {runs.length} runs</span>
          )}
        </span>
        {latest?.latency_ms != null && (
          <span className="chip-info">
            {(latest.latency_ms / 1000).toFixed(1)}s · {latest.tool_calls?.length ?? 0} tool call(s)
          </span>
        )}
      </div>
      <div className="px-4 py-3 space-y-3">
        <RunDetail run={latest} />
        {earlier.length > 0 && (
          <details className="text-xs">
            <summary className="cursor-pointer text-slate-500">
              {earlier.length} earlier run(s)
            </summary>
            <div className="mt-2 space-y-3">
              {earlier.map((r, i) => (
                <div key={i} className="border-l-2 border-slate-200 pl-3">
                  <RunDetail run={r} />
                </div>
              ))}
            </div>
          </details>
        )}
      </div>
    </div>
  );
}

function RunDetail({ run }: { run: AgentReasoning }) {
  const tools = run.tool_calls ?? [];
  return (
    <div className="space-y-2">
      {tools.length > 0 && (
        <div className="space-y-2">
          {tools.map((tc, i) => (
            <details key={i} className="border border-slate-200 rounded bg-slate-50">
              <summary className="cursor-pointer px-3 py-2 text-xs font-medium text-slate-700 flex items-center justify-between">
                <span>
                  <span className="phase-bubble phase-bubble-done !inline-flex !w-5 !h-5 !text-[10px] mr-2">{i + 1}</span>
                  tool · <code className="text-indigo-700">{tc.name}</code>
                </span>
                <span className="text-slate-500">
                  {tc.success === false ? <span className="text-red-600">failed</span> : "ok"}
                  {tc.latency_ms != null && <> · {tc.latency_ms}ms</>}
                </span>
              </summary>
              <div className="px-3 pb-3 space-y-2">
                {tc.args && (
                  <div>
                    <div className="text-[10px] uppercase tracking-wider text-slate-500 mb-1">args</div>
                    <pre className="text-[11px] text-slate-700 bg-white border border-slate-200 rounded p-2 whitespace-pre-wrap break-all">
                      {tc.args}
                    </pre>
                  </div>
                )}
                {tc.result && (
                  <div>
                    <div className="text-[10px] uppercase tracking-wider text-slate-500 mb-1">result</div>
                    <pre className="text-[11px] text-slate-700 bg-white border border-slate-200 rounded p-2 whitespace-pre-wrap break-all max-h-48 overflow-auto">
                      {tc.result.length > 1500 ? tc.result.slice(0, 1500) + "…" : tc.result}
                    </pre>
                  </div>
                )}
              </div>
            </details>
          ))}
        </div>
      )}

      {run.response_text && (
        <details className="border border-slate-200 rounded bg-white">
          <summary className="cursor-pointer px-3 py-2 text-xs font-medium text-slate-700">
            final LLM response
            {run.usage && (
              <span className="text-slate-500 ml-2">
                · in {run.usage.input_tokens ?? "?"} / out {run.usage.output_tokens ?? "?"} tok
              </span>
            )}
          </summary>
          <pre className="px-3 pb-3 text-[11px] text-slate-700 whitespace-pre-wrap break-all max-h-80 overflow-auto">
            {run.response_text}
          </pre>
        </details>
      )}

      {run.extracted_json && Object.keys(run.extracted_json).length > 0 && !run.response_text && (
        <details className="border border-slate-200 rounded bg-white">
          <summary className="cursor-pointer px-3 py-2 text-xs font-medium text-slate-700">
            extracted output
          </summary>
          <pre className="px-3 pb-3 text-[11px] text-slate-700 whitespace-pre-wrap break-all max-h-80 overflow-auto">
            {JSON.stringify(run.extracted_json, null, 2)}
          </pre>
        </details>
      )}

      {!tools.length && !run.response_text && !run.extracted_json && (
        <p className="text-xs text-slate-500 italic">
          (no tool calls, no LLM response captured for this run)
        </p>
      )}
    </div>
  );
}

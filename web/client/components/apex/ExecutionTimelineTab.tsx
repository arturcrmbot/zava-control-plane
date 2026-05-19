// web/client/components/apex/ExecutionTimelineTab.tsx
import { useState } from "react";
import type { McpCall } from "@shared/types";
import { useFleetManagerStream } from "../../hooks/useFleetManagerStream";

function statusChip(code: number) {
  if (code === 0) return <span className="chip-info">PENDING</span>;
  if (code >= 200 && code < 300) return <span className="chip-success">{code}</span>;
  if (code >= 400) return <span className="chip-danger">{code}</span>;
  return <span className="chip-info">{code}</span>;
}

export default function ExecutionTimelineTab({ mcpCalls, workflowId, onLogAction }: {
  mcpCalls: McpCall[];
  workflowId: string;
  onLogAction: (action: string) => void;
}) {
  const [selected, setSelected] = useState<number | null>(
    mcpCalls.length > 0 ? 0 : null,
  );
  const fmEvents = useFleetManagerStream();
  const sel = selected != null ? mcpCalls[selected] : null;

  return (
    <div className="grid grid-cols-3 gap-4" data-testid="execution-timeline">
      <div className="col-span-2 space-y-2">
        <div className="flex items-center justify-between">
          <div className="text-sm text-slate-600 dark:text-slate-300">Run ID: <span className="font-mono">{workflowId}</span></div>
          <div className="flex gap-2">
            <button className="btn-secondary" data-testid="rollback-workflow"
                    onClick={() => onLogAction("workflow.rollback-requested")}>
              Rollback
            </button>
            <button className="btn-secondary" data-testid="fork-workflow"
                    onClick={() => onLogAction("workflow.fork-requested")}>
              Fork Workflow
            </button>
          </div>
        </div>
        {mcpCalls.length === 0 && (
          <div className="panel panel-body text-xs text-slate-500 dark:text-slate-400">
            Timeline populates as the orchestration fires MCP calls.
          </div>
        )}
        {mcpCalls.map((c, i) => {
          const failed = c.statusCode >= 400;
          return (
            <button key={i}
                    onClick={() => setSelected(i)}
                    data-testid={`timeline-step-${i}`}
                    className={`panel w-full text-left panel-body
                      ${i === selected ? "ring-2 ring-blue-400" : ""}
                      ${failed ? "border-red-300" : ""}`}>
              <div className="flex items-center gap-3">
                <span className="text-[10px] font-mono text-slate-500 dark:text-slate-400">STEP {String(i + 1).padStart(2, "0")}</span>
                <span className="text-sm font-semibold text-slate-800 dark:text-slate-100">{c.method} {new URL(c.url).pathname}</span>
                <span className="ml-auto">{statusChip(c.statusCode)}</span>
              </div>
              <div className="text-[11px] text-slate-500 dark:text-slate-400 mt-1">
                tool: {c.tool} · {c.durationMs} ms · {new Date(c.timestamp * 1000).toLocaleTimeString()}
              </div>
              {failed && (
                <div className="flex gap-2 mt-2">
                  <button onClick={e => { e.stopPropagation(); onLogAction(`step.${i}.fork`); }}
                          className="btn-secondary text-xs">Fork Step &amp; Re-run</button>
                  <button onClick={e => { e.stopPropagation(); onLogAction(`step.${i}.rollback`); }}
                          className="btn-secondary text-xs">Rollback to here</button>
                </div>
              )}
            </button>
          );
        })}
      </div>

      <div className="col-span-1 space-y-3">
        <div className="panel" data-testid="api-configuration">
          <div className="panel-header">API Configuration</div>
          <div className="panel-body">
            {!sel && <div className="text-xs text-slate-500 dark:text-slate-400">select a step</div>}
            {sel && (
              <>
                <div className="text-[11px] uppercase text-slate-500 dark:text-slate-400 mb-1">Request</div>
                <pre className="text-[11px] bg-slate-50 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded p-2 whitespace-pre-wrap break-all max-h-48 overflow-auto">
{JSON.stringify(sel.request, null, 2)}
                </pre>
                <div className="text-[11px] uppercase text-slate-500 dark:text-slate-400 mb-1 mt-2">Response</div>
                <pre className="text-[11px] bg-slate-50 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded p-2 whitespace-pre-wrap break-all max-h-48 overflow-auto">
{JSON.stringify(sel.response, null, 2)}
                </pre>
              </>
            )}
          </div>
        </div>

        <div className="panel" data-testid="agent-thought-stream">
          <div className="panel-header">Agent Thought Stream</div>
          <div className="panel-body space-y-1.5">
            {fmEvents.length === 0 && <div className="text-xs text-slate-500 dark:text-slate-400">no agent activity</div>}
            {fmEvents.slice(-6).map((e, i) => (
              <div key={i} className="text-xs">
                <div className="text-slate-800 dark:text-slate-100 font-medium">{e.kind}</div>
                <div className="text-slate-500 dark:text-slate-400 break-all">
                  {e.data ? JSON.stringify(e.data).slice(0, 140) : ""}
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}

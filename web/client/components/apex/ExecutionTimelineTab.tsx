import { useState, type ComponentType, type ReactNode } from "react";
import {
  Activity,
  Bot,
  ChevronDown,
  CircleAlert,
  GitBranch,
  Layers3,
  ShieldCheck,
  UserRound,
  Wrench,
} from "lucide-react";
import type { ExecutionTimelineRow, McpCall } from "@shared/types";

type DisplayKind =
  | "Lifecycle"
  | "Phase"
  | "Agent"
  | "Tool"
  | "Decision"
  | "Child workflow"
  | "Error"
  | "System";

const KIND_ICONS: Record<DisplayKind, ComponentType<{ className?: string; "aria-hidden"?: boolean }>> = {
  Lifecycle: Activity,
  Phase: Layers3,
  Agent: Bot,
  Tool: Wrench,
  Decision: ShieldCheck,
  "Child workflow": GitBranch,
  Error: CircleAlert,
  System: Activity,
};

function humanize(value: string): string {
  const words = value
    .replace(/([a-z0-9])([A-Z])/g, "$1 $2")
    .replace(/[._-]+/g, " ")
    .trim()
    .toLowerCase();
  return words ? `${words[0].toUpperCase()}${words.slice(1)}` : "Activity";
}

function hasLedgerEvidence(row: ExecutionTimelineRow): boolean {
  return row.id.startsWith("ledger:") || row.ledger != null;
}

function hasAgentDiagnostics(row: ExecutionTimelineRow): boolean {
  return ["agent", "reasoning", "agentOutput"].includes(row.kind);
}

function displayKind(row: ExecutionTimelineRow): DisplayKind {
  if (row.childWorkflowId || row.label === "workflow.sub_spawned") return "Child workflow";
  if (row.kind === "phase") return "Phase";
  if (row.kind === "tool") return "Tool";
  if (row.kind === "output") return "System";
  if (row.kind === "decision") return "Decision";
  if (
    row.kind === "error"
    || row.status === "error"
    || row.status === "failed"
  ) return "Error";
  if (
    row.kind === "workflow"
    || ["workflow.started", "workflow.completed", "workflow.failed", "workflow.rejected"].includes(row.label)
  ) return "Lifecycle";
  if (!hasLedgerEvidence(row) && ["agent", "reasoning", "agentOutput"].includes(row.kind)) return "Agent";
  return "System";
}

function rowLabel(row: ExecutionTimelineRow): string {
  if (row.kind === "workflow" && row.label === "workflow.started") return "Workflow started";
  if (row.childWorkflowId || row.label.includes("sub_spawned")) {
    return `${humanize(row.childWorkflowType ?? "Child")} child workflow started`;
  }
  if (row.label.includes("retry")) return "Retry scheduled";
  if (row.label.includes("rollback")) return "Rollback requested";
  if (row.label.includes("fork")) return "Workflow forked";
  return humanize(row.label);
}

function detailsRecord(row: ExecutionTimelineRow): Record<string, unknown> | null {
  return row.details != null && typeof row.details === "object" && !Array.isArray(row.details)
    ? row.details as Record<string, unknown>
    : null;
}

function summary(row: ExecutionTimelineRow): string | null {
  if (row.reason) return row.reason;
  if (row.resultSummary || row.result_summary) return row.resultSummary ?? row.result_summary ?? null;
  if (row.childWorkflowId) {
    return [row.childWorkflowType, row.childWorkflowId].filter(Boolean).join(" · ");
  }
  const details = detailsRecord(row);
  if (row.kind === "output") {
    const outputReasoning = row.reasoning ?? details?.reasoning;
    if (typeof outputReasoning === "string") return outputReasoning;
    if (
      outputReasoning != null
      && typeof outputReasoning === "object"
      && !Array.isArray(outputReasoning)
      && typeof (outputReasoning as Record<string, unknown>).summary === "string"
    ) {
      return (outputReasoning as Record<string, unknown>).summary as string;
    }
  }
  for (const key of ["summary", "message", "error"]) {
    if (typeof details?.[key] === "string") return details[key] as string;
  }
  if (details?.attempt != null) return `Attempt ${String(details.attempt)}`;
  if (row.kind === "tool") return [row.method, row.url].filter(Boolean).join(" ");
  if (row.kind === "phase" && row.agentId) return `Executor: ${humanize(row.agentId)}`;
  if (row.kind === "workflow" && row.currentPhase) return `Current phase: ${humanize(row.currentPhase)}`;
  if (["agent", "reasoning", "agentOutput"].includes(row.kind)) {
    return [row.phase && humanize(row.phase), row.skill && humanize(row.skill), row.model]
      .filter(Boolean)
      .join(" · ") || null;
  }
  return null;
}

function actor(row: ExecutionTimelineRow): string | null {
  const value = row.personaRole ?? row.actor ?? row.agent ?? row.agentId;
  return value ? humanize(value) : null;
}

function formatDuration(milliseconds?: number | null): string | null {
  if (milliseconds == null || !Number.isFinite(milliseconds)) return null;
  if (milliseconds < 1_000) return `${Math.round(milliseconds)} ms`;
  const seconds = milliseconds / 1_000;
  return `${Number.isInteger(seconds) ? seconds : seconds.toFixed(1)} s`;
}

function formatTimestamp(timestamp: number): string {
  if (!Number.isFinite(timestamp)) return "Unknown time";
  return new Date(timestamp * 1_000).toLocaleString();
}

function statusClass(value: string): string {
  const normalized = value.toLowerCase();
  if (["ok", "completed", "success", "approved", "approve", "green"].includes(normalized)) {
    return "chip-success";
  }
  if (["error", "failed", "rejected", "reject", "red"].includes(normalized)) return "chip-danger";
  if (["pending", "in_progress", "awaiting_hitl", "amber"].includes(normalized)) return "chip-warning";
  return "chip-info";
}

function JsonBlock({ value }: { value: unknown }) {
  return (
    <pre className="text-[11px] bg-slate-50 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded p-2 whitespace-pre-wrap break-all max-h-64 overflow-auto">
      {JSON.stringify(value, null, 2)}
    </pre>
  );
}

function DetailField({ label, children }: { label: string; children: ReactNode }) {
  return (
    <div>
      <dt className="text-[10px] uppercase tracking-wide text-slate-500 dark:text-slate-400">{label}</dt>
      <dd className="mt-0.5 text-xs text-slate-800 dark:text-slate-100 break-all">{children}</dd>
    </div>
  );
}

function TimelineDetails({ row, mcpCall }: {
  row: ExecutionTimelineRow;
  mcpCall?: McpCall;
}) {
  const kind = displayKind(row);
  const showAgentDiagnostics = kind === "Agent" || hasAgentDiagnostics(row);
  const details = detailsRecord(row);
  const evidence = details?.evidence;
  const hasInlineToolEvidence = row.request !== undefined || row.response !== undefined;
  const hasToolEvidence = mcpCall != null || hasInlineToolEvidence;
  const governance = [
    ["Decision ID", row.decisionId],
    ["Policy version", row.policyVersion],
    ["Enforcement mode", row.enforcementMode],
    ["Previous hash", row.prevHash],
    ["Entry hash", row.entryHash],
    ["Actor JWS", row.actorJws],
  ].filter((entry): entry is [string, string] => typeof entry[1] === "string" && entry[1].length > 0);

  return (
    <div className="space-y-3">
      {(showAgentDiagnostics || row.kind === "phase") && (
        <dl className="grid grid-cols-2 gap-x-4 gap-y-2">
          {row.phase && <DetailField label="Phase">{row.phase}</DetailField>}
          {row.model && <DetailField label="Model">{row.model}</DetailField>}
          {row.skill && <DetailField label="Skill">{row.skill}</DetailField>}
          {row.agentId && <DetailField label="Executor">{row.agentId}</DetailField>}
          {row.tokensIn != null && <DetailField label="Input tokens">{row.tokensIn}</DetailField>}
          {row.tokensOut != null && <DetailField label="Output tokens">{row.tokensOut}</DetailField>}
          {row.costUsd != null && <DetailField label="Cost (USD)">{row.costUsd}</DetailField>}
          {row.traceId && <DetailField label="Trace ID">{row.traceId}</DetailField>}
          {row.spanId && <DetailField label="Span ID">{row.spanId}</DetailField>}
        </dl>
      )}

      {kind === "Tool" && (
        <>
          <dl className="grid grid-cols-2 gap-x-4 gap-y-2">
            {(mcpCall?.method ?? row.method) && (
              <DetailField label="Method">{mcpCall?.method ?? row.method}</DetailField>
            )}
            {(mcpCall?.statusCode ?? row.statusCode) != null && (
              <DetailField label="HTTP status">{mcpCall?.statusCode ?? row.statusCode}</DetailField>
            )}
            {(mcpCall?.url ?? row.url) && (
              <DetailField label="URL">{mcpCall?.url ?? row.url}</DetailField>
            )}
          </dl>
          {hasToolEvidence ? (
            <>
              <div>
                <div className="mb-1 text-[10px] uppercase tracking-wide text-slate-500 dark:text-slate-400">Request</div>
                <JsonBlock value={mcpCall?.request ?? row.request ?? null} />
              </div>
              <div>
                <div className="mb-1 text-[10px] uppercase tracking-wide text-slate-500 dark:text-slate-400">Response</div>
                <JsonBlock value={mcpCall?.response ?? row.response ?? null} />
              </div>
            </>
          ) : (
            <div className="text-xs text-slate-500 dark:text-slate-400">
              Tool evidence unavailable.
            </div>
          )}
        </>
      )}

      {showAgentDiagnostics && row.messages && row.messages.length > 0 && (
        <div>
          <div className="mb-1 text-[10px] uppercase tracking-wide text-slate-500 dark:text-slate-400">Persisted messages</div>
          <JsonBlock value={row.messages} />
        </div>
      )}
      {showAgentDiagnostics && row.toolCalls && row.toolCalls.length > 0 && (
        <div>
          <div className="mb-1 text-[10px] uppercase tracking-wide text-slate-500 dark:text-slate-400">Tool calls</div>
          <JsonBlock value={row.toolCalls} />
        </div>
      )}
      {showAgentDiagnostics && row.extractedJson != null && (
        <div>
          <div className="mb-1 text-[10px] uppercase tracking-wide text-slate-500 dark:text-slate-400">Extracted output</div>
          <JsonBlock value={row.extractedJson} />
        </div>
      )}
      {row.kind === "agentOutput" && row.details != null && (
        <div>
          <div className="mb-1 text-[10px] uppercase tracking-wide text-slate-500 dark:text-slate-400">Agent output</div>
          <JsonBlock value={row.details} />
        </div>
      )}
      {showAgentDiagnostics && row.attributes && (
        <div>
          <div className="mb-1 text-[10px] uppercase tracking-wide text-slate-500 dark:text-slate-400">Span attributes</div>
          <JsonBlock value={row.attributes} />
        </div>
      )}

      {kind === "Decision" && (
        <>
          {row.reason && (
            <dl>
              <DetailField label="Reason">{row.reason}</DetailField>
            </dl>
          )}
          {evidence != null && (
            <div>
              <div className="mb-1 text-[10px] uppercase tracking-wide text-slate-500 dark:text-slate-400">Evidence</div>
              <JsonBlock value={evidence} />
            </div>
          )}
        </>
      )}

      {kind === "Child workflow" && (
        <dl className="grid grid-cols-2 gap-x-4 gap-y-2">
          {row.childWorkflowId && <DetailField label="Child workflow ID">{row.childWorkflowId}</DetailField>}
          {row.childWorkflowType && <DetailField label="Child workflow type">{row.childWorkflowType}</DetailField>}
        </dl>
      )}

      {row.kind === "phase" && row.toolCalls && row.toolCalls.length > 0 && (
        <div>
          <div className="mb-1 text-[10px] uppercase tracking-wide text-slate-500 dark:text-slate-400">Tool calls</div>
          <JsonBlock value={row.toolCalls} />
        </div>
      )}
      {row.kind === "phase" && row.spanIds && row.spanIds.length > 0 && (
        <div>
          <div className="mb-1 text-[10px] uppercase tracking-wide text-slate-500 dark:text-slate-400">Span IDs</div>
          <JsonBlock value={row.spanIds} />
        </div>
      )}

      {kind !== "Agent" && kind !== "Tool" && kind !== "Decision" && row.details != null && (
        <div>
          <div className="mb-1 text-[10px] uppercase tracking-wide text-slate-500 dark:text-slate-400">Details</div>
          <JsonBlock value={row.details} />
        </div>
      )}
      {governance.length > 0 && (
        <dl className="grid grid-cols-2 gap-x-4 gap-y-2">
          {governance.map(([label, value]) => <DetailField key={label} label={label}>{value}</DetailField>)}
        </dl>
      )}
      {row.ledger && (
        <div>
          <div className="mb-1 text-[10px] uppercase tracking-wide text-slate-500 dark:text-slate-400">Ledger record</div>
          <JsonBlock value={row.ledger} />
        </div>
      )}
    </div>
  );
}

export default function ExecutionTimelineTab({
  timeline,
  mcpCalls = [],
}: {
  timeline: ExecutionTimelineRow[];
  mcpCalls?: McpCall[];
}) {
  const [expanded, setExpanded] = useState<Set<string>>(() => new Set());

  if (timeline.length === 0) {
    return (
      <div className="panel panel-body text-xs text-slate-600 dark:text-slate-300" data-testid="execution-timeline">
        No execution evidence was captured for this workflow.
      </div>
    );
  }

  const toggle = (id: string) => {
    setExpanded((current) => {
      const next = new Set(current);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  };

  return (
    <div className="space-y-2" data-testid="execution-timeline">
      <div className="text-xs text-slate-500 dark:text-slate-400">
        {timeline.length} evidence row{timeline.length === 1 ? "" : "s"}
      </div>
      <ol className="space-y-2">
        {timeline.map((row) => {
          const kind = displayKind(row);
          const Icon = KIND_ICONS[kind];
          const isExpanded = expanded.has(row.id);
          const detailTestId = `execution-timeline-details-${row.id}`;
          const detailId = detailTestId.replace(/[^A-Za-z0-9_-]/g, "-");
          const status = row.label === "workflow.started"
            ? "started"
            : row.verdict ?? row.status;
          const rowActor = actor(row);
          const rowSummary = summary(row);
          const duration = formatDuration(row.durationMs ?? row.latencyMs);
          const mcpCall = row.toolCallId
            ? mcpCalls.find((call) => call.toolCallId === row.toolCallId)
            : (
              row.mcpCallIndex != null
              && Number.isInteger(row.mcpCallIndex)
              && row.mcpCallIndex >= 0
            )
              ? mcpCalls[row.mcpCallIndex]
              : undefined;

          return (
            <li key={row.id} className="panel overflow-hidden">
              <button
                type="button"
                onClick={() => toggle(row.id)}
                aria-expanded={isExpanded}
                aria-controls={detailId}
                data-testid={`execution-timeline-row-${row.id}`}
                className="w-full p-3 text-left hover:bg-slate-50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-blue-500 dark:hover:bg-slate-800/60"
              >
                <div className="flex items-start gap-3">
                  <span className="mt-0.5 flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-slate-100 text-slate-600 dark:bg-slate-800 dark:text-slate-300">
                    <Icon className="h-3.5 w-3.5" aria-hidden />
                  </span>
                  <span className="min-w-0 flex-1">
                    <span className="flex flex-wrap items-center gap-x-2 gap-y-1">
                      <span className="text-[10px] font-semibold uppercase tracking-wide text-slate-500 dark:text-slate-400">
                        {kind}
                      </span>
                      <span className="text-sm font-semibold text-slate-900 dark:text-slate-100">
                        {rowLabel(row)}
                      </span>
                      {status && <span className={statusClass(status)}>{humanize(status)}</span>}
                    </span>
                    {(rowActor || rowSummary) && (
                      <span className="mt-1 block text-xs text-slate-600 dark:text-slate-300">
                        {rowActor && (
                          <span className="inline-flex items-center gap-1 font-medium">
                            <UserRound className="h-3 w-3" aria-hidden />
                            {rowActor}
                          </span>
                        )}
                        {rowActor && rowSummary && <span aria-hidden> · </span>}
                        {rowSummary}
                      </span>
                    )}
                    <span className="mt-1 block text-[11px] text-slate-500 dark:text-slate-400">
                      {formatTimestamp(row.ts)}
                      {duration && <> · {duration}</>}
                    </span>
                  </span>
                  <ChevronDown
                    className={`mt-1 h-4 w-4 shrink-0 text-slate-400 transition-transform duration-200 ${isExpanded ? "rotate-180" : ""}`}
                    aria-hidden
                  />
                </div>
              </button>
              {isExpanded && (
                <div
                  id={detailId}
                  data-testid={detailTestId}
                  className="border-t border-slate-200 bg-slate-50/60 px-4 py-3 dark:border-slate-700 dark:bg-slate-950/30"
                >
                  <TimelineDetails row={row} mcpCall={mcpCall} />
                </div>
              )}
            </li>
          );
        })}
      </ol>
    </div>
  );
}

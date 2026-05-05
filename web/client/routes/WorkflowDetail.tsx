// web/client/routes/WorkflowDetail.tsx
import { useEffect, useState, useCallback } from "react";
import { useParams } from "react-router-dom";
import type {
  Workflow, Phase, OtelSpan, Exception, SkillAmplification,
  ActionLedgerEntry, McpCall, Economics, Narrative, ClaimData,
} from "@shared/types";
import OtelSpanTree from "../components/OtelSpanTree";
import PhaseTimeline from "../components/PhaseTimeline";
import SkillAmplificationPanel from "../components/SkillAmplificationPanel";
import AgentDrivenComponent, { type AgentComponentSpec } from "../components/AgentDrivenComponent";
import PhaseRibbon from "../components/apex/PhaseRibbon";
import WorkflowHeaderTiles from "../components/apex/WorkflowHeaderTiles";
import ExceptionAnalysisCard from "../components/apex/ExceptionAnalysisCard";
import InterventionProtocols from "../components/apex/InterventionProtocols";
import EconomicsPanel from "../components/apex/EconomicsPanel";
import FleetAssignment from "../components/apex/FleetAssignment";
import AuditTrail from "../components/apex/AuditTrail";
import AuthorityCard from "../components/apex/AuthorityCard";
import ExecutionTimelineTab from "../components/apex/ExecutionTimelineTab";

type DetailResp = {
  workflow: Workflow; phases: Phase[]; spans: OtelSpan[];
  amplifications: SkillAmplification[];
  activeException: Exception | null;
  mcpCalls: McpCall[];
  economics: Economics;
  narrative: Narrative | null;
  auditBlobUrl?: string | null;
};

const TABS = ["Overview", "Phases", "Traces", "Ledger", "Amplification", "Timeline"] as const;

const FLAVOUR_LABEL: Record<string, { text: string; cls: string }> = {
  "correct": { text: "Receipt matches", cls: "bg-emerald-50 text-emerald-700 ring-1 ring-emerald-200" },
  "wrong-amount": { text: "Receipt amount mismatch", cls: "bg-red-50 text-red-700 ring-1 ring-red-200" },
  "wrong-date": { text: "Receipt date mismatch", cls: "bg-amber-50 text-amber-700 ring-1 ring-amber-200" },
  "wrong-vendor": { text: "Receipt vendor mismatch", cls: "bg-amber-50 text-amber-700 ring-1 ring-amber-200" },
  "missing-line-item": { text: "Line item missing on receipt", cls: "bg-amber-50 text-amber-700 ring-1 ring-amber-200" },
  "missing-receipt": { text: "Receipt missing", cls: "bg-red-50 text-red-700 ring-1 ring-red-200" },
};

function ReceiptPanel({ claim }: { claim: ClaimData }) {
  const [errored, setErrored] = useState(false);
  const flavour = claim.receiptMismatchFlavour;
  const annotation = flavour && FLAVOUR_LABEL[flavour];
  const isMissing = errored || flavour === "missing-receipt";
  return (
    <div className="panel">
      <div className="panel-header flex items-center justify-between">
        <span>Receipt · {claim.claimId}</span>
        {annotation && (
          <span className={`text-[10px] uppercase tracking-wide font-medium px-1.5 py-0.5 rounded ${annotation.cls}`}>
            {annotation.text}
          </span>
        )}
      </div>
      <div className="panel-body flex gap-4">
        {isMissing ? (
          <div className="w-32 h-40 bg-amber-50 border-2 border-dashed border-amber-300 rounded flex items-center justify-center text-xs text-amber-700 text-center px-2">
            no receipt<br />submitted
          </div>
        ) : (
          <img
            src={`/api/receipts/${claim.claimId}.png`}
            alt={`receipt ${claim.claimId}`}
            onError={() => setErrored(true)}
            className="w-32 h-40 object-contain bg-white rounded border border-slate-200"
          />
        )}
        <div className="text-xs text-slate-700 space-y-1">
          <div><span className="text-slate-500">Submitted by</span> <span className="font-medium">{claim.employeeId}</span></div>
          <div><span className="text-slate-500">Vendor</span> <span className="font-medium">{claim.vendor}</span></div>
          <div><span className="text-slate-500">Amount</span> <span className="font-semibold text-slate-900">{claim.currency} {claim.amount.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}</span></div>
          <div><span className="text-slate-500">Category</span> <span className="font-medium capitalize">{claim.category}</span></div>
          {claim.attendees > 1 && <div><span className="text-slate-500">Attendees</span> <span className="font-medium">{claim.attendees}</span></div>}
          <div><span className="text-slate-500">Submitted</span> <span className="font-mono text-[11px]">{claim.submittedAt.replace("T", " ").slice(0, 16)}</span></div>
          <div><span className="text-slate-500">Source</span> <span className="font-medium">{claim.emsSource}</span> · <span className="font-medium">{claim.market}</span></div>
        </div>
      </div>
    </div>
  );
}

export default function WorkflowDetail() {
  const { id } = useParams();
  const [d, setD] = useState<DetailResp | null>(null);
  const [tab, setTab] = useState<typeof TABS[number]>("Overview");

  const refresh = useCallback(async () => {
    if (!id) return;
    const r = await fetch(`/api/workflows/${id}`);
    setD(await r.json());
  }, [id]);

  useEffect(() => {
    void refresh();
    const i = setInterval(() => { void refresh(); }, 2500);
    return () => clearInterval(i);
  }, [refresh]);

  const logAction = useCallback(async (action: string) => {
    if (!id) return;
    await fetch("/internal/durable-event", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        workflow_id: id, kind: "log.action",
        payload: { by: "operator", action },
      }),
    }).catch(() => {});
    await refresh();
  }, [id, refresh]);

  if (!d) return <div className="text-sm text-slate-500">loading…</div>;
  const w = d.workflow;
  // POC2 §4.21 AG-UI: pull the cv_crystalliser agent's component_spec off
  // the workflow ledger. Tolerates both camelCase (from the API serialiser)
  // and snake_case (raw JSON from a synthetic fixture loader). Empty list
  // when the agent hasn't run yet.
  const agentOutputs = (w as unknown as { agentOutputs?: Record<string, unknown>; agent_outputs?: Record<string, unknown> }).agentOutputs
    ?? (w as unknown as { agent_outputs?: Record<string, unknown> }).agent_outputs
    ?? {};
  const triageOutput = (agentOutputs["cv_crystalliser"] ?? {}) as { componentSpec?: unknown[]; component_spec?: unknown[] };
  const specs = ((triageOutput.componentSpec ?? triageOutput.component_spec) ?? []) as AgentComponentSpec[];

  return (
    <div className="grid grid-cols-4 gap-4 min-w-0">
      <div className="col-span-3 space-y-4 min-w-0">
        <div>
          <div className="text-xs text-slate-500 flex items-center gap-2">
            <span>{w.id}</span>
            {/*
              Generic "open in domain view" deep-link. Each domain owns its
              own surface; admin shell stays domain-clean. Hiring → recruiter
              candidate page (when we have the candidate id); expense → the
              SSC reviewer queue filtered to this workflow.
            */}
            {(() => {
              const candidateId = (w.metadata as { candidate_id?: string } | undefined)?.candidate_id;
              if (w.type === "hiring" && candidateId) {
                return (
                  <a href={`http://localhost:5174/recruiter/c/${encodeURIComponent(candidateId)}`}
                     target="_blank" rel="noreferrer"
                     className="text-blue-600 hover:underline">
                    open in recruiter view ↗
                  </a>
                );
              }
              if (w.type === "expense-claim") {
                return (
                  <a href={`/reviewer-queue?workflow=${encodeURIComponent(w.id)}`}
                     className="text-blue-600 hover:underline">
                    open in reviewer queue ↗
                  </a>
                );
              }
              return null;
            })()}
          </div>
          {w.claim ? (
            <>
              <div className="text-xl font-semibold text-slate-900">
                {w.id} · {w.claim.employeeId} <span className="text-sm text-slate-500 capitalize">({w.claim.category})</span>
              </div>
              <div className="text-xs text-slate-500">
                {w.claim.currency} {w.claim.amount.toLocaleString()} · {w.claim.market} · {w.claim.emsSource} · {w.agency}
                {w.verdict && <span className={`ml-2 uppercase tracking-wide px-1.5 py-0.5 rounded ${
                  w.verdict === "green" ? "bg-emerald-50 text-emerald-700" :
                  w.verdict === "amber" ? "bg-amber-50 text-amber-700" :
                  "bg-red-50 text-red-700"
                }`}>{w.verdict}</span>}
              </div>
            </>
          ) : w.vendor && w.invoice ? (
            <>
              <div className="text-xl font-semibold text-slate-900">{w.id} · {w.vendor.name}</div>
              <div className="text-xs text-slate-500">
                {w.invoice.currency} {w.invoice.amount.toLocaleString()} · PO {w.invoice.poRef} · {w.agency}
              </div>
            </>
          ) : (
            <div className="text-xl font-semibold text-slate-900">{w.id}</div>
          )}
        </div>

        <WorkflowHeaderTiles workflow={w} />
        {/* 2026-05-05: Foundry Tracing deep link for the demo's tab-switch
            beat. The portal doesn't support a workflow-id pre-filter via
            URL, so we land on the project-level Tracing pane and the
            operator filters by `customDimensions.workflow_id` once. */}
        <div className="flex items-center justify-end -mt-2">
          <a
            href="https://ai.azure.com/build/tracing"
            target="_blank"
            rel="noreferrer"
            className="text-xs text-blue-700 hover:underline inline-flex items-center gap-1"
            title={`Open Foundry Tracing for this workflow. Filter by customDimensions.workflow_id == "${w.id}".`}
          >
            View in Foundry Tracing →
          </a>
        </div>
        <PhaseRibbon workflow={w} phases={d.phases} />

        <div className="flex flex-wrap gap-1 border-b border-slate-200">
          {TABS.map(t => (
            <button key={t} onClick={() => setTab(t)}
                    className={`text-sm px-3 py-2 whitespace-nowrap ${tab === t ?
                      "text-blue-700 border-b-2 border-blue-600 font-medium" :
                      "text-slate-500 hover:text-slate-800"}`}>{t}</button>
          ))}
        </div>

        {tab === "Overview" && (
          <div className="space-y-4">
            {w.type === "hiring" && specs.length > 0 && (
              <section data-testid="candidate-scorecard" className="space-y-3">
                <h3 className="text-sm font-semibold text-slate-700">
                  Candidate scorecard{" "}
                  <span className="text-xs font-normal text-slate-500">— agent-emitted</span>
                </h3>
                <div className="grid grid-cols-1 lg:grid-cols-2 gap-3">
                  {specs.map((spec, i) => (
                    <AgentDrivenComponent key={i} spec={spec} />
                  ))}
                </div>
              </section>
            )}
            {w.claim && <ReceiptPanel claim={w.claim} />}
            {d.narrative && d.activeException && (
              <>
                <ExceptionAnalysisCard narrative={d.narrative} />
                <InterventionProtocols exception={d.activeException} onResolved={refresh} />
              </>
            )}
            {!d.activeException && (() => {
              // Generic platform framing only — no domain vocabulary here.
              // For domain-friendly copy ("Awaiting screening call",
              // "Awaiting reviewer decision") use the per-domain "Open in
              // domain view" deep-link below.
              const meta = (w.metadata as { wait_kind?: string; awaiting_reason?: string } | undefined) ?? {};
              if (meta.wait_kind === "external_party") {
                return (
                  <div className="panel">
                    <div className="panel-header text-blue-700">⏳ Awaiting external party</div>
                    <div className="panel-body text-sm text-slate-700 space-y-2">
                      <p>
                        This workflow is suspended on an event from a party outside our org
                        ({meta.awaiting_reason ? <code className="bg-slate-100 px-1.5 py-0.5 rounded text-xs">{meta.awaiting_reason}</code> : "unspecified"}).
                        It does not appear on the operator queue and ages against their SLA, not ours.
                      </p>
                      <p className="text-xs text-slate-500">
                        Open the per-domain view (link in the workflow header) for the
                        domain-friendly story — who's waiting, on what, with what tokens issued.
                      </p>
                    </div>
                  </div>
                );
              }
              if (meta.wait_kind === "operator_review") {
                return (
                  <div className="panel">
                    <div className="panel-header text-amber-700">⏳ Awaiting operator review</div>
                    <div className="panel-body text-sm text-slate-700">
                      Operator action expected — see Exception Queue. Reason:{" "}
                      <code className="bg-slate-100 px-1.5 py-0.5 rounded text-xs">{meta.awaiting_reason ?? "—"}</code>.
                    </div>
                  </div>
                );
              }
              return (
                <div className="panel panel-body text-sm text-slate-500">
                  No active exception. Workflow is progressing autonomously.
                </div>
              );
            })()}
          </div>
        )}
        {tab === "Phases" && <PhaseTimeline phases={d.phases} workflowType={w.type} />}
        {tab === "Traces" && <OtelSpanTree spans={d.spans} />}
        {tab === "Ledger" && (
          <div className="space-y-1 text-xs">
            {(w.actionLedger as ActionLedgerEntry[]).map((a, i) => (
              <div key={i} className="panel panel-body">
                <div className="font-medium text-slate-800">{a.action}</div>
                <div className="text-slate-500">
                  {new Date(a.timestamp * 1000).toLocaleString()} · {a.actorKind}:{a.actorId}
                  · {a.revocable ? "revocable" : "non-revocable"}
                </div>
              </div>
            ))}
          </div>
        )}
        {tab === "Amplification" && <SkillAmplificationPanel items={d.amplifications} />}
        {tab === "Timeline" &&
          <ExecutionTimelineTab mcpCalls={d.mcpCalls} workflowId={w.id} onLogAction={logAction} />}
      </div>

      <div className="col-span-1 space-y-3">
        <AuthorityCard workflow={w} />
        <EconomicsPanel e={d.economics} />
        <FleetAssignment spans={d.spans} />
        <AuditTrail
          ledger={w.actionLedger as ActionLedgerEntry[]}
          blobUrl={d.auditBlobUrl ?? null}
        />
      </div>
    </div>
  );
}

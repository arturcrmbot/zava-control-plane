// web/client/features/governance/EvidencePanel.tsx
//
// Phase 4 TASK-031 + Phase 5 TASK-042 + Phase 7 TASK-053 of
// plan/feature-agent-governance-toolkit-1.md.
//
// Sidebar card on WorkflowDetail. Fetches GET /api/governance/verify/{wf}
// and renders three chips:
//   - chain ✓/✗      (real, served by AuditLogger.verify_chain)
//   - signatures ✓/✗ (real after Phase 5 TASK-041 — Ed25519 JWS verified
//                     against per-agent pubkeys)
//   - decisions ✓/✗  (real after Phase 7 TASK-053 — every entry's
//                     decision_id is resolved against the in-process
//                     GovernanceKernel decision registry; recorded
//                     policy_version must match the kernel's record)
//
// Click expands to show total_entries, broken_at (when broken), the
// human-readable reason, bad_signatures_at when signatures fail, and
// unresolved_decisions_at when decisions don't resolve. No new
// top-level navigation (CON-004).
import { useEffect, useState } from "react";

type VerifyReport = {
  workflow_id: string;
  chain_intact: boolean;
  signatures_valid: boolean;
  decisions_resolvable: boolean;
  total_entries: number;
  broken_at: number | null;
  bad_signatures_at: number[] | null;
  unresolved_decisions_at: number[] | null;
  reason: string | null;
};

type Props = {
  workflowId: string;
};

function Chip({
  label,
  ok,
  pending,
}: {
  label: string;
  ok: boolean;
  pending?: boolean;
}) {
  const colour = pending
    ? "bg-zinc-100 text-zinc-600 border-zinc-200"
    : ok
    ? "bg-emerald-50 text-emerald-700 border-emerald-200"
    : "bg-rose-50 text-rose-700 border-rose-200";
  const glyph = pending ? "•" : ok ? "✓" : "✗";
  return (
    <div
      className={`flex items-center justify-between rounded-md border px-2 py-1 text-xs ${colour}`}
    >
      <span className="font-medium">{label}</span>
      <span className="font-mono text-sm leading-none">{glyph}</span>
    </div>
  );
}

export default function EvidencePanel({ workflowId }: Props) {
  const [report, setReport] = useState<VerifyReport | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [expanded, setExpanded] = useState(false);

  useEffect(() => {
    let cancelled = false;
    async function run() {
      try {
        const r = await fetch(
          `/api/governance/verify/${encodeURIComponent(workflowId)}`,
        );
        if (!r.ok) {
          if (!cancelled) setError(`HTTP ${r.status}`);
          return;
        }
        const body: VerifyReport = await r.json();
        if (!cancelled) setReport(body);
      } catch (ex) {
        if (!cancelled) setError(String(ex));
      }
    }
    run();
    return () => {
      cancelled = true;
    };
  }, [workflowId]);

  if (error) return null;
  if (!report) return null;
  // Note: previously we returned null when total_entries === 0, which
  // meant the AGT panel disappeared entirely from any workflow whose
  // audit chain hadn't been written to yet. After Phase 7 TASK-053
  // every _ledger() call mirrors into the chain, so this is rarely
  // empty in practice — but render the empty state when it is so the
  // chip is always visible during the demo.
  if (report.total_entries === 0) {
    return (
      <div className="rounded-md border border-zinc-200 bg-white p-3">
        <div className="mb-2 flex items-baseline justify-between">
          <h3 className="text-xs font-semibold uppercase tracking-wide text-zinc-700">
            Evidence
          </h3>
          <span className="text-xs text-zinc-500">no activity yet</span>
        </div>
        <p className="text-xs text-zinc-500">
          Audit chain is empty for this workflow. Entries appear as the
          orchestrator writes ledger events.
        </p>
      </div>
    );
  }

  const allGreen =
    report.chain_intact && report.signatures_valid && report.decisions_resolvable;

  // Tooltip-on-hover summary (TASK-042). Fits on one line.
  const sigCount = report.bad_signatures_at
    ? `${report.total_entries - report.bad_signatures_at.length}/${report.total_entries}`
    : `${report.total_entries}/${report.total_entries}`;
  const decisionsState = report.decisions_resolvable
    ? "resolvable"
    : `unresolved at [${(report.unresolved_decisions_at ?? []).join(", ")}]`;
  const tooltip = `chain: ${report.chain_intact ? "intact" : "broken"} | signatures: ${sigCount} valid | decisions: ${decisionsState} | entries: ${report.total_entries}`;

  return (
    <div
      className="rounded-md border border-zinc-200 bg-white p-3"
      title={tooltip}
    >
      <button
        type="button"
        className="w-full text-left"
        onClick={() => setExpanded((v) => !v)}
        aria-expanded={expanded}
      >
        <div className="mb-2 flex items-baseline justify-between">
          <h3 className="text-xs font-semibold uppercase tracking-wide text-zinc-700">
            Evidence
          </h3>
          <span
            className={`text-xs ${
              allGreen ? "text-emerald-700" : "text-rose-700"
            }`}
          >
            {allGreen ? "verified" : "see details"}
          </span>
        </div>
        <div className="space-y-1">
          <Chip label="chain" ok={report.chain_intact} />
          <Chip label="signatures" ok={report.signatures_valid} />
          <Chip label="decisions" ok={report.decisions_resolvable} />
        </div>
      </button>

      {expanded && (
        <div className="mt-3 space-y-1 border-t border-zinc-100 pt-2 text-xs text-zinc-600">
          <div>
            <span className="text-zinc-500">entries:</span>{" "}
            <span className="font-mono">{report.total_entries}</span>
          </div>
          <div>
            <span className="text-zinc-500">signatures:</span>{" "}
            <span className="font-mono">{sigCount} valid</span>
          </div>
          {report.broken_at !== null && (
            <div className="text-rose-700">
              <span className="text-zinc-500">broken_at:</span>{" "}
              <span className="font-mono">{report.broken_at}</span>
            </div>
          )}
          {report.reason && (
            <div className="break-words text-rose-700">{report.reason}</div>
          )}
          {report.bad_signatures_at && report.bad_signatures_at.length > 0 && (
            <div className="text-rose-700">
              <span className="text-zinc-500">bad signatures at:</span>{" "}
              <span className="font-mono">
                [{report.bad_signatures_at.join(", ")}]
              </span>
            </div>
          )}
          {report.unresolved_decisions_at &&
            report.unresolved_decisions_at.length > 0 && (
              <div className="text-rose-700">
                <span className="text-zinc-500">unresolved decisions at:</span>{" "}
                <span className="font-mono">
                  [{report.unresolved_decisions_at.join(", ")}]
                </span>
              </div>
            )}
          <div className="pt-1 text-[10px] uppercase tracking-wide text-zinc-400">
            See plan/feature-agent-governance-toolkit-1.md (Phase 4 + 5 + 7)
          </div>
        </div>
      )}
    </div>
  );
}

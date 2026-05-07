// web/client/features/governance/EvidencePanel.tsx
//
// Phase 4 TASK-031 of plan/feature-agent-governance-toolkit-1.md.
//
// Sidebar card on WorkflowDetail. Fetches GET /api/governance/verify/{wf}
// and renders three chips:
//   - chain ✓/✗     (real, served by AuditLogger.verify_chain)
//   - signatures ✓/✗ (placeholder green; real verification lands Phase 5
//                     TASK-041 — verify Ed25519 actor_jws against per-agent
//                     pubkeys)
//   - decisions ✓/✗  (placeholder; will resolve every entry's decision_id
//                     against the in-process kernel in Phase 5)
//
// Click expands the card to show total_entries, broken_at (when broken),
// the human-readable reason, and the policy_version short hash. No
// new top-level navigation (CON-004).
import { useEffect, useState } from "react";

type VerifyReport = {
  workflow_id: string;
  chain_intact: boolean;
  signatures_valid: boolean;
  decisions_resolvable: boolean;
  total_entries: number;
  broken_at: number | null;
  bad_signatures_at: number[] | null;
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

  // Hide the card entirely on transport errors — it's an affordance,
  // not a primary surface, and the rest of WorkflowDetail still works.
  if (error) return null;
  // Also hide before the first response lands so it doesn't pop in
  // half-rendered.
  if (!report) return null;
  // Empty chain (vacuously intact) on a fresh workflow: don't bother
  // showing the card until there's something to verify.
  if (report.total_entries === 0) return null;

  const allGreen =
    report.chain_intact && report.signatures_valid && report.decisions_resolvable;

  return (
    <div className="rounded-md border border-zinc-200 bg-white p-3">
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
          {/* signatures + decisions are placeholders until Phase 5 / 7 */}
          <Chip label="signatures" ok={report.signatures_valid} pending />
          <Chip label="decisions" ok={report.decisions_resolvable} pending />
        </div>
      </button>

      {expanded && (
        <div className="mt-3 space-y-1 border-t border-zinc-100 pt-2 text-xs text-zinc-600">
          <div>
            <span className="text-zinc-500">entries:</span>{" "}
            <span className="font-mono">{report.total_entries}</span>
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
          <div className="pt-1 text-[10px] uppercase tracking-wide text-zinc-400">
            See plan/feature-agent-governance-toolkit-1.md (Phase 4)
          </div>
        </div>
      )}
    </div>
  );
}

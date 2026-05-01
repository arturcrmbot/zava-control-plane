// Recruiter view — /recruiter
//
// List every candidate the system knows about with their phase + role +
// quick links to (a) the candidate detail page and (b) any active magic
// links. Replaces the old magic-link-only view; magic links live below the
// candidate row inside the per-candidate detail page.
import { useCallback, useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { getCandidates, type CandidateRow } from "../lib/api";

const ROLE_LABELS: Record<string, string> = {
  "REQ-SDE-USA-DEMO": "Senior Data Engineer · USA",
  "REQ-SDE-DE-DEMO":  "Senior Data Engineer · Germany",
  "REQ-CD-USA-DEMO":  "Creative Director · USA",
};

const PHASE_HUMAN: Record<string, string> = {
  Triage: "Review",
  Screening: "Screening",
  Voice: "Awaiting screening call",
  Interview: "Interview",
  Compliance: "Compliance",
  Offer: "Offer",
  Onboarding: "Onboarding",
};

const AWAITING_LABEL: Record<string, string> = {
  awaiting_voice_complete:  "Awaiting screening call",
  awaiting_offer_approval:  "Awaiting offer decision",
  awaiting_budget_approval: "Awaiting budget approval",
};

const PHASE_TONE: Record<string, string> = {
  Triage: "chip-info",
  Screening: "chip-info",
  Voice: "chip-warning",
  Interview: "chip-info",
  Compliance: "chip-info",
  Offer: "chip-warning",
  Onboarding: "chip-success",
};

export default function Recruiter() {
  const [rows, setRows] = useState<CandidateRow[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [filter, setFilter] = useState("");

  const refresh = useCallback(async () => {
    setError(null);
    try {
      setRows(await getCandidates());
    } catch (e) {
      setError(String(e));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void refresh();
    const id = window.setInterval(() => void refresh(), 8_000);
    return () => window.clearInterval(id);
  }, [refresh]);

  const visible = useMemo(() => rows.filter((r) => {
    if (!filter.trim()) return true;
    const f = filter.toLowerCase();
    return (
      (r.name ?? "").toLowerCase().includes(f) ||
      (r.email ?? "").toLowerCase().includes(f) ||
      (r.role_id ?? "").toLowerCase().includes(f) ||
      (r.phase ?? "").toLowerCase().includes(f) ||
      r.candidate_id.toLowerCase().includes(f)
    );
  }), [rows, filter]);

  const counts = useMemo(() => ({
    total: rows.length,
    awaiting_voice: rows.filter((r) => r.awaiting_reason === "awaiting_voice_complete").length,
    awaiting_offer: rows.filter((r) => r.awaiting_reason === "awaiting_offer_approval").length,
    onboarding: rows.filter((r) => r.phase === "Onboarding").length,
  }), [rows]);

  return (
    <div className="max-w-6xl mx-auto p-6 sm:p-10 space-y-6">
      <div className="hero">
        <div className="hero-eyebrow">Recruiter view</div>
        <h1 className="hero-title">Candidates</h1>
        <p className="hero-subtitle">
          Click any candidate to see their full story — extracted profile, agent
          reasoning, voice transcript, audit timeline, and the magic-links
          fallback for delivering portal URLs by hand.
        </p>
      </div>

      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
        <Stat label="Candidates" value={counts.total} />
        <Stat label="Awaiting screening call" value={counts.awaiting_voice} tone="warning" />
        <Stat label="Awaiting offer decision" value={counts.awaiting_offer} tone="warning" />
        <Stat label="Onboarding" value={counts.onboarding} tone="success" />
      </div>

      <div className="panel">
        <div className="panel-header">
          <span>All candidates</span>
          <div className="flex items-center gap-2">
            <input
              type="text"
              value={filter}
              onChange={(e) => setFilter(e.target.value)}
              placeholder="Filter by name / email / role / phase"
              className="form-input !mt-0 text-xs w-72"
            />
            <button type="button" onClick={() => void refresh()} className="btn-secondary">Refresh</button>
          </div>
        </div>
        <div className="panel-body p-0">
          {loading && rows.length === 0 && (
            <div className="p-6 text-sm text-slate-500 flex items-center gap-2">
              <span className="spinner"/> Loading…
            </div>
          )}
          {error && (
            <div className="p-6 text-sm text-red-700">error: {error}</div>
          )}
          {!loading && !error && visible.length === 0 && (
            <div className="p-6 text-sm text-slate-500">
              {rows.length === 0
                ? "No candidates yet — submit an application via /apply to spin one up."
                : "No matches. Clear the filter to see all candidates."}
            </div>
          )}
          {!loading && visible.length > 0 && (
            <div className="overflow-x-auto">
              <table className="table-base">
                <thead>
                  <tr>
                    <th>Name</th>
                    <th>Email</th>
                    <th>Role</th>
                    <th>Phase</th>
                    <th>Active links</th>
                    <th className="text-right">Open</th>
                  </tr>
                </thead>
                <tbody>
                  {visible.map((row) => {
                    const phaseLabel = row.awaiting_reason
                      ? AWAITING_LABEL[row.awaiting_reason] ?? row.awaiting_reason
                      : (row.phase ? PHASE_HUMAN[row.phase] ?? row.phase : "—");
                    const phaseTone = row.awaiting_reason
                      ? "chip-warning"
                      : (row.phase ? PHASE_TONE[row.phase] ?? "chip-neutral" : "chip-neutral");
                    return (
                      <tr key={row.candidate_id}>
                        <td className="font-medium text-slate-900">{row.name ?? "—"}</td>
                        <td className="text-slate-600 text-xs">{row.email ?? "—"}</td>
                        <td className="text-xs">{ROLE_LABELS[row.role_id ?? ""] ?? row.role_id ?? "—"}</td>
                        <td><span className={phaseTone}>{phaseLabel}</span></td>
                        <td>
                          <div className="flex flex-wrap gap-1">
                            {(row.active_tokens ?? []).map((s) => (
                              <span key={s} className={`text-[10px] ${
                                s === "offer" ? "chip-warning" : s === "screen" ? "chip-success" : "chip-info"
                              }`}>{s}</span>
                            ))}
                            {(row.active_tokens ?? []).length === 0 && <span className="text-xs text-slate-400">—</span>}
                          </div>
                        </td>
                        <td className="text-right">
                          <Link to={`/recruiter/c/${row.candidate_id}`} className="btn-secondary">
                            View →
                          </Link>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          )}
        </div>
      </div>

      <p className="text-xs text-slate-500 text-center">
        Auto-refreshes every 8 seconds. List backed by{" "}
        <code className="bg-slate-100 px-1.5 py-0.5 rounded">/api/portal/admin/candidates</code>.
      </p>
    </div>
  );
}

function Stat({
  label,
  value,
  tone = "neutral",
}: {
  label: string;
  value: number;
  tone?: "neutral" | "info" | "success" | "warning";
}) {
  const ringClass =
    tone === "info" ? "ring-blue-200" :
    tone === "success" ? "ring-emerald-200" :
    tone === "warning" ? "ring-amber-200" :
    "ring-slate-200";
  return (
    <div className={`bg-white rounded-xl p-4 ring-1 ${ringClass} shadow-sm`}>
      <div className="text-xs text-slate-500 uppercase tracking-wider">{label}</div>
      <div className="mt-1 text-2xl font-semibold text-slate-900">{value}</div>
    </div>
  );
}

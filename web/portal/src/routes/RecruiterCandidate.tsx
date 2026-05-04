// Recruiter candidate detail — /recruiter/c/:id
//
// "Who is this person, what did we learn, what did the AI decide?"
// Pulls /api/portal/admin/candidate/:id and renders:
//   - candidate header (name, role, jurisdiction, current phase, CV download)
//   - what we learned (cv_crystalliser profile + reasoning steps + verdict)
//   - voice screening transcript (when present)
//   - active magic links (operator copy-link fallback)
//   - audit ledger (every orchestration step with timestamp)
import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import {
  getCandidateDetail,
  getCandidateEmails,
  type AgentReasoning,
  type CandidateDetail,
  type CandidateEmail,
  type CrystalliserOutput,
} from "../lib/api";
import {
  InterviewInvitePanel,
  AwaitingBookingPanel,
  PostInterviewPanel,
} from "../components/InterviewPanels";
import PhaseProgress from "../components/PhaseProgress";
import AgentReasoningTimeline from "../components/AgentReasoningTimeline";
import CommunicationsPanel from "../components/CommunicationsPanel";

const ROLE_LABELS: Record<string, string> = {
  "REQ-SDE-USA-DEMO": "Senior Data Engineer · USA",
  "REQ-SDE-DE-DEMO":  "Senior Data Engineer · Germany",
  "REQ-CD-USA-DEMO":  "Creative Director · USA",
};

const PHASE_HUMAN: Record<string, string> = {
  Triage: "Review (Triage)",
  Screening: "Screening",
  Voice: "Awaiting screening call",
  Interview: "Interview",
  Compliance: "Compliance",
  Offer: "Offer",
  Onboarding: "Onboarding",
};

const AWAITING_LABEL: Record<string, string> = {
  awaiting_voice_complete:  "Awaiting candidate's screening call",
  awaiting_offer_approval:  "Awaiting candidate's offer decision",
  awaiting_budget_approval: "Awaiting Finance-BP budget approval",
};

function asString(v: unknown): string {
  if (v == null) return "—";
  if (typeof v === "string") return v;
  if (typeof v === "number") return String(v);
  if (typeof v === "object" && v !== null && "value" in v) return String((v as { value: unknown }).value);
  return String(v);
}

const LEVELS_BY_ROLE_TITLE: Record<string, string[]> = {
  "Senior Data Engineer": ["Mid-Level", "Senior", "Staff", "Principal"],
  "Creative Director": ["Director", "Senior Director", "VP Creative"],
};
const DEFAULT_LEVELS = ["Junior", "Mid", "Senior", "Lead"];

function levelsFor(roleTitle: string | undefined | null): string[] {
  if (!roleTitle) return DEFAULT_LEVELS;
  for (const [k, v] of Object.entries(LEVELS_BY_ROLE_TITLE)) {
    if (roleTitle.toLowerCase().includes(k.toLowerCase())) return v;
  }
  return DEFAULT_LEVELS;
}

export default function RecruiterCandidate() {
  const { id } = useParams<{ id: string }>();
  const [data, setData] = useState<CandidateDetail | null>(null);
  const [emails, setEmails] = useState<CandidateEmail[]>([]);
  const [error, setError] = useState<string | null>(null);

  async function refresh() {
    if (!id) return;
    try {
      const [detail, mails] = await Promise.all([
        getCandidateDetail(id),
        getCandidateEmails(id).catch(() => [] as CandidateEmail[]),
      ]);
      setData(detail);
      setEmails(mails);
      setError(null);
    } catch (e) {
      setError(String(e));
    }
  }

  useEffect(() => {
    void refresh();
    const t = window.setInterval(() => void refresh(), 8_000);
    return () => window.clearInterval(t);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [id]);

  if (error) {
    return (
      <div className="max-w-4xl mx-auto p-6 sm:p-10">
        <div className="panel">
          <div className="panel-header">Candidate not found</div>
          <div className="panel-body text-sm text-red-700">{error}</div>
        </div>
      </div>
    );
  }
  if (!data) {
    return (
      <div className="max-w-4xl mx-auto p-6 sm:p-10 text-sm text-slate-500 flex items-center gap-2">
        <span className="spinner"/> Loading candidate…
      </div>
    );
  }

  const c = data.candidate;
  const w = data.workflow;
  const cv = data.agent_outputs?.cv_crystalliser as CrystalliserOutput | undefined;
  const profile = cv?.profile ?? {};
  const verdict = cv?.verdict;
  const transcript = data.voice_transcript ?? [];
  const ledger = data.action_ledger ?? [];
  // Real LLM reasoning trace from agent.completed → append_agent_reasoning.
  // Filter to just the cv_crystalliser entries; show the latest run first.
  const cvReasoning: AgentReasoning[] = (data.agent_reasoning ?? [])
    .filter((r) => r.agent_label === "cv_crystalliser")
    .reverse();
  const latestRun = cvReasoning[0];

  const roleLabel = ROLE_LABELS[c.role_id ?? ""] ?? c.role_id ?? "—";
  const phaseLabel = w.awaiting_reason
    ? AWAITING_LABEL[w.awaiting_reason] ?? `Awaiting: ${w.awaiting_reason}`
    : (w.phase ? PHASE_HUMAN[w.phase] ?? w.phase : "In progress");

  return (
    <div className="max-w-5xl mx-auto p-6 sm:p-10 space-y-6">
      <Link to="/recruiter" className="text-sm text-blue-600 hover:underline">← back to candidates</Link>

      {/* Header */}
      <div className="hero">
        <div className="hero-eyebrow">Candidate · {c.id}</div>
        <h1 className="hero-title">{c.name ?? "—"}</h1>
        <p className="hero-subtitle">
          {roleLabel} &nbsp;·&nbsp; {c.email ?? "—"}
          {w.jurisdiction && (<> &nbsp;·&nbsp; {w.jurisdiction}</>)}
        </p>
        <div className="mt-4 flex flex-wrap gap-2 text-xs">
          <span className="bg-white/10 backdrop-blur rounded-full px-3 py-1.5 border border-white/20">
            <span className="opacity-70">phase:</span> <strong className="ml-1">{phaseLabel}</strong>
          </span>
          {c.cv_url && (
            <a href={c.cv_url} target="_blank" rel="noreferrer"
               className="bg-white/15 hover:bg-white/25 backdrop-blur rounded-full px-3 py-1.5 border border-white/20 transition">
              📄 Download CV ↗
            </a>
          )}
          <span className="bg-white/10 backdrop-blur rounded-full px-3 py-1.5 border border-white/20">
            <span className="opacity-70">workflow:</span> <strong className="ml-1">{w.id}</strong>
          </span>
        </div>
      </div>

      {/* Phase stepper — shows where the candidate is in the 7-step pipeline */}
      <div className="panel">
        <div className="panel-header">
          <span>Pipeline progress</span>
          <span className="text-xs font-normal text-slate-500">refreshes every 8s</span>
        </div>
        <div className="panel-body">
          <PhaseProgress phase={w.phase ?? "apply"} />
        </div>
      </div>

      {/* Phase 7 sub-wait action panels */}
      {w.awaiting_reason === "awaiting_interview_invite" && (
        <InterviewInvitePanel
          candidateId={c.id}
          agent_reasoning={data.agent_reasoning ?? []}
          onSubmitted={() => void refresh()}
        />
      )}

      {w.awaiting_reason === "awaiting_interview_booking" && (
        <AwaitingBookingPanel
          bookingTokenUrl={
            (() => {
              const tok = data.active_tokens.find((t) => t.scope === "book_interview");
              return tok ? `${window.location.origin}/book?token=${tok.token}` : null;
            })()
          }
        />
      )}

      {w.awaiting_reason === "awaiting_interview_complete" && (
        <PostInterviewPanel
          candidateId={c.id}
          agent_reasoning={data.agent_reasoning ?? []}
          levelOptions={levelsFor(
            (w.metadata?.role_title as string | undefined) ?? null,
          )}
          onSubmitted={() => void refresh()}
        />
      )}

      {/* CV summary — what the cv_crystalliser agent extracted */}
      <div className="panel">
        <div className="panel-header">
          <span>CV summary</span>
          {cv?.extraction_status === "failed" && (
            <span className="chip-danger">extraction failed</span>
          )}
          {!latestRun && !profile._source && cv?.extraction_status !== "failed" && (
            <span className="chip-info">awaiting LLM run</span>
          )}
          {verdict?.decision && (
            <span className={`chip-${
              verdict.decision === "shortlist" ? "success" :
              verdict.decision === "drop" ? "danger" : "warning"
            }`}>
              verdict: {verdict.decision}
              {typeof verdict.confidence === "number" && (
                <> · {(verdict.confidence * 100).toFixed(0)}%</>
              )}
            </span>
          )}
        </div>
        <div className="panel-body grid grid-cols-1 sm:grid-cols-2 gap-5">
          <div>
            <h3 className="text-xs uppercase tracking-wider text-slate-500 mb-2">Profile</h3>
            <dl className="text-sm space-y-1.5">
              <div className="flex"><dt className="w-32 text-slate-500">Current role</dt><dd className="text-slate-800 font-medium">{asString(profile.current_title)}</dd></div>
              <div className="flex"><dt className="w-32 text-slate-500">Total tenure</dt><dd className="text-slate-800">{asString(profile.tenure_years_total)} yrs</dd></div>
              <div className="flex"><dt className="w-32 text-slate-500">Right to work</dt><dd className="text-slate-800">
                {profile.right_to_work?.jurisdiction ?? "—"} · {profile.right_to_work?.evidence ?? "—"}
              </dd></div>
            </dl>

            {Array.isArray(profile.skills) && profile.skills.length > 0 && (
              <>
                <h3 className="text-xs uppercase tracking-wider text-slate-500 mt-4 mb-2">Top skills</h3>
                <div className="flex flex-wrap gap-1.5">
                  {profile.skills.slice(0, 12).map((s, i) => (
                    <span key={i} className="text-[11px] bg-indigo-50 text-indigo-700 border border-indigo-200 rounded-full px-2 py-0.5">{s}</span>
                  ))}
                </div>
              </>
            )}
          </div>

          <div>
            {Array.isArray(profile.work_history) && profile.work_history.length > 0 && (
              <>
                <h3 className="text-xs uppercase tracking-wider text-slate-500 mb-2">Recent work</h3>
                <div className="text-sm space-y-2">
                  {profile.work_history.slice(0, 3).map((r, i) => (
                    <div key={i}>
                      <div><strong>{r.title}</strong> · <span className="text-slate-500">{r.employer}</span></div>
                      <div className="text-xs text-slate-500">{r.start} – {r.end}</div>
                    </div>
                  ))}
                </div>
              </>
            )}
            {verdict?.rationale && (
              <>
                <h3 className="text-xs uppercase tracking-wider text-slate-500 mt-4 mb-2">Verdict rationale</h3>
                <p className="text-sm text-slate-700">{verdict.rationale}</p>
              </>
            )}
            {cv?.extraction_status === "failed" && (
              <>
                <h3 className="text-xs uppercase tracking-wider text-slate-500 mt-4 mb-2">Extraction error</h3>
                <p className="text-xs text-slate-700">
                  {(cv as { extraction_error?: string }).extraction_error
                    ?? "The agent did not return a profile."}
                </p>
              </>
            )}
          </div>
        </div>
      </div>

      {/* Per-agent reasoning timeline — every agent run, not just CV */}
      <AgentReasoningTimeline runs={data.agent_reasoning ?? []} />

      {/* Communications — every email sent to the candidate */}
      <CommunicationsPanel emails={emails} />

      {/* Voice transcript */}
      {transcript.length > 0 && (
        <div className="panel">
          <div className="panel-header">
            <span>Voice screening transcript</span>
            <span className="chip-success">{transcript.length} turns</span>
          </div>
          <div className="panel-body">
            {transcript.map((t, i) => (
              <div key={i} className="transcript-line">
                <span className={t.role === "agent" ? "transcript-role-agent" : "transcript-role-candidate"}>
                  {t.role === "agent" ? "Agent" : c.name?.split(" ")[0] ?? "Candidate"}
                </span>
                <span className="text-slate-800">{t.text}</span>
              </div>
            ))}
          </div>
        </div>
      )}
      {transcript.length === 0 && (w.phase === "Voice" || w.awaiting_reason === "awaiting_voice_complete") && (
        <div className="panel">
          <div className="panel-header"><span><span className="status-dot status-dot-pending"/> Awaiting screening call</span></div>
          <div className="panel-body text-sm text-slate-700 space-y-2">
            <p>The candidate has been emailed a single-use screening link. The transcript will appear here once they complete the call.</p>
          </div>
        </div>
      )}

      {/* Action ledger / audit timeline */}
      <div className="panel">
        <div className="panel-header">
          <span>Audit timeline</span>
          <span className="chip-info">{ledger.length} entries</span>
        </div>
        <div className="panel-body">
          {ledger.length === 0 ? (
            <p className="text-sm text-slate-500 italic">No ledger entries yet.</p>
          ) : (
            <ol className="space-y-2 text-sm">
              {ledger.map((a, i) => (
                <li key={i} className="border-l-2 border-slate-200 pl-3 py-1">
                  <div className="font-medium text-slate-800">{a.action}</div>
                  <div className="text-xs text-slate-500">
                    {new Date(a.timestamp * 1000).toLocaleString()} · {a.actor_kind}:{a.actor_id}
                  </div>
                  {a.details && Object.keys(a.details).length > 0 && (
                    <pre className="text-[11px] text-slate-600 bg-slate-50 rounded p-1.5 mt-1 whitespace-pre-wrap">
                      {JSON.stringify(a.details, null, 2)}
                    </pre>
                  )}
                </li>
              ))}
            </ol>
          )}
        </div>
      </div>

      {/* Active magic links (operator fallback) */}
      {data.active_tokens.length > 0 && (
        <div className="panel">
          <div className="panel-header">
            <span>Active magic links</span>
            <span className="text-xs font-normal text-slate-500">copy + paste to deliver manually if email failed</span>
          </div>
          <div className="panel-body">
            <table className="table-base">
              <thead><tr><th>Scope</th><th>Token</th><th>Expires</th></tr></thead>
              <tbody>
                {data.active_tokens.map((t) => (
                  <tr key={t.token}>
                    <td><span className={`chip-${t.scope === "offer" ? "warning" : t.scope === "screen" ? "success" : "info"}`}>{t.scope}</span></td>
                    <td className="font-mono text-xs">{t.token}</td>
                    <td className="text-xs text-slate-500">{new Date(t.expires_at * 1000).toLocaleString()}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      <p className="text-xs text-slate-500 text-center">
        Auto-refreshes every 8 seconds.
      </p>
    </div>
  );
}

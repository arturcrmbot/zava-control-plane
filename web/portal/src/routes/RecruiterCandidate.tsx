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
  type AgentReasoning,
  type CandidateDetail,
  type CrystalliserOutput,
} from "../lib/api";
import {
  InterviewInvitePanel,
  AwaitingBookingPanel,
  PostInterviewPanel,
} from "../components/InterviewPanels";

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
  const [error, setError] = useState<string | null>(null);

  async function refresh() {
    if (!id) return;
    try {
      setData(await getCandidateDetail(id));
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

      {/* What the AI learned */}
      <div className="panel-elevated">
        <div className="panel-header">
          <span>What we learned · cv_crystalliser</span>
          {cv?.extraction_status === "failed" && (
            <span className="chip-danger">extraction failed</span>
          )}
          {!latestRun && !profile._source && (
            <span className="chip-info">awaiting LLM run</span>
          )}
          {latestRun?.latency_ms != null && (
            <span className="chip-info">{(latestRun.latency_ms / 1000).toFixed(1)}s · {latestRun.tool_calls?.length ?? 0} tool call(s)</span>
          )}
        </div>
        <div className="panel-body grid grid-cols-1 sm:grid-cols-2 gap-5">
          {/* Profile */}
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

            {Array.isArray(profile.work_history) && profile.work_history.length > 0 && (
              <>
                <h3 className="text-xs uppercase tracking-wider text-slate-500 mt-4 mb-2">Recent work</h3>
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
          </div>

          {/* Real LLM reasoning trace */}
          <div>
            <h3 className="text-xs uppercase tracking-wider text-slate-500 mb-2">How the agent reasoned</h3>
            {!latestRun ? (
              <p className="text-sm text-slate-500 italic">No reasoning trace recorded yet — agent has not completed.</p>
            ) : (
              <div className="space-y-3">
                {(latestRun.tool_calls ?? []).map((tc, i) => (
                  <details key={i} className="border border-slate-200 rounded-lg bg-slate-50">
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
                          <pre className="text-[11px] text-slate-700 bg-white border border-slate-200 rounded p-2 whitespace-pre-wrap break-all">{tc.args}</pre>
                        </div>
                      )}
                      {tc.result && (
                        <div>
                          <div className="text-[10px] uppercase tracking-wider text-slate-500 mb-1">result</div>
                          <pre className="text-[11px] text-slate-700 bg-white border border-slate-200 rounded p-2 whitespace-pre-wrap break-all max-h-48 overflow-auto">{tc.result.length > 1200 ? tc.result.slice(0, 1200) + "…" : tc.result}</pre>
                        </div>
                      )}
                    </div>
                  </details>
                ))}

                {latestRun.response_text && (
                  <details className="border border-slate-200 rounded-lg bg-white">
                    <summary className="cursor-pointer px-3 py-2 text-xs font-medium text-slate-700">
                      final LLM response
                      {latestRun.usage && (
                        <span className="text-slate-500 ml-2">
                          · in {latestRun.usage.input_tokens ?? "?"} / out {latestRun.usage.output_tokens ?? "?"} tok
                        </span>
                      )}
                    </summary>
                    <pre className="px-3 pb-3 text-[11px] text-slate-700 whitespace-pre-wrap break-all max-h-64 overflow-auto">{latestRun.response_text}</pre>
                  </details>
                )}

                {cvReasoning.length > 1 && (
                  <p className="text-[11px] text-slate-500">{cvReasoning.length - 1} earlier run(s) — see workflow trace.</p>
                )}
              </div>
            )}

            {cv?.extraction_status === "failed" && (
              <>
                <h3 className="text-xs uppercase tracking-wider text-slate-500 mt-4 mb-2">Verdict</h3>
                <div className="rounded-lg border p-3 bg-red-50 border-red-200">
                  <div className="text-sm"><strong>Extraction failed — no verdict</strong></div>
                  <p className="text-xs text-slate-700 mt-1">
                    {(cv as { extraction_error?: string }).extraction_error
                      ?? "The agent did not return a profile. Inspect the tool-call result above."}
                  </p>
                </div>
              </>
            )}
            {verdict?.decision && (
              <>
                <h3 className="text-xs uppercase tracking-wider text-slate-500 mt-4 mb-2">Verdict</h3>
                <div className={`rounded-lg border p-3 ${
                  verdict.decision === "shortlist" ? "bg-emerald-50 border-emerald-200" :
                  verdict.decision === "drop" ? "bg-red-50 border-red-200" :
                  "bg-amber-50 border-amber-200"
                }`}>
                  <div className="text-sm">
                    <strong className="capitalize">{verdict.decision}</strong>
                    {typeof verdict.confidence === "number" && (
                      <span className="text-slate-500 ml-2 text-xs">confidence {(verdict.confidence * 100).toFixed(0)}%</span>
                    )}
                  </div>
                  {verdict.rationale && <p className="text-xs text-slate-700 mt-1">{verdict.rationale}</p>}
                </div>
              </>
            )}
          </div>
        </div>
      </div>

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

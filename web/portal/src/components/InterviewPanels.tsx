// Three conditional action panels rendered on the recruiter candidate detail
// page when the workflow is parked at one of the Phase 7 sub-waits. Each
// panel reads the latest `interview_recommender` agent_reasoning entry so
// the recruiter sees the AI rec next to their decision controls.
import { useState } from "react";
import {
  postInterviewInvite,
  postPostInterviewDecision,
  type AgentReasoning,
} from "../lib/api";

type RecPayload = {
  decision?: "advance" | "decline";
  level_suggestion?: string | null;
  rationale?: string;
  talking_points?: string[];
  recommender_status?: "ok" | "failed";
};

function latestRec(agent_reasoning: AgentReasoning[]): RecPayload | null {
  const runs = agent_reasoning.filter((r) => r.agent_label === "interview_recommender");
  if (runs.length === 0) return null;
  const latest = runs[runs.length - 1];
  return (latest.extracted_json as RecPayload) ?? null;
}

function RecCard({ rec }: { rec: RecPayload | null }) {
  if (!rec) {
    return (
      <div className="rounded-lg border border-slate-200 bg-slate-50 p-3 text-sm text-slate-600">
        AI recommendation pending — agent has not completed yet.
      </div>
    );
  }
  if (rec.recommender_status === "failed") {
    return (
      <div className="rounded-lg border border-amber-200 bg-amber-50 p-3 text-sm">
        <strong>AI recommendation unavailable</strong>
        <p className="text-xs text-slate-700 mt-1">
          {rec.rationale ?? "See agent_reasoning trace for the failing call."}
        </p>
      </div>
    );
  }
  const isAdvance = rec.decision === "advance";
  return (
    <div className={`rounded-lg border p-3 text-sm ${
      isAdvance ? "bg-emerald-50 border-emerald-200" : "bg-amber-50 border-amber-200"
    }`}>
      <div>
        <strong>AI recommends:</strong>{" "}
        <span className="capitalize">{rec.decision}</span>
        {rec.level_suggestion && (
          <span className="text-slate-600"> · suggested level: {rec.level_suggestion}</span>
        )}
      </div>
      {rec.rationale && (
        <p className="text-xs text-slate-700 mt-1">{rec.rationale}</p>
      )}
      {rec.talking_points && rec.talking_points.length > 0 && (
        <ul className="text-xs text-slate-700 mt-2 list-disc list-inside">
          {rec.talking_points.map((p, i) => <li key={i}>{p}</li>)}
        </ul>
      )}
    </div>
  );
}

export function InterviewInvitePanel({
  candidateId, agent_reasoning, onSubmitted,
}: {
  candidateId: string;
  agent_reasoning: AgentReasoning[];
  onSubmitted: () => void;
}) {
  const rec = latestRec(agent_reasoning);
  const [reason, setReason] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function submit(decision: "invite" | "reject") {
    setBusy(true);
    setError(null);
    try {
      await postInterviewInvite(candidateId, {
        decision,
        reason: reason || undefined,
      });
      onSubmitted();
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="panel-elevated">
      <div className="panel-header">
        <span>Decision · invite to interview?</span>
        <span className="chip-info">awaiting recruiter</span>
      </div>
      <div className="panel-body space-y-3">
        <RecCard rec={rec}/>
        <textarea
          value={reason}
          onChange={(e) => setReason(e.target.value)}
          placeholder="Optional reason (logged on the workflow ledger; not sent to candidate)"
          className="w-full text-sm border border-slate-200 rounded p-2"
          rows={2}
        />
        <div className="flex gap-2">
          <button
            type="button"
            disabled={busy}
            onClick={() => submit("invite")}
            className="btn-primary flex-1"
          >{busy ? <><span className="spinner"/> Processing…</> : "Invite to interview"}</button>
          <button
            type="button"
            disabled={busy}
            onClick={() => submit("reject")}
            className="btn-danger flex-1"
          >{busy ? <><span className="spinner"/> Processing…</> : "Reject"}</button>
        </div>
        {error && <p className="text-xs text-red-600">{error}</p>}
      </div>
    </div>
  );
}

export function AwaitingBookingPanel({
  bookingTokenUrl,
}: {
  bookingTokenUrl: string | null;
}) {
  return (
    <div className="panel">
      <div className="panel-header">
        <span><span className="status-dot status-dot-pending"/> Awaiting candidate to book interview</span>
      </div>
      <div className="panel-body text-sm text-slate-700 space-y-2">
        <p>The candidate has been emailed an interview-booking link (single-use, 7-day expiry).</p>
        {bookingTokenUrl && (
          <p className="text-xs">
            Operator copy/paste fallback:{" "}
            <code className="bg-slate-100 px-1 py-0.5 rounded">{bookingTokenUrl}</code>
          </p>
        )}
      </div>
    </div>
  );
}

export function PostInterviewPanel({
  candidateId, agent_reasoning, levelOptions, onSubmitted,
}: {
  candidateId: string;
  agent_reasoning: AgentReasoning[];
  levelOptions: string[];
  onSubmitted: () => void;
}) {
  const rec = latestRec(agent_reasoning);
  const [decision, setDecision] = useState<"offer" | "reject">("offer");
  const [notes, setNotes] = useState("");
  const [rating, setRating] = useState(3);
  const [level, setLevel] = useState<string>(levelOptions[0] ?? "");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function submit() {
    setBusy(true);
    setError(null);
    try {
      await postPostInterviewDecision(candidateId, {
        decision,
        notes,
        rating,
        level: decision === "offer" ? level : undefined,
      });
      onSubmitted();
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="panel-elevated">
      <div className="panel-header">
        <span>Post-interview decision</span>
        <span className="chip-info">awaiting recruiter</span>
      </div>
      <div className="panel-body space-y-3">
        <RecCard rec={rec}/>
        <textarea
          value={notes}
          onChange={(e) => setNotes(e.target.value)}
          placeholder="Interview notes — what did the candidate show? Any concerns?"
          className="w-full text-sm border border-slate-200 rounded p-2"
          rows={4}
        />
        <div className="flex items-center gap-3 text-sm">
          <label>Overall rating:</label>
          {[1, 2, 3, 4, 5].map((n) => (
            <button
              key={n}
              type="button"
              onClick={() => setRating(n)}
              className={`w-8 h-8 rounded ${
                rating === n ? "bg-blue-600 text-white" : "bg-slate-100 text-slate-700"
              }`}
            >{n}</button>
          ))}
        </div>
        <div className="flex items-center gap-3 text-sm">
          <label>Decision:</label>
          <select
            value={decision}
            onChange={(e) => setDecision(e.target.value as "offer" | "reject")}
            className="border border-slate-200 rounded px-2 py-1"
          >
            <option value="offer">Offer</option>
            <option value="reject">Reject</option>
          </select>
          {decision === "offer" && (
            <>
              <label>Level:</label>
              <select
                value={level}
                onChange={(e) => setLevel(e.target.value)}
                className="border border-slate-200 rounded px-2 py-1"
              >
                {levelOptions.map((l) => <option key={l} value={l}>{l}</option>)}
              </select>
            </>
          )}
        </div>
        <button
          type="button"
          disabled={busy}
          onClick={submit}
          className="btn-primary w-full"
        >{busy ? <><span className="spinner"/> Submitting…</> : "Submit decision"}</button>
        {error && <p className="text-xs text-red-600">{error}</p>}
      </div>
    </div>
  );
}

import { useEffect, useState } from "react";
import PhaseProgress from "../components/PhaseProgress";
import OfferPanel from "../components/OfferPanel";
import OnboardingPanel from "../components/OnboardingPanel";
import TranscriptList from "../components/TranscriptList";
import { resolvePhase, type Phase } from "../lib/phases";

export type StatusResponse = {
  candidate: { id: string; name: string; email: string; role_id?: string };
  phase: string;
  next_action: string | null;
  offer_letter_url: string | null;
  onboarding_video_url: string | null;
  voice_transcript?: Array<{ role: string; text: string; ts: number }>;
  screen_token: string | null;
  offer_token: string | null;
};

const ROLE_LABELS: Record<string, string> = {
  "REQ-SDE-USA-DEMO": "Senior Data Engineer · USA",
  "REQ-SDE-DE-DEMO":  "Senior Data Engineer · Germany",
  "REQ-CD-USA-DEMO":  "Creative Director · USA",
};

const PHASE_HEADLINES: Partial<Record<Phase, { eyebrow: string; title: string; sub: string }>> = {
  triage:     { eyebrow: "Step 2 of 6", title: "Reviewing your CV", sub: "Our triage agent is matching your profile to the role's success criteria." },
  screening:  { eyebrow: "Step 3 of 6", title: "Time for a quick chat", sub: "Open the screening call when you're ready — it's about 60 seconds." },
  interview:  { eyebrow: "Step 4 of 6", title: "Interview being scheduled", sub: "We're coordinating with your hiring panel. Watch your inbox." },
  offer:      { eyebrow: "Step 5 of 6", title: "Your offer is ready", sub: "Review and respond below. Single-use link — please decide before it expires." },
  onboarding: { eyebrow: "Step 6 of 6", title: "Welcome to the team!", sub: "Day 1 essentials are below. We've already provisioned your tooling." },
  complete:   { eyebrow: "All set", title: "You're onboarded.", sub: "Reach out to your manager — see you on day 1." },
};

function BookCallButton({ screenToken }: { screenToken: string | null }) {
  if (!screenToken) {
    return (
      <div className="panel">
        <div className="panel-header">
          <span><span className="status-dot status-dot-pending"/> Preparing your screening link</span>
        </div>
        <div className="panel-body text-sm text-slate-600">
          Your screening link is being prepared. Refresh in a few seconds.
        </div>
      </div>
    );
  }
  return (
    <div className="panel-elevated">
      <div className="panel-header">
        <span><span className="status-dot status-dot-active"/> Screening call ready</span>
        <span className="chip-info">~60 seconds</span>
      </div>
      <div className="panel-body space-y-4">
        <p className="text-sm text-slate-700">
          A quick conversation with our screening agent. Four questions about
          your most impactful project, your interests, work authorisation, and
          earliest start date.
        </p>
        <ul className="text-sm text-slate-600 list-disc pl-5 space-y-1">
          <li>Browser-based — no app to install</li>
          <li>Microphone access required (we'll prompt you)</li>
          <li>Take the call whenever it suits you, link is good for 24h</li>
        </ul>
        <a href={`/screen?token=${encodeURIComponent(screenToken)}`} className="btn-primary btn-large">
          Start screening call →
        </a>
      </div>
    </div>
  );
}

function InterviewRsvp({ nextAction }: { nextAction: string | null }) {
  return (
    <div className="panel">
      <div className="panel-header">
        <span><span className="status-dot status-dot-pending"/> Interview being scheduled</span>
      </div>
      <div className="panel-body text-sm text-slate-700 space-y-2">
        <p>
          Our scheduling agent is coordinating with your hiring panel across
          their calendars. You'll get a calendar invite in your inbox shortly.
        </p>
        <p className="text-xs text-slate-500">
          Next action: <code className="bg-slate-100 px-1.5 py-0.5 rounded">{nextAction ?? "wait_for_email"}</code>
        </p>
      </div>
    </div>
  );
}

export default function Portal() {
  const params = new URLSearchParams(window.location.search);
  const token = params.get("token") ?? "";
  const [data, setData] = useState<StatusResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function refetch() {
    if (!token) {
      setError("Missing token in URL. Did you click the right link?");
      return;
    }
    try {
      const resp = await fetch(`/api/portal/status/${encodeURIComponent(token)}`);
      if (!resp.ok) {
        // 404 most commonly = stale link from a previous demo session
        // (the in-memory token store was reset). 410 = link expired.
        // Either way the candidate needs a fresh status link from the
        // most recent application — guide them rather than show a code.
        const message =
          resp.status === 410
            ? "This link has expired. Please request a new one from the recruiter team."
            : resp.status === 404
            ? "This link is no longer active — most likely it's from an earlier session that has been reset. Open the latest 'Application received' email we sent you, or reply to it and we'll resend the link."
            : `Status load failed (${resp.status}). Please try again in a moment.`;
        setError(message);
        return;
      }
      const body = (await resp.json()) as StatusResponse;
      setData((prev) => (prev && JSON.stringify(prev) === JSON.stringify(body) ? prev : body));
      setError(null);
    } catch (err) {
      setError(`Network error: ${(err as Error).message}`);
    }
  }

  useEffect(() => {
    refetch();
    const id = window.setInterval(refetch, 8_000); // gentle live-update
    return () => window.clearInterval(id);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [token]);

  if (error) {
    return (
      <div className="max-w-2xl mx-auto p-6 sm:p-10">
        <div className="panel">
          <div className="panel-header">
            <span><span className="status-dot status-dot-error"/> Link no longer active</span>
          </div>
          <div className="panel-body text-sm text-slate-700 space-y-3">
            <p>{error}</p>
            <p className="text-xs text-slate-500">
              If you don't see the latest email, check spam or reply to any
              previous message from us — we'll send a fresh link.
            </p>
          </div>
        </div>
      </div>
    );
  }

  if (!data) {
    return (
      <div className="max-w-2xl mx-auto p-6 sm:p-10 text-sm text-slate-500 flex items-center gap-2">
        <span className="spinner"/> Loading…
      </div>
    );
  }

  const resolved = resolvePhase(data.phase);
  const headline = PHASE_HEADLINES[resolved] ?? PHASE_HEADLINES.triage!;
  const roleLabel = ROLE_LABELS[data.candidate.role_id ?? ""] ?? "Your role";
  const turns = data.voice_transcript ?? [];

  return (
    <div className="max-w-3xl mx-auto p-6 sm:p-10 space-y-6">
      <div className="hero">
        <div className="hero-eyebrow">{headline.eyebrow}</div>
        <h1 className="hero-title">Hi {data.candidate.name.split(" ")[0]} — {headline.title}</h1>
        <p className="hero-subtitle">{headline.sub}</p>
        <div className="mt-4 inline-flex items-center gap-2 text-xs text-white/90 bg-white/10 backdrop-blur rounded-full px-3 py-1.5 border border-white/20">
          <span>📋</span>
          <span>{roleLabel}</span>
        </div>
      </div>

      <div className="panel">
        <div className="panel-header">
          <span>Your application progress</span>
          <span className="text-xs font-normal text-slate-500">refreshes every 8s</span>
        </div>
        <div className="panel-body">
          <PhaseProgress phase={data.phase} />
        </div>
      </div>

      {resolved === "screening" && <BookCallButton screenToken={data.screen_token} />}
      {resolved === "interview" && <InterviewRsvp nextAction={data.next_action} />}
      {resolved === "offer" && (
        <OfferPanel
          token={data.offer_token ?? token}
          url={data.offer_letter_url}
          onDecided={refetch}
        />
      )}
      {resolved === "onboarding" && (
        <OnboardingPanel
          videoUrl={data.onboarding_video_url}
          candidateName={data.candidate.name}
          roleLabel={roleLabel}
        />
      )}

      {turns.length > 0 && (
        <div className="panel">
          <div className="panel-header">
            <span>Your screening transcript</span>
            <span className="chip-success">{turns.length} turns</span>
          </div>
          <div className="panel-body">
            <TranscriptList turns={turns} />
          </div>
        </div>
      )}
    </div>
  );
}

import { useEffect, useState } from "react";
import PhaseProgress from "../components/PhaseProgress";
import OfferPanel from "../components/OfferPanel";
import OnboardingPanel from "../components/OnboardingPanel";

export type StatusResponse = {
  candidate: { id: string; name: string; email: string };
  // Backend returns capitalised phase names (Triage, Screening, Voice,
  // Interview, Compliance, Offer, Onboarding). The UI normalises before
  // matching; PhaseProgress also collapses Voice/Compliance into the
  // visible buckets.
  phase: string;
  next_action: string | null;
  offer_letter_url: string | null;
  onboarding_video_url: string | null;
  // Active scope tokens injected by the status route so the candidate UI
  // can route to /screen and /offer accept-decline without a separate fetch.
  screen_token: string | null;
  offer_token: string | null;
};

function BookCallButton({ screenToken }: { screenToken: string | null }) {
  if (!screenToken) {
    return (
      <div className="panel">
        <div className="panel-header">Screening call</div>
        <div className="panel-body text-sm text-slate-600">
          Preparing your screening link… refresh in a few seconds.
        </div>
      </div>
    );
  }
  return (
    <a href={`/screen?token=${encodeURIComponent(screenToken)}`} className="btn-primary">
      Book a screening call
    </a>
  );
}

function InterviewRsvp({ nextAction }: { nextAction: string | null }) {
  return (
    <div className="panel">
      <div className="panel-header">Interview scheduled</div>
      <div className="panel-body text-sm text-slate-700">
        Your interview is being arranged. Next action: <code>{nextAction ?? "wait_for_email"}</code>.
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
      setError("Missing token in URL");
      return;
    }
    try {
      const resp = await fetch(`/api/portal/status/${encodeURIComponent(token)}`);
      if (!resp.ok) {
        setError(`Status load failed (${resp.status})`);
        return;
      }
      const body = (await resp.json()) as StatusResponse;
      setData(body);
      setError(null);
    } catch (err) {
      setError(`Network error: ${(err as Error).message}`);
    }
  }

  useEffect(() => {
    refetch();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [token]);

  if (error) {
    return (
      <div className="max-w-2xl mx-auto p-8">
        <div className="panel">
          <div className="panel-header">Unable to load your portal</div>
          <div className="panel-body text-sm text-red-600">{error}</div>
        </div>
      </div>
    );
  }

  if (!data) {
    return (
      <div className="max-w-2xl mx-auto p-8 text-sm text-slate-500">Loading…</div>
    );
  }

  return (
    <div className="max-w-2xl mx-auto p-8 space-y-6">
      <div className="panel">
        <div className="panel-header">Hi {data.candidate.name}</div>
        <div className="panel-body">
          <PhaseProgress phase={(data.phase ?? "apply").toLowerCase() as any} />
        </div>
      </div>

      {(() => {
        // Backend phase strings are Capitalised (Screening, Interview, Offer,
        // Onboarding) — see api/server/routes/portal.py::_next_action_for_phase.
        // Normalise once so per-phase UI gates match regardless of casing.
        const phase = (data.phase ?? "").toLowerCase();
        return (
          <>
            {(phase === "screening" || phase === "voice") && (
              <BookCallButton screenToken={data.screen_token} />
            )}
            {phase === "interview" && <InterviewRsvp nextAction={data.next_action} />}
            {phase === "offer" && (
              <OfferPanel
                token={data.offer_token ?? token}
                url={data.offer_letter_url}
                onDecided={refetch}
              />
            )}
            {phase === "onboarding" && (
              <OnboardingPanel videoUrl={data.onboarding_video_url} />
            )}
          </>
        );
      })()}
    </div>
  );
}

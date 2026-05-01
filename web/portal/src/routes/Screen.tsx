import { useEffect, useRef, useState } from "react";
import { RealtimeCall, type Turn } from "../voice/RealtimeCall";
import TranscriptList from "../components/TranscriptList";
import { getScreenResolve, postCannedScreen, postTranscript } from "../lib/api";

/**
 * /screen?token=xxx — voice screening surface, native WebRTC.
 *
 * 1. On mount, GET /api/portal/voice/screen-resolve?token=xxx to peek the
 *    screen-scope magic-link token without consuming it. Surfaces 404/410
 *    explicitly so the candidate sees a clear error instead of a stuck spinner.
 * 2. The candidate clicks "Start screening call" — we instantiate a
 *    RealtimeCall against /api/portal/voice/session + /rtc (which proxy
 *    Azure GPT-Realtime). Mic + audio playback happen in this tab, no iframe.
 * 3. When the candidate clicks "End call", we stop the WebRTC connection,
 *    take the captured transcript, POST it to
 *    /api/portal/voice/{candidate_id}/transcript with the screen token,
 *    and redirect back to /portal?token=xxx.
 *
 * Demo-mode fallback: VITE_VOICE_TRANSPORT=canned renders a button that
 * POSTs the canned transcript via /api/portal/voice/{cid}/canned and skips
 * the WebRTC plumbing entirely. Useful for environments without mic / Azure.
 */

const SCREENING_PROMPT = `You are a friendly recruiter doing a 60-second voice screen for a Senior Data Engineer role.
Open with a quick greeting, then ask 4 questions in order and let the candidate answer each:
  1. "Tell me about your most impactful data project in the last year."
  2. "What's one technology you're excited to learn about right now?"
  3. "Are you authorised to work in the country we're hiring for?"
  4. "What's your earliest possible start date?"

Keep it conversational and short. After question 4, thank the candidate and say
"That's all for the screen — we'll be in touch." Do not score, do not give
verdicts, do not extend offers.`;

function getVoiceTransport(): string {
  if (typeof import.meta !== "undefined" && import.meta.env?.VITE_VOICE_TRANSPORT) {
    return import.meta.env.VITE_VOICE_TRANSPORT as string;
  }
  return "accelerator";
}

export default function Screen() {
  const params = new URLSearchParams(window.location.search);
  const token = params.get("token") ?? "";

  const [candidateId, setCandidateId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [callStatus, setCallStatus] = useState<
    "idle" | "connecting" | "connected" | "ending" | "ended" | "error"
  >("idle");
  const [transcript, setTranscript] = useState<Turn[]>([]);
  const [cannedRunning, setCannedRunning] = useState(false);
  const [portalUrl, setPortalUrl] = useState<string | null>(null);

  const callRef = useRef<RealtimeCall | null>(null);

  useEffect(() => {
    if (!token) {
      setError("Missing token in URL");
      return;
    }
    let cancelled = false;
    (async () => {
      try {
        const body = await getScreenResolve(token);
        if (cancelled) return;
        setCandidateId(body.candidate_id);
      } catch (err) {
        if (cancelled) return;
        const msg = (err as Error).message;
        setError(
          msg === "expired"
            ? "This screening link has expired."
            : msg.startsWith("screen-resolve failed")
              ? `Could not resolve screening link (${msg.replace("screen-resolve failed ", "")}).`
              : `Network error: ${msg}`,
        );
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [token]);

  async function startCall() {
    if (!candidateId || callRef.current) return;
    setError(null);
    const call = new RealtimeCall({
      instructions: SCREENING_PROMPT,
      onStatus: setCallStatus,
      onTranscript: (turn) => setTranscript((t) => [...t, turn]),
      onError: (err) => setError(err.message),
    });
    callRef.current = call;
    try {
      await call.start();
    } catch (err) {
      callRef.current = null;
      setError((err as Error).message);
    }
  }

  async function endCall() {
    if (!candidateId || !callRef.current) return;
    const summary = callRef.current.stop();
    callRef.current = null;
    try {
      const resp = await postTranscript(candidateId, {
        token,
        transcript: summary.transcript,
        score: 0,
        duration_s: summary.duration_s,
      });
      setPortalUrl(resp.portal_url ?? null);
      setCallStatus("ended");
    } catch (err) {
      setError(`Transcript post failed: ${(err as Error).message}`);
    }
  }

  async function runCannedScreen() {
    if (!candidateId) return;
    setCannedRunning(true);
    try {
      const resp = await postCannedScreen(candidateId, token);
      setPortalUrl(resp.portal_url ?? null);
      setCallStatus("ended");
    } catch (err) {
      setError((err as Error).message);
      setCannedRunning(false);
    }
  }

  if (error) {
    return (
      <div className="max-w-2xl mx-auto p-6 sm:p-10">
        <div className="panel">
          <div className="panel-header">
            <span><span className="status-dot status-dot-error"/> Screening unavailable</span>
          </div>
          <div className="panel-body text-sm text-red-700">{error}</div>
        </div>
      </div>
    );
  }

  if (!candidateId) {
    return (
      <div className="max-w-2xl mx-auto p-6 sm:p-10 text-sm text-slate-500 flex items-center gap-2">
        <span className="spinner"/> Loading screening surface…
      </div>
    );
  }

  if (getVoiceTransport() === "canned") {
    return (
      <div className="min-h-[calc(100vh-7rem)] flex items-center justify-center p-6">
        <div
          data-testid="screen-canned-mount"
          className="panel-elevated w-full max-w-xl"
        >
          <div className="panel-header">
            <span><span className="status-dot status-dot-pending"/> Canned screening</span>
            <span className="chip-warning">demo mode</span>
          </div>
          <div className="panel-body space-y-4 text-sm text-slate-700">
            <p>
              Voice screening is in canned mode. Press the button below to
              replay the canned transcript and advance the workflow as if you
              had completed a real call.
            </p>
            {callStatus === "ended" ? (
              <div className="space-y-3">
                <p className="text-sm text-slate-700">
                  Thanks — canned transcript replayed. The orchestration is
                  advancing.
                </p>
                {portalUrl && (
                  <a href={portalUrl} className="btn-primary btn-large w-full inline-block text-center">
                    View my application status →
                  </a>
                )}
              </div>
            ) : (
              <button
                type="button"
                onClick={runCannedScreen}
                disabled={cannedRunning}
                className="btn-primary btn-large w-full"
              >
                {cannedRunning ? <><span className="spinner"/> Running…</> : "Run canned screen"}
              </button>
            )}
          </div>
        </div>
      </div>
    );
  }

  const statusLabels: Record<string, { dot: string; label: string; tone: string }> = {
    idle:       { dot: "status-dot-idle",    label: "Ready when you are",  tone: "text-slate-600" },
    connecting: { dot: "status-dot-pending", label: "Connecting…",         tone: "text-amber-700" },
    connected:  { dot: "status-dot-active",  label: "Live · listening",     tone: "text-emerald-700" },
    ending:     { dot: "status-dot-pending", label: "Wrapping up…",         tone: "text-amber-700" },
    ended:      { dot: "status-dot-idle",    label: "Call ended",           tone: "text-slate-600" },
    error:      { dot: "status-dot-error",   label: "Error",                tone: "text-red-700" },
  };
  const sl = statusLabels[callStatus] ?? statusLabels.idle;

  return (
    <div
      className="min-h-[calc(100vh-7rem)] flex flex-col"
      data-testid="screen-call-mount"
    >
      <div className="max-w-2xl mx-auto p-6 sm:p-10 w-full space-y-5">
        <div className="hero">
          <div className="hero-eyebrow">Voice screening · ~60 seconds</div>
          <h1 className="hero-title">Quick chat with our screening agent</h1>
          <p className="hero-subtitle">
            We'll ask 4 questions — your most impactful project, what you're
            excited about, work authorisation, and earliest start. The agent
            will explain each before you speak. You can re-do the call by
            ending and clicking Start again.
          </p>
        </div>

        <div className="panel-elevated">
          <div className="panel-header">
            <span>
              <span className={`status-dot ${sl.dot}`}/>
              <span className={sl.tone}>{sl.label}</span>
            </span>
            {transcript.length > 0 && <span className="chip-info">{transcript.length} turns</span>}
          </div>
          <div className="panel-body space-y-4">
            {callStatus === "idle" && (
              <>
                <p className="text-sm text-slate-700">
                  When you press Start, we'll request mic access. Speak
                  naturally — there's no script to read off.
                </p>
                <button
                  type="button"
                  onClick={startCall}
                  className="btn-primary btn-large w-full"
                  data-testid="btn-start-call"
                >
                  🎙️ Start screening call
                </button>
              </>
            )}
            {(callStatus === "connecting" || callStatus === "connected") && (
              <>
                <p className="text-sm text-slate-700">
                  Speak naturally — the agent listens between turns. Press End
                  call when you're done with the four questions.
                </p>
                <button
                  type="button"
                  onClick={endCall}
                  className="btn-danger btn-large w-full"
                  data-testid="btn-end-call"
                >
                  End call
                </button>
              </>
            )}
            {callStatus === "ended" && (
              <div className="space-y-3">
                <p className="text-sm text-slate-700">
                  Thanks — call ended. We've sent your transcript through and
                  the orchestration is advancing.
                </p>
                {portalUrl ? (
                  <a href={portalUrl} className="btn-primary btn-large w-full inline-block text-center">
                    View my application status →
                  </a>
                ) : (
                  <p className="text-xs text-slate-500">
                    Closing this tab is fine — your application status link was
                    emailed at apply time.
                  </p>
                )}
              </div>
            )}
            {callStatus === "error" && (
              <button
                type="button"
                onClick={startCall}
                className="btn-secondary btn-large w-full"
              >
                Try again
              </button>
            )}
          </div>
        </div>

        {transcript.length > 0 && (
          <div className="panel" data-testid="transcript-panel">
            <div className="panel-header">Live transcript</div>
            <div className="panel-body max-h-96 overflow-y-auto">
              <TranscriptList turns={transcript} />
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

import { useEffect, useRef, useState } from "react";
import { RealtimeCall, type Turn } from "../voice/RealtimeCall";

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

  const callRef = useRef<RealtimeCall | null>(null);

  useEffect(() => {
    if (!token) {
      setError("Missing token in URL");
      return;
    }
    let cancelled = false;
    (async () => {
      try {
        const resp = await fetch(
          `/api/portal/voice/screen-resolve?token=${encodeURIComponent(token)}`,
        );
        if (cancelled) return;
        if (resp.status === 410) {
          setError("This screening link has expired.");
          return;
        }
        if (!resp.ok) {
          setError(`Could not resolve screening link (${resp.status}).`);
          return;
        }
        const body = (await resp.json()) as { candidate_id: string };
        setCandidateId(body.candidate_id);
      } catch (err) {
        if (!cancelled) setError(`Network error: ${(err as Error).message}`);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [token]);

  function returnToPortal() {
    window.location.assign(`/portal?token=${encodeURIComponent(token)}`);
  }

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
      const resp = await fetch(
        `/api/portal/voice/${encodeURIComponent(candidateId)}/transcript`,
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            token,
            transcript: summary.transcript,
            score: 0,
            duration_s: summary.duration_s,
          }),
        },
      );
      if (!resp.ok) {
        setError(`Transcript callback failed (${resp.status}).`);
        return;
      }
      returnToPortal();
    } catch (err) {
      setError(`Transcript post failed: ${(err as Error).message}`);
    }
  }

  async function runCannedScreen() {
    if (!candidateId) return;
    setCannedRunning(true);
    try {
      const resp = await fetch(
        `/api/portal/voice/${encodeURIComponent(candidateId)}/canned?token=${encodeURIComponent(token)}`,
        { method: "POST" },
      );
      if (!resp.ok) {
        setError(`Canned screen failed (${resp.status}).`);
        setCannedRunning(false);
        return;
      }
      returnToPortal();
    } catch (err) {
      setError(`Network error: ${(err as Error).message}`);
      setCannedRunning(false);
    }
  }

  if (error) {
    return (
      <div className="max-w-2xl mx-auto p-8">
        <div className="panel">
          <div className="panel-header">Screening unavailable</div>
          <div className="panel-body text-sm text-red-600">{error}</div>
        </div>
      </div>
    );
  }

  if (!candidateId) {
    return (
      <div className="max-w-2xl mx-auto p-8 text-sm text-slate-500">
        Loading screening surface…
      </div>
    );
  }

  if (getVoiceTransport() === "canned") {
    return (
      <div className="min-h-[calc(100vh-3.5rem)] flex items-center justify-center bg-slate-100">
        <div
          data-testid="screen-canned-mount"
          className="w-full max-w-xl rounded-lg bg-white border border-slate-200 shadow-sm p-8 space-y-4"
        >
          <h2 className="text-lg font-semibold text-slate-900">
            Canned screening (demo mode)
          </h2>
          <p className="text-sm text-slate-600">
            Voice screening is in canned mode. Press the button below to replay
            the canned transcript and continue the workflow.
          </p>
          <button
            type="button"
            onClick={runCannedScreen}
            disabled={cannedRunning}
            className="btn-primary"
          >
            {cannedRunning ? "Running…" : "Run canned screen"}
          </button>
        </div>
      </div>
    );
  }

  return (
    <div
      className="min-h-[calc(100vh-3.5rem)] flex flex-col bg-slate-100"
      data-testid="screen-call-mount"
    >
      <div className="max-w-2xl mx-auto p-8 w-full space-y-4">
        <div className="panel">
          <div className="panel-header">Voice screening</div>
          <div className="panel-body space-y-3 text-sm">
            <p>Status: <span className="font-medium">{callStatus}</span></p>
            {callStatus === "idle" && (
              <button
                type="button"
                onClick={startCall}
                className="btn-primary"
                data-testid="btn-start-call"
              >
                Start screening call
              </button>
            )}
            {(callStatus === "connecting" || callStatus === "connected") && (
              <button
                type="button"
                onClick={endCall}
                className="btn-primary"
                data-testid="btn-end-call"
              >
                End call
              </button>
            )}
          </div>
        </div>

        {transcript.length > 0 && (
          <div className="panel" data-testid="transcript-panel">
            <div className="panel-header">Live transcript</div>
            <div className="panel-body space-y-2 text-sm max-h-96 overflow-y-auto">
              {transcript.map((t, i) => (
                <div key={i}>
                  <span className="font-medium text-slate-700">{t.role}:</span>{" "}
                  <span className="text-slate-800">{t.text}</span>
                </div>
              ))}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

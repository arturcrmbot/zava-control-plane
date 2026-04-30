import { useEffect, useState } from "react";
import VoiceCallSurface from "../components/VoiceCallSurface";

/**
 * /screen?token=xxx — voice screening surface.
 *
 * 1. On mount, GET /api/portal/voice/screen-resolve?token=xxx to peek the
 *    screen-scope magic-link token without consuming it. Surfaces 404/410
 *    explicitly so the candidate sees a clear error instead of a stuck
 *    spinner.
 * 2. Mount <VoiceCallSurface> with the resolved candidate_id. The component
 *    iframes the firstcentral voice-direct accelerator (default
 *    http://localhost:8000) and listens for the on-call-end postMessage.
 * 3. On call-end the surface POSTs the transcript to
 *    /api/portal/voice/{candidate_id}/transcript and we redirect back to
 *    /portal?token=xxx so the candidate sees the next phase.
 *
 * Demo-mode fallback: VITE_VOICE_TRANSPORT=canned renders a button that
 * POSTs the canned transcript via /api/portal/voice/{cid}/canned. Useful
 * if the accelerator host is offline during a demo.
 */

function getVoiceTransport(): string {
  // Read at render time so tests can flip the env between cases without
  // having to evict the module cache. Production builds inline the env
  // anyway so the indirection is free at runtime.
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
  const [cannedRunning, setCannedRunning] = useState(false);

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
        if (!cancelled) {
          setError(`Network error: ${(err as Error).message}`);
        }
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [token]);

  function returnToPortal() {
    window.location.assign(`/portal?token=${encodeURIComponent(token)}`);
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
            The voice accelerator is disabled. Press the button below to
            replay the canned screening transcript and continue the workflow.
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
      <VoiceCallSurface
        candidateId={candidateId}
        token={token}
        onComplete={returnToPortal}
        onError={setError}
      />
    </div>
  );
}

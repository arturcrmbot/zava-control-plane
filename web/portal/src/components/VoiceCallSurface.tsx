import { useEffect, useRef, useState } from "react";

/**
 * VoiceCallSurface — embeds the firstcentral voice-direct accelerator in an
 * iframe and bridges its on-call-end signal back to our portal so we can POST
 * the transcript to /api/portal/voice/{candidate_id}/transcript.
 *
 * Wire shape:
 *   - Parent <Screen> resolves candidate_id from /screen-resolve and passes
 *     it here along with the screen-scope magic-link token.
 *   - We render an <iframe> pointing at VITE_VOICE_ACCELERATOR_URL
 *     (default http://localhost:8000) — the accelerator's FastAPI server.
 *   - We listen for window.message events from the iframe.
 *   - The accelerator's static/app.js currently does NOT postMessage on
 *     end-of-call (see endCall() in C:\dev\firstcentral\voice-direct\static\app.js).
 *     The user must patch that file to add the bridge:
 *
 *         window.parent.postMessage(
 *           { type: "voice-call-ended",
 *             transcript: <list of {role,text,ts}>,
 *             score: <number>, duration_s: <number> },
 *           "*"
 *         );
 *
 *     until then VOICE_TRANSPORT=canned (fallback button) is the demo path.
 *   - When we receive the message, POST to /api/portal/voice/{cid}/transcript
 *     with the token + payload, then call onComplete().
 */

export type CallEndPayload = {
  transcript: Array<{ role: string; text: string; ts: number }>;
  score: number;
  duration_s: number;
};

export type VoiceCallSurfaceProps = {
  candidateId: string;
  token: string;
  acceleratorUrl?: string;
  onComplete: () => void;
  onError?: (err: string) => void;
};

const DEFAULT_ACCELERATOR_URL = "http://localhost:8000";

export default function VoiceCallSurface({
  candidateId,
  token,
  acceleratorUrl,
  onComplete,
  onError,
}: VoiceCallSurfaceProps) {
  const iframeRef = useRef<HTMLIFrameElement | null>(null);
  const [status, setStatus] = useState<"idle" | "uploading" | "done" | "error">("idle");
  const [errMsg, setErrMsg] = useState<string | null>(null);

  const url = (acceleratorUrl
    || (typeof import.meta !== "undefined" && import.meta.env?.VITE_VOICE_ACCELERATOR_URL)
    || DEFAULT_ACCELERATOR_URL) as string;

  // Pass candidate context to the accelerator via query params; the
  // accelerator currently ignores them but the user can patch its app.js
  // to read them and stash on the saved session.
  const iframeSrc = `${url.replace(/\/+$/, "")}/?candidate_id=${encodeURIComponent(candidateId)}&token=${encodeURIComponent(token)}`;

  useEffect(() => {
    async function postTranscript(payload: CallEndPayload) {
      setStatus("uploading");
      try {
        const resp = await fetch(
          `/api/portal/voice/${encodeURIComponent(candidateId)}/transcript`,
          {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
              token,
              transcript: payload.transcript,
              score: payload.score,
              duration_s: payload.duration_s,
            }),
          },
        );
        if (!resp.ok) {
          const text = await resp.text();
          const msg = `transcript upload failed (${resp.status}): ${text}`;
          setErrMsg(msg);
          setStatus("error");
          onError?.(msg);
          return;
        }
        setStatus("done");
        onComplete();
      } catch (err) {
        const msg = `network error posting transcript: ${(err as Error).message}`;
        setErrMsg(msg);
        setStatus("error");
        onError?.(msg);
      }
    }

    function handleMessage(ev: MessageEvent) {
      // Accept events from any origin since the accelerator runs on a
      // separate port (different origin). Validate by message shape.
      const data = ev.data;
      if (!data || typeof data !== "object") return;
      if (data.type !== "voice-call-ended") return;
      const transcript = Array.isArray(data.transcript) ? data.transcript : [];
      const score = typeof data.score === "number" ? data.score : 0;
      const duration_s = typeof data.duration_s === "number" ? data.duration_s : 0;
      void postTranscript({ transcript, score, duration_s });
    }

    window.addEventListener("message", handleMessage);
    return () => window.removeEventListener("message", handleMessage);
  }, [candidateId, token, onComplete, onError]);

  return (
    <div className="w-full h-full flex flex-col" data-testid="voice-call-surface">
      {status === "uploading" && (
        <div className="bg-blue-50 border-b border-blue-200 px-4 py-2 text-sm text-blue-800">
          Uploading transcript…
        </div>
      )}
      {status === "done" && (
        <div className="bg-emerald-50 border-b border-emerald-200 px-4 py-2 text-sm text-emerald-800">
          Call complete — returning you to the portal.
        </div>
      )}
      {status === "error" && (
        <div className="bg-red-50 border-b border-red-200 px-4 py-2 text-sm text-red-800">
          {errMsg ?? "Transcript upload failed."}
        </div>
      )}
      <iframe
        ref={iframeRef}
        src={iframeSrc}
        title="Voice screening call"
        data-testid="voice-iframe"
        className="flex-1 w-full border-0"
        // Allow microphone for WebRTC capture; the accelerator does its own
        // getUserMedia inside, so the iframe needs the policy delegated.
        allow="microphone; autoplay"
      />
    </div>
  );
}

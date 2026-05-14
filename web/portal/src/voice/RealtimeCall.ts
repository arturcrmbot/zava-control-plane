/**
 * RealtimeCall — browser-side WebRTC client for Azure GPT-Realtime, mirrored
 * from C:\dev\firstcentral\voice-direct\static\app.js (startCall, endCall,
 * data-channel handlers) and adapted for our candidate voice screen.
 *
 * Wire-up:
 *   1. POST /api/portal/voice/session  → ephemeral key + webrtc URL
 *   2. getUserMedia({audio: true})      → local mic stream
 *   3. RTCPeerConnection.createOffer()  → SDP offer
 *   4. POST /api/portal/voice/rtc       → SDP answer (proxied through FastAPI)
 *   5. setRemoteDescription(answer)     → connection up
 *   6. Data channel "oai-events" carries:
 *        - session.update from us (instructions + voice + transcription)
 *        - response.create from us (kicks off the agent's first turn)
 *        - conversation.item.input_audio_transcription.completed (candidate speech)
 *        - response.audio_transcript.done                       (agent speech)
 *
 * Lifecycle:
 *   const call = new RealtimeCall({ instructions, onTranscript, onError });
 *   await call.start();
 *   ...
 *   const summary = call.stop();   // returns { transcript, duration_s }
 */

export type Turn = {
  role: "agent" | "candidate";
  text: string;
  ts: number;
};

export type RealtimeCallOptions = {
  /** System prompt the GPT-Realtime model gets at session.update time. */
  instructions: string;
  /** Override the `<audio>` element to attach the remote track to.
   *  Defaults to a freshly-minted detached audio element. */
  audioElement?: HTMLAudioElement;
  /** Backend base URL for /api/portal/voice routes. Defaults to "" (same origin). */
  apiBase?: string;
  /** Called every time a fresh transcript turn arrives. */
  onTranscript?: (turn: Turn) => void;
  /** Called on any non-fatal status change (connecting / connected / disconnected / error). */
  onStatus?: (status: CallStatus) => void;
  /** Called when an unrecoverable error occurs. */
  onError?: (err: Error) => void;
};

export type CallStatus =
  | "idle"
  | "connecting"
  | "connected"
  | "ending"
  | "ended"
  | "error";

export type CallSummary = {
  transcript: Turn[];
  duration_s: number;
};

type SessionResponse = {
  ephemeral_key: string;
  webrtc_url: string;
  deployment: string;
  voice: string;
};

export class RealtimeCall {
  private opts: RealtimeCallOptions;
  private pc: RTCPeerConnection | null = null;
  private dc: RTCDataChannel | null = null;
  private localStream: MediaStream | null = null;
  private audioEl: HTMLAudioElement | null = null;
  private session: SessionResponse | null = null;
  private startedAt = 0;
  private transcript: Turn[] = [];
  private status: CallStatus = "idle";

  constructor(opts: RealtimeCallOptions) {
    this.opts = opts;
  }

  getStatus(): CallStatus {
    return this.status;
  }

  getTranscript(): Turn[] {
    return this.transcript.slice();
  }

  /** Start the call: mint session, get mic, exchange SDP, wire data channel. */
  async start(): Promise<void> {
    this.setStatus("connecting");
    try {
      const apiBase = this.opts.apiBase ?? "";

      // 1. Ephemeral key from our backend (which holds the long-lived Azure cred).
      const sessionResp = await fetch(`${apiBase}/api/portal/voice/session`, {
        method: "POST",
      });
      if (!sessionResp.ok) {
        throw new Error(
          `Session mint failed: ${sessionResp.status} ${await sessionResp.text()}`,
        );
      }
      this.session = (await sessionResp.json()) as SessionResponse;

      // 2. Mic.
      this.localStream = await navigator.mediaDevices.getUserMedia({ audio: true });

      // 3. Peer connection + audio playback element.
      this.pc = new RTCPeerConnection();
      this.audioEl = this.opts.audioElement ?? document.createElement("audio");
      this.audioEl.autoplay = true;
      this.pc.ontrack = (e) => {
        if (this.audioEl) this.audioEl.srcObject = e.streams[0];
      };
      const audioTrack = this.localStream.getAudioTracks()[0];
      if (audioTrack) this.pc.addTrack(audioTrack);

      // 4. Data channel for OAI events.
      this.dc = this.pc.createDataChannel("oai-events");
      this.dc.onopen = () => this.onDataChannelOpen();
      this.dc.onmessage = (e) => this.onDataChannelMessage(e);

      // 5. Offer / proxy / answer.
      const offer = await this.pc.createOffer();
      await this.pc.setLocalDescription(offer);
      const sdpResp = await fetch(`${apiBase}/api/portal/voice/rtc`, {
        method: "POST",
        body: offer.sdp,
        headers: {
          "Authorization": `Bearer ${this.session.ephemeral_key}`,
          "Content-Type": "application/sdp",
        },
      });
      if (!sdpResp.ok) {
        throw new Error(`WebRTC ${sdpResp.status}: ${await sdpResp.text()}`);
      }
      await this.pc.setRemoteDescription({
        type: "answer",
        sdp: await sdpResp.text(),
      });

      this.startedAt = Date.now();
      this.setStatus("connected");
    } catch (err) {
      this.setStatus("error");
      const e = err instanceof Error ? err : new Error(String(err));
      this.opts.onError?.(e);
      this.cleanup();
      throw e;
    }
  }

  /** End the call. Returns transcript + duration; idempotent. */
  stop(): CallSummary {
    if (this.status === "ended") {
      return {
        transcript: this.transcript.slice(),
        duration_s: this.computeDuration(),
      };
    }
    this.setStatus("ending");
    const summary: CallSummary = {
      transcript: this.transcript.slice(),
      duration_s: this.computeDuration(),
    };
    this.cleanup();
    this.setStatus("ended");
    return summary;
  }

  // ── private ──────────────────────────────────────────────────────

  private setStatus(s: CallStatus) {
    this.status = s;
    this.opts.onStatus?.(s);
  }

  private computeDuration(): number {
    if (!this.startedAt) return 0;
    return Math.round((Date.now() - this.startedAt) / 100) / 10;
  }

  private cleanup() {
    try {
      this.dc?.close();
    } catch {/* ignore */}
    this.dc = null;
    try {
      this.pc?.close();
    } catch {/* ignore */}
    this.pc = null;
    this.localStream?.getTracks().forEach((t) => {
      try { t.stop(); } catch { /* ignore */ }
    });
    this.localStream = null;
    if (this.audioEl) {
      try { this.audioEl.srcObject = null; } catch { /* ignore */ }
      this.audioEl = null;
    }
  }

  private onDataChannelOpen() {
    if (!this.dc || !this.session) return;
    // Configure the agent's persona + transcription settings.
    this.dc.send(JSON.stringify({
      type: "session.update",
      session: {
        instructions: this.opts.instructions,
        modalities: ["text", "audio"],
        input_audio_transcription: { model: "whisper-1" },
        voice: this.session.voice,
      },
    }));
    // Have the agent open the conversation.
    this.dc.send(JSON.stringify({ type: "response.create" }));
  }

  private onDataChannelMessage(event: MessageEvent) {
    let msg: { type?: string; transcript?: string };
    try {
      msg = JSON.parse(event.data);
    } catch {
      return;
    }
    switch (msg.type) {
      case "conversation.item.input_audio_transcription.completed":
        if (msg.transcript?.trim()) {
          this.appendTurn("candidate", msg.transcript.trim());
        }
        break;
      case "response.audio_transcript.done":
        if (msg.transcript?.trim()) {
          this.appendTurn("agent", msg.transcript.trim());
        }
        break;
      // Other event types (audio buffers, response.created, etc.) are ignored
      // for our purposes — we only persist transcripts.
    }
  }

  private appendTurn(role: Turn["role"], text: string) {
    const turn: Turn = {
      role,
      text,
      ts: this.computeDuration(),
    };
    this.transcript.push(turn);
    this.opts.onTranscript?.(turn);
  }
}

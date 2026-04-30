import "@testing-library/jest-dom/vitest";
import { render, screen, fireEvent, waitFor, act } from "@testing-library/react";
import { http, HttpResponse } from "msw";
import { setupServer } from "msw/node";
import Screen from "@portal/routes/Screen";

let resolveStatus = 200;
let resolveBody: { candidate_id: string } = { candidate_id: "C-NATIVE1" };
let lastTranscriptPost: { url: string; body: any } | null = null;
let lastCannedPost: { url: string; query: string } | null = null;
let lastSessionPost: { url: string } | null = null;
let lastRtcPost: { url: string; body: string; auth: string } | null = null;

const server = setupServer(
  http.get("*/api/portal/voice/screen-resolve", () => {
    if (resolveStatus !== 200) {
      return HttpResponse.json({ detail: "err" }, { status: resolveStatus });
    }
    return HttpResponse.json(resolveBody);
  }),
  http.post("*/api/portal/voice/session", async ({ request }) => {
    lastSessionPost = { url: request.url };
    return HttpResponse.json({
      ephemeral_key: "EPH-FAKE",
      webrtc_url: "https://fake.webrtc",
      deployment: "gpt-realtime-1.5",
      voice: "alloy",
    });
  }),
  http.post("*/api/portal/voice/rtc", async ({ request }) => {
    lastRtcPost = {
      url: request.url,
      body: await request.text(),
      auth: request.headers.get("authorization") ?? "",
    };
    return new HttpResponse("v=0\nmocked-answer\n", {
      status: 200,
      headers: { "Content-Type": "application/sdp" },
    });
  }),
  http.post("*/api/portal/voice/:cid/transcript", async ({ request }) => {
    const body = await request.json();
    lastTranscriptPost = { url: request.url, body };
    return HttpResponse.json({ ok: true });
  }),
  http.post("*/api/portal/voice/:cid/canned", async ({ request }) => {
    const url = new URL(request.url);
    lastCannedPost = { url: request.url, query: url.search };
    return HttpResponse.json({ ok: true, source: "canned" });
  }),
);

// ── WebRTC mocks ─────────────────────────────────────────────────────
//
// jsdom doesn't ship RTCPeerConnection / MediaDevices; stub them at
// module level so the RealtimeCall class can drive its lifecycle.

class FakeRTCDataChannel {
  readyState = "connecting";
  onopen: (() => void) | null = null;
  onmessage: ((ev: MessageEvent) => void) | null = null;
  sent: string[] = [];
  close() { this.readyState = "closed"; }
  send(s: string) { this.sent.push(s); }
}

class FakeRTCPeerConnection {
  static instances: FakeRTCPeerConnection[] = [];
  ontrack: ((e: any) => void) | null = null;
  dc: FakeRTCDataChannel | null = null;
  closed = false;
  constructor() { FakeRTCPeerConnection.instances.push(this); }
  createDataChannel(_name: string) {
    this.dc = new FakeRTCDataChannel();
    return this.dc as unknown as RTCDataChannel;
  }
  addTrack(_t: any) {}
  async createOffer() { return { type: "offer", sdp: "v=0\nfake-offer\n" }; }
  async setLocalDescription(_o: any) {}
  async setRemoteDescription(_a: any) {}
  close() { this.closed = true; }
}

const fakeMediaStream = {
  getTracks: () => [{ stop: () => {} }],
  getAudioTracks: () => [{}],
};

beforeAll(() => {
  server.listen({ onUnhandledRequest: "error" });
  // @ts-expect-error — install fakes for jsdom
  globalThis.RTCPeerConnection = FakeRTCPeerConnection;
  Object.defineProperty(globalThis.navigator, "mediaDevices", {
    value: { getUserMedia: async () => fakeMediaStream },
    configurable: true,
  });
});

beforeEach(() => {
  resolveStatus = 200;
  resolveBody = { candidate_id: "C-NATIVE1" };
  lastTranscriptPost = null;
  lastCannedPost = null;
  lastSessionPost = null;
  lastRtcPost = null;
  FakeRTCPeerConnection.instances = [];
  window.history.replaceState({}, "", "/screen?token=SCRTOK");
  vi.stubEnv("VITE_VOICE_TRANSPORT", "accelerator");
  Object.defineProperty(window, "location", {
    value: { ...window.location, assign: vi.fn(), search: "?token=SCRTOK" },
    writable: true,
  });
});

afterEach(() => {
  server.resetHandlers();
  vi.unstubAllEnvs();
});

afterAll(() => server.close());


describe("Screen (native WebRTC)", () => {
  test("resolves token, then renders the Start call button", async () => {
    render(<Screen />);
    expect(await screen.findByTestId("btn-start-call")).toBeTruthy();
  });

  test("clicking Start call opens a peer connection via /api/portal/voice/session + /rtc", async () => {
    render(<Screen />);
    const btn = await screen.findByTestId("btn-start-call");
    await act(async () => {
      fireEvent.click(btn);
    });
    await waitFor(() => expect(lastSessionPost).not.toBeNull());
    await waitFor(() => expect(lastRtcPost).not.toBeNull());
    expect(lastRtcPost!.auth).toBe("Bearer EPH-FAKE");
    expect(lastRtcPost!.body).toContain("fake-offer");
    expect(FakeRTCPeerConnection.instances).toHaveLength(1);
  });

  test("on End call, captured transcript is POSTed and we redirect to /portal", async () => {
    render(<Screen />);
    const start = await screen.findByTestId("btn-start-call");
    await act(async () => { fireEvent.click(start); });
    await waitFor(() => expect(lastRtcPost).not.toBeNull());

    // Simulate two transcript events arriving over the data channel.
    const pc = FakeRTCPeerConnection.instances[0];
    await act(async () => {
      pc.dc!.onmessage?.(new MessageEvent("message", {
        data: JSON.stringify({
          type: "conversation.item.input_audio_transcription.completed",
          transcript: "Hello there",
        }),
      }));
      pc.dc!.onmessage?.(new MessageEvent("message", {
        data: JSON.stringify({
          type: "response.audio_transcript.done",
          transcript: "Welcome to the call.",
        }),
      }));
    });

    const end = await screen.findByTestId("btn-end-call");
    await act(async () => { fireEvent.click(end); });
    await waitFor(() => expect(lastTranscriptPost).not.toBeNull());
    expect(lastTranscriptPost!.url).toContain("/api/portal/voice/C-NATIVE1/transcript");
    expect(lastTranscriptPost!.body).toMatchObject({ token: "SCRTOK" });
    expect(lastTranscriptPost!.body.transcript).toHaveLength(2);
    expect(lastTranscriptPost!.body.transcript[0]).toMatchObject({
      role: "candidate",
      text: "Hello there",
    });
    expect(lastTranscriptPost!.body.transcript[1]).toMatchObject({
      role: "agent",
      text: "Welcome to the call.",
    });
    await waitFor(() => {
      expect((window.location.assign as any)).toHaveBeenCalledWith(
        "/portal?token=SCRTOK",
      );
    });
  });

  test("expired token (410) renders a clear error message", async () => {
    resolveStatus = 410;
    render(<Screen />);
    expect(await screen.findByText(/expired/i)).toBeTruthy();
    expect(screen.queryByTestId("btn-start-call")).toBeNull();
  });

  test("missing token in URL shows error without hitting screen-resolve", async () => {
    window.history.replaceState({}, "", "/screen");
    Object.defineProperty(window, "location", {
      value: { ...window.location, assign: vi.fn(), search: "" },
      writable: true,
    });
    render(<Screen />);
    expect(await screen.findByText(/missing token/i)).toBeTruthy();
  });

  test("VITE_VOICE_TRANSPORT=canned renders Run canned screen button that POSTs the canned route", async () => {
    vi.stubEnv("VITE_VOICE_TRANSPORT", "canned");
    render(<Screen />);
    const btn = (await screen.findByRole("button", { name: /run canned screen/i })) as HTMLButtonElement;
    fireEvent.click(btn);
    await waitFor(() => expect(lastCannedPost).not.toBeNull());
    expect(lastCannedPost!.url).toContain("/api/portal/voice/C-NATIVE1/canned");
    expect(lastCannedPost!.query).toContain("token=SCRTOK");
  });
});

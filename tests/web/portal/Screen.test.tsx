import "@testing-library/jest-dom/vitest";
import { render, screen, fireEvent, waitFor, act } from "@testing-library/react";
import { http, HttpResponse } from "msw";
import { setupServer } from "msw/node";
import Screen from "@portal/routes/Screen";

let resolveStatus = 200;
let resolveBody: { candidate_id: string } = { candidate_id: "C-IFRAME1" };
let lastTranscriptPost: { url: string; body: any } | null = null;
let lastCannedPost: { url: string; query: string } | null = null;

const server = setupServer(
  http.get("*/api/portal/voice/screen-resolve", ({ request }) => {
    if (resolveStatus !== 200) {
      return HttpResponse.json({ detail: "err" }, { status: resolveStatus });
    }
    return HttpResponse.json(resolveBody);
  }),
  http.post("*/api/portal/voice/:cid/transcript", async ({ request, params }) => {
    const body = await request.json();
    lastTranscriptPost = { url: request.url, body };
    return HttpResponse.json({ ok: true });
  }),
  http.post("*/api/portal/voice/:cid/canned", async ({ request, params }) => {
    const url = new URL(request.url);
    lastCannedPost = { url: request.url, query: url.search };
    return HttpResponse.json({ ok: true, source: "canned" });
  }),
);

beforeAll(() => server.listen({ onUnhandledRequest: "error" }));
beforeEach(() => {
  resolveStatus = 200;
  resolveBody = { candidate_id: "C-IFRAME1" };
  lastTranscriptPost = null;
  lastCannedPost = null;
  window.history.replaceState({}, "", "/screen?token=SCRTOK");
  // Default: accelerator transport. Tests for canned override.
  vi.stubEnv("VITE_VOICE_TRANSPORT", "accelerator");
  // Stub location.assign so the redirect after call-end doesn't crash jsdom.
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


describe("Screen", () => {
  test("resolves token, renders the accelerator iframe with candidate_id + token", async () => {
    render(<Screen />);
    const iframe = (await screen.findByTestId("voice-iframe")) as HTMLIFrameElement;
    expect(iframe).toBeTruthy();
    expect(iframe.getAttribute("src")).toContain("candidate_id=C-IFRAME1");
    expect(iframe.getAttribute("src")).toContain("token=SCRTOK");
    // Microphone delegated to the iframe so getUserMedia inside works.
    expect(iframe.getAttribute("allow")).toContain("microphone");
  });

  test("on voice-call-ended message, POSTs transcript and redirects to /portal", async () => {
    render(<Screen />);
    await screen.findByTestId("voice-iframe");
    // Simulate the accelerator's iframe posting the call-end signal.
    await act(async () => {
      window.dispatchEvent(new MessageEvent("message", {
        data: {
          type: "voice-call-ended",
          transcript: [
            { role: "agent", text: "Hi", ts: 0 },
            { role: "candidate", text: "Hello", ts: 1.2 },
          ],
          score: 8.4,
          duration_s: 95.2,
        },
      }));
    });
    await waitFor(() => expect(lastTranscriptPost).not.toBeNull());
    expect(lastTranscriptPost!.url).toContain("/api/portal/voice/C-IFRAME1/transcript");
    expect(lastTranscriptPost!.body).toMatchObject({
      token: "SCRTOK",
      score: 8.4,
      duration_s: 95.2,
    });
    expect(lastTranscriptPost!.body.transcript).toHaveLength(2);
    // Returns to /portal once the upload succeeds.
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
    // Iframe must NOT mount when resolve fails.
    expect(screen.queryByTestId("voice-iframe")).toBeNull();
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
    // getVoiceTransport() reads import.meta.env at render time so flipping
    // the env BEFORE render flips the branch. vi.stubEnv works on
    // import.meta.env for vite/vitest.
    vi.stubEnv("VITE_VOICE_TRANSPORT", "canned");
    render(<Screen />);
    const btn = (await screen.findByRole("button", { name: /run canned screen/i })) as HTMLButtonElement;
    expect(btn).toBeTruthy();
    fireEvent.click(btn);
    await waitFor(() => expect(lastCannedPost).not.toBeNull());
    expect(lastCannedPost!.url).toContain("/api/portal/voice/C-IFRAME1/canned");
    expect(lastCannedPost!.query).toContain("token=SCRTOK");
  });
});

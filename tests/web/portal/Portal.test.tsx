import "@testing-library/jest-dom/vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { http, HttpResponse } from "msw";
import { setupServer } from "msw/node";
import Portal, { type StatusResponse } from "@portal/routes/Portal";

let nextStatus: StatusResponse;
let lastOfferDecision: string | null = null;

const server = setupServer(
  http.get("*/api/portal/status/:token", () => HttpResponse.json(nextStatus)),
  http.post("*/api/portal/offer/:token", ({ request }) => {
    const url = new URL(request.url);
    lastOfferDecision = url.searchParams.get("decision");
    return HttpResponse.json({ ok: true, decision: lastOfferDecision });
  }),
);

beforeAll(() => server.listen({ onUnhandledRequest: "error" }));
beforeEach(() => {
  // Default: a token is present in the URL so Portal.tsx's effect fires.
  window.history.replaceState({}, "", "/portal?token=DEMO123");
  lastOfferDecision = null;
});
afterEach(() => server.resetHandlers());
afterAll(() => server.close());

describe("Portal", () => {
  test("phase=offer renders Accept and Decline buttons that POST decisions", async () => {
    nextStatus = {
      candidate: { id: "C-1", name: "Alice", email: "alice@example.com" },
      phase: "offer",
      next_action: "decide_offer",
      offer_letter_url: "https://example.com/offer.pdf",
      onboarding_video_url: null,
      screen_token: null,
      offer_token: "OFFER123",
    };
    render(<Portal />);
    const acceptBtn = await screen.findByRole("button", { name: /accept/i });
    const declineBtn = screen.getByRole("button", { name: /decline/i });
    expect(acceptBtn).toBeTruthy();
    expect(declineBtn).toBeTruthy();

    // Click Accept; verify the API was called with decision=accept.
    fireEvent.click(acceptBtn);
    await waitFor(() => expect(lastOfferDecision).toBe("accept"));
  });

  test("phase=onboarding renders an autoplaying video at the SAS url", async () => {
    nextStatus = {
      candidate: { id: "C-2", name: "Bob", email: "bob@example.com" },
      phase: "onboarding",
      next_action: null,
      offer_letter_url: null,
      onboarding_video_url: "https://example.com/welcome.mp4",
      screen_token: null,
      offer_token: null,
    };
    render(<Portal />);
    const video = (await screen.findByTestId("hg-video")) as HTMLVideoElement;
    expect(video.getAttribute("src")).toBe("https://example.com/welcome.mp4");
    expect(video.hasAttribute("controls")).toBe(true);
    // React's autoPlay prop maps to the HTML `autoplay` attribute.
    expect(video.hasAttribute("autoplay")).toBe(true);
  });

  test("phase=screening shows its token-specific screening link", async () => {
    nextStatus = {
      candidate: { id: "C-3", name: "Cara", email: "cara@example.com" },
      phase: "screening",
      next_action: "rsvp_screening",
      offer_letter_url: null,
      onboarding_video_url: null,
      screen_token: "SCREEN123",
      offer_token: null,
    };
    render(<Portal />);
    const link = (await screen.findByRole("link", {
      name: /start screening call/i,
    })) as HTMLAnchorElement;
    expect(link.getAttribute("href")).toBe("/screen?token=SCREEN123");
  });
});

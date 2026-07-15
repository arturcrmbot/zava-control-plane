// @vitest-environment jsdom
import { describe, expect, it, vi, beforeEach, afterEach } from "vitest";
import { render, screen, waitFor, cleanup, fireEvent } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";

import Memory from "../Memory";

// Stub EventSource for the useSSE module that the memory hooks pull in.
class _StubES {
  url: string;
  readyState = 0;
  onmessage: ((e: MessageEvent) => void) | null = null;
  onerror: (() => void) | null = null;
  onopen: (() => void) | null = null;
  constructor(url: string) { this.url = url; }
  close() {}
  addEventListener() {}
  removeEventListener() {}
  dispatchEvent() { return true; }
}
(globalThis as { EventSource?: typeof EventSource }).EventSource = _StubES as unknown as typeof EventSource;

beforeEach(() => {
  globalThis.fetch = vi.fn(async (url: RequestInfo | URL) => {
    const u = String(url);
    if (u.includes("/api/memory/lessons/active")) {
      return new Response(JSON.stringify({ items: [
        { id: "L-1", body: "Trigger: X. Action: Y.", domain: "hiring",
          promoted_at: "2026-05-20T08:00:00Z", rubric_score_delta: 0.12,
          experiment_n: 40, proposed_by: "ghcp", status: "active" },
      ] }), { status: 200 });
    }
    if (u.includes("/api/memory/dream-passes/recent")) {
      return new Response(JSON.stringify({ items: [
        { id: "DP-1", domain: "hiring", skill_version: "1.0",
          started_at: "2026-05-20T07:55:00Z", completed_at: "2026-05-20T07:55:30Z",
          status: "complete", candidates_proposed: 3, candidates_promoted: 1 },
      ] }), { status: 200 });
    }
    if (u.includes("/api/memory/working-notes")) {
      return new Response(JSON.stringify({ items: [
        { id: "N-1", workflow_id: "WF-1", agent_skill: "interview-recommender",
          kind: "observation", body: "candidate weak on leadership",
          captured_at: "2026-05-20T07:50:00Z", consumed_by_dream_pass: null },
      ] }), { status: 200 });
    }
    return new Response("{}", { status: 404 });
  }) as unknown as typeof fetch;
});


describe("Memory route", () => {
  afterEach(cleanup);

  it("renders the current memory and dream-pass columns", async () => {
    render(<MemoryRouter><Memory /></MemoryRouter>);
    expect(screen.getByText(/Memories/i)).toBeTruthy();
    expect(screen.getByText(/Dream passes/i)).toBeTruthy();
  });

  it("has Trigger dream pass and Dream storm buttons", () => {
    render(<MemoryRouter><Memory /></MemoryRouter>);
    expect(screen.getByRole("button", { name: /Trigger pass/i })).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: /More actions/i }));
    expect(screen.getByRole("menuitem", { name: /Dream storm/i })).toBeTruthy();
  });

  it("uses the live Telco memory domains returned by the API", async () => {
    globalThis.fetch = vi.fn(async (url: RequestInfo | URL) => {
      if (String(url).includes("/api/memory/v2/domains")) {
        return new Response(JSON.stringify({
          domains: ["network-incident", "proactive-customer-care"],
        }), { status: 200 });
      }
      return new Response(JSON.stringify({ items: [] }), { status: 200 });
    }) as unknown as typeof fetch;

    render(<MemoryRouter><Memory /></MemoryRouter>);

    await waitFor(() => {
      expect(screen.getByRole("option", { name: "network-incident" })).toBeTruthy();
      expect(screen.getByRole("option", { name: "proactive-customer-care" })).toBeTruthy();
    });
    expect(screen.queryByRole("option", { name: "hiring" })).toBeNull();
  });
});

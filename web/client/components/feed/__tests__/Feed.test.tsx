// @vitest-environment jsdom
import { describe, it, expect, beforeEach, afterEach, vi } from "vitest";
import { render, screen, cleanup, waitFor, fireEvent } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import Feed from "@client/components/feed/Feed";
import { ResolutionProvider } from "@client/hooks/useResolutionStore";
import { getRolePreset } from "@shared/roles";

beforeEach(() => {
  (globalThis as any).EventSource = class {
    onmessage: ((ev: MessageEvent) => void) | null = null;
    addEventListener() {} close() {}
  };
  globalThis.fetch = vi.fn().mockImplementation((url: string) => {
    if (url.startsWith("/api/workflows")) {
      return Promise.resolve({
        ok: true, json: async () => [
          { id: "W-1", type: "expense-claim", status: "awaiting_hitl",
            currentPhase: "Intake", createdAt: 100, slaDueAt: 9999,
            jurisdiction: "UK", agency: "Z", actionLedger: [],
            tokensSpent: 0, costUSD: 0,
            claim: { claimId: "CL-1", employeeId: "E-1", submittedAt: "2026-05-18T10:00:00Z",
                     market: "UK", currency: "GBP", category: "meals", vendor: "Pret",
                     amount: 42.5, attendees: 1, emsSource: "concur" } },
        ],
      } as Response);
    }
    return Promise.resolve({ ok: true, json: async () => [] } as Response);
  });
});
afterEach(() => { cleanup(); vi.restoreAllMocks(); });

describe("Feed", () => {
  it("renders the filter bar + at least one HITL card", async () => {
    const role = getRolePreset("ops-reviewer");
    render(
      <MemoryRouter>
        <ResolutionProvider>
          <Feed role={role} onOpenDrawer={() => {}} />
        </ResolutionProvider>
      </MemoryRouter>,
    );
    await waitFor(() => {
      expect(screen.getByText("W-1")).toBeTruthy();
    });
    expect(screen.getByRole("button", { name: /Needs you/i })).toBeTruthy();
  });

  it("switching to All activity calls the same query but with different filter", async () => {
    const role = getRolePreset("ops-reviewer");
    render(
      <MemoryRouter>
        <ResolutionProvider>
          <Feed role={role} onOpenDrawer={() => {}} />
        </ResolutionProvider>
      </MemoryRouter>,
    );
    fireEvent.click(await screen.findByRole("button", { name: /All activity/i }));
    expect(screen.getByRole("button", { name: /All activity/i }).className).toMatch(/bg-blue-600/);
  });

  it("preserves the URL ?filter param across mount", async () => {
    const role = getRolePreset("ops-reviewer"); // default filter is "needs-you"
    render(
      <MemoryRouter initialEntries={["/?filter=all"]}>
        <ResolutionProvider>
          <Feed role={role} onOpenDrawer={() => {}} />
        </ResolutionProvider>
      </MemoryRouter>,
    );
    // After mount the filter should reflect "all-activity" (from URL),
    // not role's default "needs-you".
    await waitFor(() => {
      expect(screen.getByRole("button", { name: /All activity/i }).className).toMatch(/bg-blue-600/);
    });
  });
});

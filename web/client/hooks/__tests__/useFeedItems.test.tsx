// @vitest-environment jsdom
// web/client/hooks/__tests__/useFeedItems.test.ts
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { renderHook, waitFor } from "@testing-library/react";
import type { ReactNode } from "react";
import { useFeedItems } from "../useFeedItems";
import { ResolutionProvider } from "../useResolutionStore";
import { getRolePreset } from "@shared/roles";

const wrapper = ({ children }: { children: ReactNode }) => (
  <ResolutionProvider>{children}</ResolutionProvider>
);

beforeEach(() => {
  (globalThis as any).EventSource = class {
    onmessage: ((ev: MessageEvent) => void) | null = null;
    addEventListener() {}
    close() {}
  };
  globalThis.fetch = vi.fn().mockImplementation((url: string) => {
    if (url.startsWith("/api/workflows")) {
      return Promise.resolve({
        ok: true,
        json: async () => [
          { id: "W-A", type: "expense-claim", status: "awaiting_hitl",
            currentPhase: "Intake", createdAt: 200, slaDueAt: 1, jurisdiction: "UK",
            agency: "Z", actionLedger: [], tokensSpent: 0, costUSD: 0 },
          { id: "W-B", type: "hiring", status: "in_progress",
            currentPhase: "Intake", createdAt: 100, slaDueAt: 1, jurisdiction: "UK",
            agency: "Z", actionLedger: [], tokensSpent: 0, costUSD: 0,
            metadata: { wait_kind: "external_party", awaiting_reason: "cand" } },
        ],
      } as Response);
    }
    if (url.startsWith("/api/exceptions")) {
      return Promise.resolve({
        ok: true,
        json: async () => [
          { id: "E-1", workflowId: "W-A", composedBy: "fleet-manager",
            severity: "high", category: "compliance", summary: "s",
            recommendation: "r", options: [], relatedPolicyRefs: [],
            confidence: 0.8, createdAt: 150 },
        ],
      } as Response);
    }
    if (url.startsWith("/api/policy")) {
      return Promise.resolve({ ok: true, json: async () => [] } as Response);
    }
    return Promise.resolve({ ok: true, json: async () => [] } as Response);
  });
});
afterEach(() => vi.restoreAllMocks());

describe("useFeedItems", () => {
  it("emits HITL + Exception + ExternalWait in chronological order for needs-you filter", async () => {
    const { result } = renderHook(
      () =>
        useFeedItems(getRolePreset("ops-reviewer"), {
          mode: "needs-you", domains: [], severity: null, search: "",
        }),
      { wrapper },
    );
    await waitFor(() => {
      expect(result.current.length).toBeGreaterThanOrEqual(2);
    });
    const ids = result.current.map((i) => i.id);
    expect(ids).toContain("hitl:W-A");
    expect(ids).toContain("exception:E-1");
    expect(ids).toContain("external-wait:W-B");
    expect(ids[0]).toBe("hitl:W-A"); // ts=200 newest
  });

  it("filters by role visibleCardTypes", async () => {
    const exec = getRolePreset("executive");
    const { result } = renderHook(
      () =>
        useFeedItems(exec, { mode: "all-activity", domains: [], severity: null, search: "" }),
      { wrapper },
    );
    await waitFor(() => {
      expect(
        result.current.every((i) => exec.visibleCardTypes.includes(i.type)),
      ).toBe(true);
    });
  });
});

// @vitest-environment jsdom
// web/client/hooks/__tests__/useFeedItems.test.ts
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { renderHook, waitFor } from "@testing-library/react";
import type { ReactNode } from "react";
import { useFeedItems } from "../useFeedItems";
import { ResolutionProvider } from "../useResolutionStore";
import { useResolutionStore as useResolutionStoreImported } from "../useResolutionStore";
import { getRolePreset } from "@shared/roles";

const wrapper = ({ children }: { children: ReactNode }) => (
  <ResolutionProvider>{children}</ResolutionProvider>
);

beforeEach(() => {
  // useResolutionStore persists to localStorage under a day-keyed slot —
  // wipe it between tests so prior recordings don't leak across cases.
  if (typeof localStorage !== "undefined") localStorage.clear();
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
          // W-C is the workflow E-1 attaches to — separate from W-A so the
          // HITL/Exception per-workflow dedup doesn't swallow hitl:W-A.
          { id: "W-C", type: "vendor-kyc", status: "awaiting_hitl",
            currentPhase: "Intake", createdAt: 150, slaDueAt: 1, jurisdiction: "UK",
            agency: "Z", actionLedger: [], tokensSpent: 0, costUSD: 0 },
        ],
      } as Response);
    }
    if (url.startsWith("/api/exceptions")) {
      return Promise.resolve({
        ok: true,
        json: async () => [
          { id: "E-1", workflowId: "W-C", composedBy: "fleet-manager",
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

  it("overlays a recorded resolution as a ResolvedItem in chronological place", async () => {
    // Need to access the resolution store from inside the wrapper. Use a
    // custom wrapper that exposes a setter.
    let storeRef: ReturnType<typeof import("../useResolutionStore").useResolutionStore> | null = null;
    function StoreProbe({ children }: { children: ReactNode }) {
      const store = useResolutionStoreImported();
      storeRef = store;
      return <>{children}</>;
    }
    const customWrapper = ({ children }: { children: ReactNode }) => (
      <ResolutionProvider>
        <StoreProbe>{children}</StoreProbe>
      </ResolutionProvider>
    );

    const { result, rerender } = renderHook(
      () =>
        useFeedItems(getRolePreset("ops-reviewer"), {
          mode: "needs-you", domains: [], severity: null, search: "",
        }),
      { wrapper: customWrapper },
    );

    await waitFor(() => {
      expect(result.current.map((i) => i.id)).toContain("hitl:W-A");
    });

    // Record a resolution and re-render.
    storeRef!.record("hitl:W-A", { verb: "Approved", actor: "you", actedAt: 200 });
    rerender();

    await waitFor(() => {
      const ids = result.current.map((i) => i.id);
      expect(ids).toContain("resolved:hitl:W-A");
      expect(ids).not.toContain("hitl:W-A");
    });
  });

  it("excludes milestone/policy/agent-event cards in needs-you mode but includes them in all-activity", async () => {
    // The test fixture has W-A=awaiting_hitl, W-B=in_progress(external_party).
    // Neither is completed/failed, so no milestone cards expected even in
    // all-activity. Verify by adding a completed workflow to the mock.
    globalThis.fetch = vi.fn().mockImplementation((url: string) => {
      if (url.startsWith("/api/workflows")) {
        return Promise.resolve({
          ok: true,
          json: async () => [
            { id: "W-Done", type: "expense-claim", status: "completed",
              currentPhase: "Audit", createdAt: 50, slaDueAt: 1, jurisdiction: "UK",
              agency: "Z", actionLedger: [], tokensSpent: 0, costUSD: 0 },
            { id: "W-A", type: "expense-claim", status: "awaiting_hitl",
              currentPhase: "Intake", createdAt: 200, slaDueAt: 1, jurisdiction: "UK",
              agency: "Z", actionLedger: [], tokensSpent: 0, costUSD: 0 },
          ],
        } as Response);
      }
      return Promise.resolve({ ok: true, json: async () => [] } as Response);
    });

    const role = getRolePreset("sre");
    const { result, rerender } = renderHook(
      ({ mode }) => useFeedItems(role, { mode, domains: [], severity: null, search: "" }),
      { wrapper, initialProps: { mode: "needs-you" as const } },
    );

    await waitFor(() => expect(result.current.length).toBeGreaterThan(0));
    expect(result.current.find((i) => i.id === "milestone:W-Done")).toBeUndefined();

    rerender({ mode: "all-activity" as const });
    await waitFor(() => {
      expect(result.current.find((i) => i.id === "milestone:W-Done")).toBeDefined();
    });
  });
});

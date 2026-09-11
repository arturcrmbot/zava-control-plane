// @vitest-environment jsdom
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { loadGuidedJourney, readJourneyDetails, resolveJourneyDecision, startAuroraJourney } from "../guidedJourney";

const root = {
  id: "AUR-recorded",
  type: "aurora-budget-response",
  orchestrationInstanceId: "AUR-recorded",
  status: "completed",
  createdAt: 10,
};

beforeEach(() => vi.stubGlobal("fetch", vi.fn()));
afterEach(() => vi.unstubAllGlobals());

describe("guided journey evidence", () => {
  it("selects an actual recorded Aurora root without issuing a POST", async () => {
    vi.mocked(fetch).mockResolvedValueOnce(Response.json([
      { id: "EXP-1", type: "expense-claim" },
      root,
      { ...root, id: "AUR-latest", orchestrationInstanceId: "AUR-latest", createdAt: 20 },
    ]));

    expect(await loadGuidedJourney(true)).toEqual({
      workflowId: "AUR-latest", source: "replay",
    });
    expect(fetch).toHaveBeenCalledTimes(1);
    expect(fetch).toHaveBeenCalledWith("/api/workflows");
  });

  it("does not invent a journey when the tape has no Aurora execution", async () => {
    vi.mocked(fetch).mockResolvedValueOnce(Response.json([
      { ...root, orchestrationInstanceId: null },
    ]));
    await expect(loadGuidedJourney(true)).rejects.toThrow(/no recorded Aurora/i);
    expect(fetch).toHaveBeenCalledTimes(1);
  });

  it("follows an existing live run instead of starting another", async () => {
    vi.mocked(fetch).mockResolvedValueOnce(Response.json([root]));
    expect(await loadGuidedJourney(false)).toEqual({
      workflowId: root.id, source: "live",
    });
    expect(fetch).toHaveBeenCalledTimes(1);
  });

  it("starts a real asynchronous run when no existing run is available", async () => {
    vi.mocked(fetch)
      .mockResolvedValueOnce(Response.json([]))
      .mockResolvedValueOnce(Response.json({ workflow_id: "AUR-new" }, { status: 202 }));
    expect(await loadGuidedJourney(false, "request-1")).toEqual({
      workflowId: "AUR-new", source: "live",
    });
    expect(fetch).toHaveBeenLastCalledWith("/api/demo/trigger/full-aurora-arc?count=3", {
      method: "POST", headers: { "Idempotency-Key": "request-1" },
    });
  });

  it("rejects the old synchronous caption response", async () => {
    vi.mocked(fetch).mockResolvedValueOnce(Response.json({ phases: [] }));
    await expect(startAuroraJourney("request-1")).rejects.toThrow(/202/);
  });

  it("surfaces a failed starter rather than claiming work began", async () => {
    vi.mocked(fetch).mockResolvedValueOnce(Response.json(
      { detail: "Functions unavailable" }, { status: 503 },
    ));
    await expect(startAuroraJourney("request-1")).rejects.toThrow(/Functions unavailable/);
  });

  it("reads actual phases and children from workflow detail", async () => {
    vi.mocked(fetch).mockResolvedValueOnce(Response.json({
      workflow: { ...root, currentPhase: "Synthesise outcomes" },
      phases: [{ name: "Queue AP invoice reviews", status: "completed" }],
      activeException: null,
      packDetail: {
        outputs: {
          recommendation: { rationale: "Commitments exceed the budget." },
          policy: { decision_id: "DEC-real" },
        },
        children: [
          { workflow_id: "API-real-1", outcome: { status: "rejected" } },
          { workflow_id: "API-real-2", outcome: { status: "completed" } },
        ],
      },
    }));

    const detail = await readJourneyDetails(root.id);
    expect(detail?.phases).toEqual([{ name: "Queue AP invoice reviews", status: "completed" }]);
    expect(detail?.children).toEqual([
      { workflowId: "API-real-1", status: "rejected" },
      { workflowId: "API-real-2", status: "completed" },
    ]);
    expect(detail?.policyDecisionId).toBe("DEC-real");
    expect(detail?.recommendation).toBe("Commitments exceed the budget.");
  });

  it("rejects evidence for a different workflow", async () => {
    vi.mocked(fetch).mockResolvedValueOnce(Response.json({
      workflow: { ...root, id: "AUR-wrong" }, phases: [],
    }));
    await expect(readJourneyDetails(root.id)).rejects.toThrow(/identity/);
  });

  it("preserves the business rejection carried by the legacy terminal status", async () => {
    vi.mocked(fetch).mockResolvedValueOnce(Response.json({
      workflow: {
        ...root,
        status: "failed",
        metadata: { rejected: true, rejection_reason: "Operator declined the freeze" },
      },
      phases: [],
    }));

    const detail = await readJourneyDetails(root.id);
    expect(detail?.outcome).toBe("rejected");
    expect(detail?.reason).toBe("Operator declined the freeze");
  });

  it("reports missing detail without constructing a fake phase", async () => {
    vi.mocked(fetch).mockResolvedValueOnce(new Response("", { status: 404 }));
    expect(await readJourneyDetails(root.id)).toBeNull();
  });

  it("uses the existing decision route without inventing an actor role", async () => {
    vi.mocked(fetch).mockResolvedValueOnce(Response.json({ resolved: 1 }));
    await resolveJourneyDecision("exception-1", "reject");
    expect(fetch).toHaveBeenCalledWith("/api/exceptions/exception-1/resolve", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ resolution: "reject" }),
    });
  });
});

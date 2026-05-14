// @vitest-environment jsdom
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import { useRef } from "react";
import { WorkflowDrawer, type DrawerView } from "../WorkflowDrawer";
import type { CosmicFlash, EntityRow } from "../../lib/types";

// EntityView is not a named export; render WorkflowDrawer in entity mode
// (per task contract).

function Harness({ view }: { view: DrawerView }) {
  const flashesRef = useRef<{ buffer: CosmicFlash[]; version: number }>({
    buffer: [],
    version: 0,
  });
  return (
    <WorkflowDrawer
      view={view}
      onClose={() => {}}
      onOpenWorkflow={() => {}}
      onOpenEntity={() => {}}
      flashesRef={flashesRef}
    />
  );
}

const ENTITY_ID = "VEN-0042";

const ENTITY: EntityRow = {
  id: ENTITY_ID,
  _label: "Vendor",
  kind: "Vendor",
  source_workflows: ["vendor-kyc-1", "vendor-kyc-2", "expense-claim-9"],
  first_seen_at: null,
  last_seen_at: null,
};

beforeEach(() => {
  vi.stubGlobal(
    "fetch",
    vi.fn(async (input: RequestInfo | URL) => {
      const url = String(input);
      if (url.endsWith(`/linked`)) {
        return new Response(JSON.stringify([]), {
          status: 200,
          headers: { "Content-Type": "application/json" },
        });
      }
      return new Response(JSON.stringify(ENTITY), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      });
    }),
  );
});

afterEach(() => {
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
});

describe("WorkflowDrawer (EntityView)", () => {
  it("shows a humanized loading state before fetch resolves", () => {
    render(<Harness view={{ type: "entity", id: ENTITY_ID }} />);
    // Track F humanization replaced the technical "Loading…" stub copy.
    expect(screen.getByText("Loading record…")).toBeTruthy();
  });

  it("renders humanized 'Touched by …' header once entity loads", async () => {
    render(<Harness view={{ type: "entity", id: ENTITY_ID }} />);
    // 3 source workflows across 2 domains (vendor-kyc + expense-claim).
    await waitFor(() => {
      expect(
        screen.getByText(/Touched by 3 workflows across 2 domains/),
      ).toBeTruthy();
    });
  });

  it("renders the precedent chain when the entity is a Decision", async () => {
    const DECISION_ID = "DEC-NOW";
    const DECISION: EntityRow = {
      id: DECISION_ID,
      _label: "Decision",
      kind: "Decision",
      source_workflows: ["expense-claim-9"],
      first_seen_at: null,
      last_seen_at: null,
      verdict: "approve",
      reason: "looks fine",
      phase: "signoff",
      workflow_id: "expense-claim-9",
    } as EntityRow;

    vi.unstubAllGlobals();
    vi.stubGlobal(
      "fetch",
      vi.fn(async (input: RequestInfo | URL) => {
        const url = String(input);
        if (url.endsWith("/precedents")) {
          return new Response(
            JSON.stringify({
              precedents: [
                {
                  id: "DEC-PRIOR",
                  workflow_id: "expense-claim-1",
                  phase: "signoff",
                  verdict: "approve",
                  reason: "prior precedent",
                  decided_at: "2026-05-01T10:00:00",
                },
              ],
            }),
            { status: 200, headers: { "Content-Type": "application/json" } },
          );
        }
        if (url.endsWith("/linked")) {
          return new Response(JSON.stringify([]), {
            status: 200,
            headers: { "Content-Type": "application/json" },
          });
        }
        return new Response(JSON.stringify(DECISION), {
          status: 200,
          headers: { "Content-Type": "application/json" },
        });
      }),
    );

    render(<Harness view={{ type: "entity", id: DECISION_ID }} />);
    await waitFor(() => {
      expect(screen.getByText("Precedents")).toBeTruthy();
      expect(screen.getByText("expense-claim-1")).toBeTruthy();
      expect(screen.getByText(/prior precedent/)).toBeTruthy();
    });
  });
});

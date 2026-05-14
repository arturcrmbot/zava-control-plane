// @vitest-environment jsdom
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { cleanup, render, screen, waitFor } from "@testing-library/react";
import { useRef } from "react";
import { WorkflowDrawer, type DrawerView } from "../WorkflowDrawer";
import type { CosmicFlash, EntityRow } from "../../lib/types";

const PERSONA_ID = "PER-cfo";

const PERSONA: EntityRow = {
  id: PERSONA_ID,
  _label: "Person",
  kind: "Person",
  role: "cfo",
  name: "CFO",
  source_workflows: [],
  first_seen_at: null,
  last_seen_at: null,
};

const INSIGHT = {
  id: "INSIGHT-cfo-1",
  role: "cfo",
  scope: "Finance",
  decided_at: "2026-05-12T10:00:00Z",
  headline: "All brands within budget",
  body: "calm",
  kpis: { budget_used_pct: 0.62 },
  proposed_actions: [
    {
      id: "ACT-1",
      label: "Tighten Brand A budget",
      verdict: "freeze",
      decided_on: ["BRAND-Aurora"],
      attributes: { scope: "po", expiry_days: 14 },
    },
  ],
  fingerprint: "fp-1",
};

const LABELS = {
  verdicts: {
    approve: "Approved", reject: "Rejected", escalate: "Escalated",
    defer: "Deferred", request_changes: "Changes requested",
    freeze: "Freeze", unfreeze: "Unfreeze", cap: "Cap",
    void: "Voided", partial: "Partial approval",
  },
  scopes: {
    po: "purchase orders", vendor_po: "vendor POs", hiring: "new hires",
    fx: "FX hedges", expense: "expenses", access: "access requests", data: "data access",
  },
  personas: {
    cfo: "CFO", ceo: "CEO", controller: "Controller", ap_clerk: "AP Clerk",
    treasurer: "Treasurer", hr_director: "HR Director", sourcing_lead: "Sourcing Lead",
    it_admin_director: "IT Director", dpo: "Data Protection Officer",
  },
};

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

function jsonResponse(body: unknown, status = 200) {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

describe("WorkflowDrawer persona-insight panel", () => {
  beforeEach(() => {
    cleanup();
  });

  afterEach(() => {
    cleanup();
    vi.unstubAllGlobals();
    vi.restoreAllMocks();
  });

  it("renders the latest insight when a persona Person entity is open", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async (input: RequestInfo | URL) => {
        const url = String(input);
        if (url.includes("/api/personas/labels/preview")) return jsonResponse(LABELS);
        if (url.includes("/insights/latest")) return jsonResponse(INSIGHT);
        if (url.endsWith("/linked")) return jsonResponse([]);
        if (url.endsWith(`/api/entities/${PERSONA_ID}`)) return jsonResponse(PERSONA);
        return jsonResponse({});
      }),
    );

    render(<Harness view={{ type: "entity", id: PERSONA_ID }} />);

    await waitFor(() => {
      expect(screen.getByText(/All brands within budget/)).toBeTruthy();
    });
    expect(screen.getByText(/budget_used_pct/)).toBeTruthy();
    await waitFor(() => {
      expect(screen.getByText(/Freeze Aurora purchase orders \(14 days\)/)).toBeTruthy();
    });
    expect(screen.getByText("CFO")).toBeTruthy();

    // Persona-in-the-loop: no approve button. The proposed action is
    // displayed with an "Auto-applied ✓" badge (the cadence loop
    // self-applies via apply_proposed_actions, gated only by the AGT
    // matrix). Confirm the badge renders and no Approve button exists.
    expect(screen.getByText(/Auto-applied/)).toBeTruthy();
    expect(screen.queryByRole("button", { name: /Approve/ })).toBeNull();
  });

  it("renders nothing for the insight panel when the API returns 404", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async (input: RequestInfo | URL) => {
        const url = String(input);
        if (url.includes("/api/personas/labels/preview")) return jsonResponse(LABELS);
        if (url.includes("/insights/latest")) {
          return new Response("", { status: 404 });
        }
        if (url.endsWith("/linked")) return jsonResponse([]);
        if (url.endsWith(`/api/entities/${PERSONA_ID}`)) return jsonResponse(PERSONA);
        return jsonResponse({});
      }),
    );

    render(<Harness view={{ type: "entity", id: PERSONA_ID }} />);

    // Wait for entity to load (Connected to section appears for any loaded entity).
    await waitFor(() => {
      expect(screen.getByText(/Connected to/)).toBeTruthy();
    });
    expect(screen.queryByText(/All brands within budget/)).toBeNull();
  });
});

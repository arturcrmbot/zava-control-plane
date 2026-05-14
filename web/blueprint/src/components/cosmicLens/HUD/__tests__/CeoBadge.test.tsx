// @vitest-environment jsdom
import { afterEach, describe, it, expect, vi, beforeEach } from "vitest";
import { act, cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { CeoBadge } from "../CeoBadge";

type ESInstance = {
  url: string;
  onmessage: ((ev: { data: string }) => void) | null;
  onerror: ((ev: unknown) => void) | null;
  close: () => void;
};

describe("CeoBadge", () => {
  let esInstances: ESInstance[] = [];

  beforeEach(() => {
    esInstances = [];
    vi.stubGlobal(
      "fetch",
      vi.fn(async (url: string) => {
        if (url.includes("/api/personas/ceo/insights/latest")) {
          return new Response(
            JSON.stringify({
              id: "INS-CEO-1",
              role: "ceo",
              headline: "Initial CEO snapshot — 3 domains green",
              body: "All hiring, vendor-kyc, and expense flows nominal.",
              kpis: { domains: 3, alerts: 0 },
              decided_at: new Date().toISOString(),
            }),
            { status: 200 },
          );
        }
        return new Response("{}", { status: 200 });
      }),
    );
    (global as any).EventSource = class {
      url: string;
      onmessage: any = null;
      onerror: any = null;
      constructor(url: string) {
        this.url = url;
        esInstances.push(this as unknown as ESInstance);
      }
      close() {}
    };
  });

  afterEach(() => {
    cleanup();
  });

  it("renders nothing when disabled", () => {
    const { container } = render(<CeoBadge enabled={false} />);
    expect(container.innerHTML).toBe("");
  });

  it("renders the latest CEO headline from the snapshot endpoint", async () => {
    render(<CeoBadge enabled={true} />);
    await waitFor(() => {
      expect(
        screen.getByText(/Initial CEO snapshot — 3 domains green/i),
      ).toBeTruthy();
    });
  });

  it("updates the headline when a new CEO Insight arrives via SSE", async () => {
    render(<CeoBadge enabled={true} />);
    await waitFor(() => {
      expect(
        screen.getByText(/Initial CEO snapshot — 3 domains green/i),
      ).toBeTruthy();
    });
    expect(esInstances.length).toBeGreaterThan(0);
    const es = esInstances[0];
    act(() => {
      es.onmessage?.({
        data: JSON.stringify({
          kind: "Insight",
          role: "ceo",
          id: "INS-CEO-2",
          headline: "Live update — vendor-kyc surge contained",
          body: "Surge contained within policy thresholds.",
          kpis: { surge: 12 },
          decided_at: new Date().toISOString(),
        }),
      });
    });
    await waitFor(() => {
      expect(
        screen.getByText(/Live update — vendor-kyc surge contained/i),
      ).toBeTruthy();
    });
  });

  it("opens a popover with body text when clicked", async () => {
    const { getByTestId } = render(<CeoBadge enabled={true} />);
    await waitFor(() => {
      expect(
        screen.getByText(/Initial CEO snapshot — 3 domains green/i),
      ).toBeTruthy();
    });
    fireEvent.click(getByTestId("ceo-badge"));
    await waitFor(() => {
      expect(
        screen.getByText(/All hiring, vendor-kyc, and expense flows nominal\./i),
      ).toBeTruthy();
    });
  });
});

// @vitest-environment jsdom
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { cleanup, render, screen, waitFor } from "@testing-library/react";
import { DecisionTicker } from "../DecisionTicker";

describe("DecisionTicker", () => {
  afterEach(() => { cleanup(); });
  beforeEach(() => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async (url: string) => {
        if (url.includes("/api/ticker/recent")) {
          return new Response(
            JSON.stringify({
              ticker: [
                {
                  kind: "Decision",
                  id: "DEC-1",
                  persona_role: "cfo",
                  verdict: "freeze",
                  decided_on: ["BRAND-aurora"],
                  decided_at: new Date().toISOString(),
                },
                {
                  kind: "Insight",
                  id: "INS-1",
                  role: "ceo",
                  headline: "Org snapshot — 3 domain(s) reporting",
                  decided_at: new Date().toISOString(),
                },
              ],
            }),
            { status: 200 },
          );
        }
        if (url.includes("/api/personas/colors")) {
          return new Response(
            JSON.stringify({ cfo: "#4f9bff" }),
            { status: 200 },
          );
        }
        return new Response("{}", { status: 200 });
      }),
    );
    (global as any).EventSource = class {
      close() {}
      onmessage: any = null;
      onerror: any = null;
      constructor(_: string) {}
    };
  });

  it("renders nothing when disabled", () => {
    const { container } = render(<DecisionTicker enabled={false} />);
    expect(container.innerHTML).toBe("");
  });

  it("renders recent items from snapshot", async () => {
    render(<DecisionTicker enabled={true} />);
    await waitFor(() => {
      expect(screen.getByText(/froze aurora/i)).toBeTruthy();
      expect(screen.getByText(/Org snapshot — 3 domain\(s\)/i)).toBeTruthy();
    });
  });

  it("shows 'Recorded' header when isReplay=true", async () => {
    render(<DecisionTicker enabled={true} isReplay={true} />);
    await waitFor(() => {
      expect(screen.getByText(/Recorded · org decisions and insights/i)).toBeTruthy();
    });
  });

  it("shows 'Live' header by default", async () => {
    render(<DecisionTicker enabled={true} />);
    await waitFor(() => {
      expect(screen.getByText(/Live · org decisions and insights/i)).toBeTruthy();
    });
  });

  it("colours persona names from /api/personas/colors", async () => {
    render(<DecisionTicker enabled={true} />);
    await waitFor(() => {
      const cfo = screen.getByText("CFO");
      expect(cfo).toBeTruthy();
      expect((cfo as HTMLElement).style.color).toBeTruthy();
      // jsdom normalises hex to rgb in computed style strings.
      const c = (cfo as HTMLElement).style.color.replace(/\s+/g, "");
      expect(
        c === "#4f9bff" || c === "rgb(79,155,255)",
      ).toBe(true);
    });
  });
});

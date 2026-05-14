// @vitest-environment jsdom
import { describe, it, expect, beforeEach, afterEach, vi } from "vitest";
import { cleanup, render, screen, waitFor } from "@testing-library/react";
import { AccountsPage } from "../AccountsPage";

const SUMMARY = {
  accounts: [
    { id: "ACC-6010", code: "6010", name: "Production cost — external",
      type: "expense", total_gbp: 154300, row_count: 47, cost_centres: ["CC-zava-creative"] },
    { id: "ACC-4100", code: "4100", name: "Revenue — media commission",
      type: "revenue", total_gbp: 88200, row_count: 23, cost_centres: [] },
  ],
};

beforeEach(() => {
  vi.stubGlobal("fetch", vi.fn(async (url: string | URL) => {
    const u = typeof url === "string" ? url : url.toString();
    if (u.includes("/by-brand")) {
      return new Response(JSON.stringify({
        brands: [{ brand_id: "BRAND-aurora", brand_name: "Aurora",
                   client_name: "Zava Creative", total_gbp: 9999, row_count: 3 }],
      }), { status: 200, headers: { "Content-Type": "application/json" } });
    }
    return new Response(JSON.stringify(SUMMARY), {
      status: 200, headers: { "Content-Type": "application/json" },
    });
  }));
});
afterEach(() => { cleanup(); vi.unstubAllGlobals(); });

describe("AccountsPage", () => {
  it("lists accounts with totals", async () => {
    render(<AccountsPage />);
    await waitFor(() => {
      expect(screen.getByText(/Production cost/)).toBeTruthy();
      expect(screen.getByText(/154,300/)).toBeTruthy();
    });
  });

  it("groups expense vs revenue", async () => {
    render(<AccountsPage />);
    await waitFor(() => {
      expect(screen.getByText(/^Expenses$/i)).toBeTruthy();
      expect(screen.getByText(/^Revenue$/i)).toBeTruthy();
    });
  });

  it("shows the spend-by-brand panel when the route returns data", async () => {
    render(<AccountsPage />);
    await waitFor(() => {
      expect(screen.getByText(/Spend by brand/i)).toBeTruthy();
      expect(screen.getByText("Aurora")).toBeTruthy();
      expect(screen.getByText(/9,999/)).toBeTruthy();
    });
  });
});

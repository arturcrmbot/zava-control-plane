// @vitest-environment jsdom
import { describe, expect, it, vi, beforeEach, afterEach } from "vitest";
import { render, screen, fireEvent, waitFor, cleanup } from "@testing-library/react";
import { AccuracyReport } from "@client/components/AccuracyReport";

describe("AccuracyReport", () => {
  beforeEach(() => {
    // Stub EventSource so the component's useEffect doesn't try to open a real SSE.
    (globalThis as any).EventSource = class {
      addEventListener() {}
      close() {}
    };
  });

  afterEach(() => {
    cleanup();
    vi.restoreAllMocks();
  });

  it("renders 'no run yet' when no last report", async () => {
    globalThis.fetch = vi.fn().mockResolvedValue({ ok: false, status: 404 } as Response);
    render(<AccuracyReport />);
    await waitFor(() => expect(screen.getByText(/no completed run/i)).toBeTruthy());
  });

  it("renders confusion matrix when last report present", async () => {
    const fakeReport = {
      run_id: "acc-1",
      n: 300,
      overall_accuracy: 0.974,
      per_category: { meals: { n: 100, accuracy: 0.97 } },
      confusion_matrix: {
        green: { green: 200, amber: 5, red: 0 },
        amber: { green: 2, amber: 50, red: 3 },
        red: { green: 0, amber: 1, red: 39 },
      },
      per_claim: [],
    };
    globalThis.fetch = vi.fn().mockResolvedValue({ ok: true, json: async () => fakeReport } as Response);
    render(<AccuracyReport />);
    await waitFor(() => expect(screen.getByText("97.4%")).toBeTruthy());
    expect(screen.getByText("200")).toBeTruthy();
    expect(screen.getByText(/meals/i)).toBeTruthy();
  });

  it("clicking 'Run accuracy harness' POSTs /api/accuracy/run", async () => {
    const fetchMock = vi.fn()
      .mockResolvedValueOnce({ ok: false, status: 404 } as Response) // initial GET /last
      .mockResolvedValueOnce({ ok: true, json: async () => ({ run_id: "acc-2", n: 300 }) } as Response); // POST /run
    globalThis.fetch = fetchMock;
    render(<AccuracyReport />);
    const btn = await screen.findByRole("button", { name: /run accuracy/i });
    fireEvent.click(btn);
    await waitFor(() => {
      expect(fetchMock).toHaveBeenCalledWith("/api/accuracy/run", expect.objectContaining({ method: "POST" }));
    });
  });
});

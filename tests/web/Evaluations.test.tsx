// @vitest-environment jsdom
import { render, screen, waitFor, cleanup } from "@testing-library/react";
import { describe, it, expect, beforeEach, afterEach, vi } from "vitest";
import Evaluations from "@client/routes/Evaluations";

beforeEach(() => {
  (globalThis as any).EventSource = class {
    addEventListener() {}
    close() {}
  };
});

afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
});

const fetchMock = (jsonByUrl: Record<string, any>) =>
  vi.fn(async (url: string | URL | Request) => {
    const path = typeof url === "string" ? url : (url as any).toString();
    const keys = Object.keys(jsonByUrl).sort((a, b) => b.length - a.length);
    for (const key of keys) {
      if (path.startsWith(key)) {
        const body = jsonByUrl[key];
        if (body && body.__status === 404) {
          return { ok: false, status: 404, json: async () => null } as any;
        }
        return { ok: true, json: async () => body } as any;
      }
    }
    return { ok: false, status: 404, json: async () => null } as any;
  });

describe("Evaluations.tsx", () => {
  it("renders the not-configured panel when Foundry is not configured", async () => {
    global.fetch = fetchMock({
      "/api/evals/summary": { configured: false, reason: "endpoint not set" },
      "/api/evals/": { configured: false, reason: "endpoint not set" },
      "/api/accuracy/last": { __status: 404 },
    }) as any;
    render(<Evaluations />);
    await waitFor(() => expect(screen.getByText(/Evaluation pipeline is not configured/i)).toBeTruthy());
    expect(screen.queryByRole("heading", { name: /Task adherence/i })).toBeNull();
    expect(document.querySelector(".grid.grid-cols-3")).toBeNull();
  });

  it("renders three tiles with real values when configured + data", async () => {
    global.fetch = fetchMock({
      "/api/evals/summary": {
        configured: true,
        window_minutes: 60,
        tiles: {
          task_adherence: { value: 0.92, n_evals: 47, n_agents: 2, evaluators: ["groundedness"] },
          safety: { value: 0.99, n_evals: 47, n_agents: 2, evaluators: ["violence", "hate_unfairness"] },
          tool_accuracy: { value: 0.96, n_evals: 32, n_agents: 1, evaluators: ["tool_call_validity"] },
        },
        by_agent: [
          { agent_label: "rag-classifier", n: 32, scores: { groundedness: 0.93 } },
        ],
        n_completed: 47,
        n_errored: 0,
        queue: { pending: 0, completed: 47, errored: 0 },
      },
      "/api/evals/": { configured: true, rows: [] },
      "/api/accuracy/last": { __status: 404 },
    }) as any;
    render(<Evaluations />);
    await waitFor(() => {
      expect(screen.getByText(/92\.0%/)).toBeTruthy();
      expect(screen.getByText(/99\.0%/)).toBeTruthy();
      expect(screen.getByText(/96\.0%/)).toBeTruthy();
      expect(screen.getByText(/rag-classifier/)).toBeTruthy();
    });
  });

  it("renders the empty state when configured + no data", async () => {
    global.fetch = fetchMock({
      "/api/evals/summary": {
        configured: true, window_minutes: 60,
        tiles: {
          task_adherence: { value: 0.0, n_evals: 0, n_agents: 0, evaluators: ["groundedness"] },
          safety: { value: 0.0, n_evals: 0, n_agents: 0, evaluators: ["violence", "hate_unfairness"] },
          tool_accuracy: { value: 0.0, n_evals: 0, n_agents: 0, evaluators: ["tool_call_validity"] },
        },
        by_agent: [],
        n_completed: 0, n_errored: 0,
        queue: { pending: 0, completed: 0, errored: 0 },
      },
      "/api/evals/": { configured: true, rows: [] },
      "/api/accuracy/last": { __status: 404 },
    }) as any;
    render(<Evaluations />);
    await waitFor(() => expect(screen.getByText(/No evaluations yet/i)).toBeTruthy());
  });
});

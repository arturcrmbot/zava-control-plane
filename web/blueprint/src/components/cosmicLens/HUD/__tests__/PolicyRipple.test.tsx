// @vitest-environment jsdom
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { act, cleanup, render, screen, waitFor } from "@testing-library/react";
import { PolicyRipple } from "../PolicyRipple";

type FakeES = {
  url: string;
  close: () => void;
  onmessage: ((ev: { data: string }) => void) | null;
  onerror: ((ev: any) => void) | null;
};

const fakeSources: FakeES[] = [];

function setupFakes() {
  fakeSources.length = 0;
  vi.stubGlobal(
    "fetch",
    vi.fn(async (url: string) => {
      if (url.includes("/api/personas/colors")) {
        return new Response(JSON.stringify({ cfo: "#4f9bff" }), {
          status: 200,
        });
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
      fakeSources.push(this as unknown as FakeES);
    }
    close() {}
  };
}

function emit(item: any) {
  const es = fakeSources[fakeSources.length - 1];
  expect(es).toBeTruthy();
  act(() => {
    es!.onmessage?.({ data: JSON.stringify(item) });
  });
}

describe("PolicyRipple", () => {
  beforeEach(() => {
    setupFakes();
  });
  afterEach(() => {
    cleanup();
  });

  it("renders nothing when disabled", () => {
    const { container } = render(<PolicyRipple enabled={false} />);
    expect(container.innerHTML).toBe("");
  });

  it("paints a ripple when a Decision policy_set event arrives", async () => {
    render(<PolicyRipple enabled={true} />);
    await waitFor(() => expect(fakeSources.length).toBe(1));

    emit({
      kind: "Decision",
      id: "DEC-1",
      persona_role: "cfo",
      phase: "policy_set",
      verdict: "approve",
      decided_at: new Date().toISOString(),
    });

    await waitFor(() => {
      const rings = screen.getAllByTestId("policy-ripple-ring");
      expect(rings.length).toBeGreaterThan(0);
    });

    // animation still running 100ms in
    await new Promise((r) => setTimeout(r, 100));
    expect(screen.getAllByTestId("policy-ripple-ring").length).toBeGreaterThan(0);
  });

  it("ignores non-matching events (Insight, non-policy_set Decision)", async () => {
    render(<PolicyRipple enabled={true} />);
    await waitFor(() => expect(fakeSources.length).toBe(1));

    emit({
      kind: "Insight",
      id: "INS-1",
      role: "cfo",
      headline: "hi",
      decided_at: new Date().toISOString(),
    });
    emit({
      kind: "Decision",
      id: "DEC-2",
      persona_role: "cfo",
      phase: "approve",
      verdict: "approve",
      decided_at: new Date().toISOString(),
    });

    expect(screen.queryAllByTestId("policy-ripple-ring").length).toBe(0);
  });

  it("uses persona hue from /api/personas/colors", async () => {
    render(<PolicyRipple enabled={true} />);
    // wait for fetch to populate colors
    await waitFor(() =>
      expect((global.fetch as any)).toHaveBeenCalledWith(
        "/api/personas/colors",
      ),
    );
    await waitFor(() => expect(fakeSources.length).toBe(1));
    // Give the colors fetch microtask a chance to flush into state.
    await act(async () => {
      await Promise.resolve();
      await Promise.resolve();
    });

    emit({
      kind: "Decision",
      id: "DEC-3",
      persona_role: "cfo",
      phase: "policy_set",
      verdict: "approve",
      decided_at: new Date().toISOString(),
    });

    await waitFor(() => {
      const ring = screen.getAllByTestId("policy-ripple-ring")[0] as HTMLElement;
      expect(ring).toBeTruthy();
      const border = ring.style.border || "";
      // jsdom may report border as empty if shorthand isn't supported; accept either.
      const matches =
        border.includes("#4f9bff") ||
        border.includes("rgb(79, 155, 255)") ||
        ring.style.borderColor.includes("4f9bff") ||
        ring.style.borderColor.includes("rgb(79, 155, 255)") ||
        ring.outerHTML.includes("#4f9bff");
      expect(matches).toBe(true);
    });
  });
});

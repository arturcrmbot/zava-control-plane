// @vitest-environment jsdom
import { afterEach, describe, expect, it, vi } from "vitest";
import { apiFetch, REPLAY_BLOCKED_EVENT } from "@client/lib/api";

afterEach(() => {
  vi.restoreAllMocks();
});

describe("apiFetch", () => {
  it("dispatches replay-blocked on 403 replay responses for non-GET requests", async () => {
    const handler = vi.fn();
    window.addEventListener(REPLAY_BLOCKED_EVENT, handler as EventListener);
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(JSON.stringify({ error: "replay", message: "test message" }), {
        status: 403,
        headers: { "content-type": "application/json" },
      }),
    );

    const response = await apiFetch("/foo", { method: "POST" });

    expect(handler).toHaveBeenCalledTimes(1);
    expect((handler.mock.calls[0]?.[0] as CustomEvent<{ message: string }>).detail).toEqual({
      message: "test message",
    });
    expect(response.ok).toBe(false);
    expect(response.status).toBe(403);
    window.removeEventListener(REPLAY_BLOCKED_EVENT, handler as EventListener);
  });

  it("does not dispatch replay-blocked for GET replay responses", async () => {
    const handler = vi.fn();
    window.addEventListener(REPLAY_BLOCKED_EVENT, handler as EventListener);
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(JSON.stringify({ error: "replay", message: "test message" }), {
        status: 403,
        headers: { "content-type": "application/json" },
      }),
    );

    const response = await apiFetch("/foo", { method: "GET" });

    expect(handler).not.toHaveBeenCalled();
    expect(response.status).toBe(403);
    window.removeEventListener(REPLAY_BLOCKED_EVENT, handler as EventListener);
  });

  it("does not dispatch replay-blocked on non-403 responses", async () => {
    const handler = vi.fn();
    window.addEventListener(REPLAY_BLOCKED_EVENT, handler as EventListener);
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(JSON.stringify({ ok: true }), {
        status: 200,
        headers: { "content-type": "application/json" },
      }),
    );

    await apiFetch("/foo", { method: "POST" });

    expect(handler).not.toHaveBeenCalled();
    window.removeEventListener(REPLAY_BLOCKED_EVENT, handler as EventListener);
  });

  it("does not dispatch replay-blocked for other 403 errors", async () => {
    const handler = vi.fn();
    window.addEventListener(REPLAY_BLOCKED_EVENT, handler as EventListener);
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(JSON.stringify({ error: "auth", message: "nope" }), {
        status: 403,
        headers: { "content-type": "application/json" },
      }),
    );

    await apiFetch("/foo", { method: "POST" });

    expect(handler).not.toHaveBeenCalled();
    window.removeEventListener(REPLAY_BLOCKED_EVENT, handler as EventListener);
  });
});

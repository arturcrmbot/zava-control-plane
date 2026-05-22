// @vitest-environment jsdom
import { describe, it, expect, beforeEach, afterEach, vi } from "vitest";
import { render, screen, cleanup, act } from "@testing-library/react";
import { RestartBanner } from "@client/components/feed/RestartBanner";

class FakeEventSource {
  static instances: FakeEventSource[] = [];

  onmessage: ((event: { data: string }) => void) | null = null;
  onopen: (() => void) | null = null;
  onerror: (() => void) | null = null;
  readyState = 1;
  url: string;
  close = vi.fn();

  constructor(url: string) {
    this.url = url;
    FakeEventSource.instances.push(this);
  }
}

beforeEach(() => {
  vi.useFakeTimers();
  FakeEventSource.instances = [];
  (globalThis as { __sseShared?: Map<string, unknown> }).__sseShared?.clear();
  (globalThis as { __sseStatusListeners?: Set<() => void> }).__sseStatusListeners?.clear();
  (globalThis as { EventSource?: unknown }).EventSource = vi.fn().mockImplementation((url: string) => new FakeEventSource(url));
});

afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
  vi.useRealTimers();
  (globalThis as { __sseShared?: Map<string, unknown> }).__sseShared?.clear();
  (globalThis as { __sseStatusListeners?: Set<() => void> }).__sseStatusListeners?.clear();
});

describe("RestartBanner", () => {
  it("renders nothing before a restart event arrives", () => {
    render(<RestartBanner />);

    expect(globalThis.EventSource).toHaveBeenCalledWith("/api/blueprint/stream");
    expect(screen.queryByText(/Replay restarting…/i)).toBeNull();
  });

  it("shows the banner when playback.restart.pending arrives", () => {
    render(<RestartBanner />);

    act(() => {
      FakeEventSource.instances[0]?.onmessage?.({
        data: JSON.stringify({ type: "playback.restart.pending" }),
      });
    });

    expect(screen.getByText(/Replay restarting…/i)).toBeTruthy();
  });

  it("auto-dismisses after 3 seconds", () => {
    render(<RestartBanner />);

    act(() => {
      FakeEventSource.instances[0]?.onmessage?.({
        data: JSON.stringify({ type: "playback.restart.pending" }),
      });
    });

    expect(screen.getByText(/Replay restarting…/i)).toBeTruthy();

    act(() => {
      vi.advanceTimersByTime(3_001);
    });

    expect(screen.queryByText(/Replay restarting…/i)).toBeNull();
  });

  it("resets the dismiss timer when another restart event arrives", () => {
    render(<RestartBanner />);

    act(() => {
      FakeEventSource.instances[0]?.onmessage?.({
        data: JSON.stringify({ type: "playback.restart.pending" }),
      });
    });

    act(() => {
      vi.advanceTimersByTime(2_500);
      FakeEventSource.instances[0]?.onmessage?.({
        data: JSON.stringify({ type: "playback.restart.pending" }),
      });
    });

    act(() => {
      vi.advanceTimersByTime(600);
    });

    expect(screen.getByText(/Replay restarting…/i)).toBeTruthy();

    act(() => {
      vi.advanceTimersByTime(2_401);
    });

    expect(screen.queryByText(/Replay restarting…/i)).toBeNull();
  });
});

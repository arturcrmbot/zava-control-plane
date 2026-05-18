// @vitest-environment jsdom
// web/client/components/feed/__tests__/Toast.test.tsx
import { describe, it, expect, afterEach, vi, beforeEach } from "vitest";
import { render, screen, cleanup, act } from "@testing-library/react";
import { ToastProvider, useToast } from "@client/components/feed/Toast";

beforeEach(() => vi.useFakeTimers());
afterEach(() => { cleanup(); vi.useRealTimers(); });

describe("Toast", () => {
  it("show() renders a message; auto-dismisses after default TTL", () => {
    function Probe() {
      const t = useToast();
      return <button onClick={() => t.show("hello")}>fire</button>;
    }
    render(<ToastProvider><Probe /></ToastProvider>);
    act(() => { (screen.getByRole("button") as HTMLButtonElement).click(); });
    expect(screen.getByText("hello")).toBeTruthy();
    act(() => { vi.advanceTimersByTime(4_001); });
    expect(screen.queryByText("hello")).toBeNull();
  });
});

// @vitest-environment jsdom
import { cleanup, renderHook } from "@testing-library/react";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import { usePanelVisibility } from "../usePanelVisibility";

beforeEach(() => {
  localStorage.clear();
  vi.stubGlobal("matchMedia", vi.fn(() => ({
    matches: true, addEventListener: vi.fn(), removeEventListener: vi.fn(),
  })));
});
afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
  localStorage.clear();
});

it("starts small screens with optional side panels hidden", () => {
  const { result } = renderHook(usePanelVisibility);
  expect(result.current.visible("narrative-arcs")).toBe(false);
  expect(result.current.visible("activity-rail")).toBe(false);
});

it("preserves an explicit choice to show all panels on a small screen", () => {
  localStorage.setItem("zava.hud.hidden", "[]");
  const { result } = renderHook(usePanelVisibility);
  expect(result.current.visible("narrative-arcs")).toBe(true);
  expect(result.current.visible("activity-rail")).toBe(true);
});

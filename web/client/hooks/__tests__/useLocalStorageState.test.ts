// @vitest-environment jsdom
// web/client/hooks/__tests__/useLocalStorageState.test.ts
import { describe, it, expect, beforeEach, afterEach, vi } from "vitest";
import { renderHook, act } from "@testing-library/react";
import { useLocalStorageState } from "../useLocalStorageState";

beforeEach(() => localStorage.clear());
afterEach(() => localStorage.clear());

describe("useLocalStorageState", () => {
  it("returns the default value when the key is absent", () => {
    const { result } = renderHook(() => useLocalStorageState("k", { x: 1 }));
    expect(result.current[0]).toEqual({ x: 1 });
  });

  it("persists updates to localStorage", () => {
    const { result } = renderHook(() => useLocalStorageState("k", 0));
    act(() => result.current[1](42));
    expect(localStorage.getItem("k")).toBe(JSON.stringify(42));
    expect(result.current[0]).toBe(42);
  });

  it("reads a pre-existing value on mount", () => {
    localStorage.setItem("k", JSON.stringify("hello"));
    const { result } = renderHook(() => useLocalStorageState("k", "default"));
    expect(result.current[0]).toBe("hello");
  });

  it("falls back to default on malformed JSON", () => {
    localStorage.setItem("k", "{not json");
    const { result } = renderHook(() => useLocalStorageState("k", 99));
    expect(result.current[0]).toBe(99);
  });

  it("supports functional updates", () => {
    const { result } = renderHook(() => useLocalStorageState("k", 1));
    act(() => result.current[1]((v) => (v as number) + 1));
    expect(result.current[0]).toBe(2);
  });

  it("keeps in-memory state when localStorage.setItem throws", () => {
    const spy = vi.spyOn(Storage.prototype, "setItem").mockImplementation(() => {
      throw new Error("quota exceeded");
    });
    const { result } = renderHook(() => useLocalStorageState("k", 0));
    act(() => result.current[1](7));
    expect(result.current[0]).toBe(7);
    spy.mockRestore();
  });

  it("does not write the default value to localStorage on mount", () => {
    renderHook(() => useLocalStorageState("k", { x: 1 }));
    expect(localStorage.getItem("k")).toBeNull();
  });

  it("re-syncs state from localStorage when key changes", () => {
    localStorage.setItem("k1", JSON.stringify(11));
    localStorage.setItem("k2", JSON.stringify(22));
    const { result, rerender } = renderHook(
      ({ k }) => useLocalStorageState(k, 0),
      { initialProps: { k: "k1" } },
    );
    expect(result.current[0]).toBe(11);
    rerender({ k: "k2" });
    expect(result.current[0]).toBe(22);
  });

  it("falls back to defaultValue when the new key is absent after a key change", () => {
    localStorage.setItem("present", JSON.stringify(99));
    const { result, rerender } = renderHook(
      ({ k }) => useLocalStorageState(k, "default"),
      { initialProps: { k: "present" } },
    );
    expect(result.current[0]).toBe(99);
    rerender({ k: "absent" });
    expect(result.current[0]).toBe("default");
  });
});

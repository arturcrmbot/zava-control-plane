// @vitest-environment jsdom
// web/client/hooks/__tests__/useLocalStorageState.test.ts
import { describe, it, expect, beforeEach, afterEach } from "vitest";
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
});

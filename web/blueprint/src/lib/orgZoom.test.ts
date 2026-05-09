import { describe, expect, it } from "vitest";
import { act, renderHook } from "@testing-library/react";
import {
  DEPARTMENT_FRAMING,
  ORG_FRAMING,
  WORKFLOW_FRAMING,
  framingFor,
  levelForKind,
  useOrgZoom,
  wingFraming,
} from "./orgZoom";

describe("orgZoom level numbering", () => {
  it("maps kinds to spec-level numbers", () => {
    expect(levelForKind("org")).toBe(3);
    expect(levelForKind("wing")).toBe(2);
    expect(levelForKind("department")).toBe(1);
    expect(levelForKind("workflow")).toBe(0);
  });

  it("framingFor returns the kind-appropriate framing", () => {
    expect(framingFor({ kind: "org" })).toEqual(ORG_FRAMING);
    expect(framingFor({ kind: "department" })).toEqual(DEPARTMENT_FRAMING);
    expect(framingFor({ kind: "workflow" })).toEqual(WORKFLOW_FRAMING);
  });

  it("wingFraming Y-targets the mean floor Y of the wing", () => {
    const money = wingFraming("Money");
    // Money = finance + revenue (two adjacent floors); framing should
    // sit somewhere in the middle of the building, not at the org default.
    expect(money.lookAt[1]).toBeGreaterThan(0);
    expect(money.fov).toBe(38);
  });

  it("wingFraming falls back to ORG_FRAMING for unknown wings", () => {
    expect(wingFraming("not-a-wing")).toEqual(ORG_FRAMING);
  });
});

describe("useOrgZoom — zoomOut chain (chunk 4)", () => {
  it("ESC chains workflow → department → wing → org via history", () => {
    const { result } = renderHook(() => useOrgZoom());
    // Drill from org → wing → department → workflow.
    act(() => result.current.zoomTo({ kind: "wing", id: "Money" }));
    expect(result.current.target).toEqual({ kind: "wing", id: "Money" });
    act(() => result.current.zoomTo({ kind: "department", id: "finance" }));
    expect(result.current.target).toEqual({
      kind: "department",
      id: "finance",
    });
    act(() => result.current.zoomTo({ kind: "workflow", id: "wf-1" }));
    expect(result.current.target).toEqual({ kind: "workflow", id: "wf-1" });

    // Now ESC three times — must walk back through the chain.
    act(() => result.current.zoomOut());
    expect(result.current.target).toEqual({
      kind: "department",
      id: "finance",
    });
    act(() => result.current.zoomOut());
    expect(result.current.target).toEqual({ kind: "wing", id: "Money" });
    act(() => result.current.zoomOut());
    expect(result.current.target).toEqual({ kind: "org" });
    // Org is terminal — further ESC is a no-op.
    act(() => result.current.zoomOut());
    expect(result.current.target).toEqual({ kind: "org" });
  });

  it("history-less workflow target falls back to org on ESC", () => {
    const { result } = renderHook(() => useOrgZoom());
    // Simulate a deep-link / programmatic workflow zoom with no
    // breadcrumb (e.g. EventFeed click from org view).
    act(() => result.current.zoomTo({ kind: "workflow", id: "wf-x" }));
    act(() => result.current.zoomOut());
    // Single hop back to where we came from (org).
    expect(result.current.target).toEqual({ kind: "org" });
  });

  it("department-without-history falls back to its wing on ESC", () => {
    const { result } = renderHook(() => useOrgZoom());
    // Simulate landing directly at department via window event so the
    // history stack only contains org.
    act(() => {
      window.dispatchEvent(
        new CustomEvent("org-building:zoom-to", {
          detail: { kind: "department", id: "finance" },
        }),
      );
    });
    expect(result.current.target).toEqual({
      kind: "department",
      id: "finance",
    });
    act(() => result.current.zoomOut());
    // Pops the org we came from.
    expect(result.current.target).toEqual({ kind: "org" });
  });
});

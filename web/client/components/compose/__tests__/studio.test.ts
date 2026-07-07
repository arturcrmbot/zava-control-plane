import { describe, it, expect } from "vitest";
import { visualStage } from "../studio/types";
import { buildPreviewState } from "../studio/StudioPreview";

describe("visualStage", () => {
  it("maps agent stages to the four milestones", () => {
    expect(visualStage("intake", false)).toBe("read");
    expect(visualStage("understanding", false)).toBe("read");
    expect(visualStage("brief", false)).toBe("design");
    expect(visualStage("composing", false)).toBe("build");
    expect(visualStage("graduating", false)).toBe("build");
    expect(visualStage("verifying", false)).toBe("build");
    expect(visualStage("ready", false)).toBe("ready");
    expect(visualStage("composing", true)).toBe("ready"); // done overrides
  });
});

describe("buildPreviewState", () => {
  it("has no composition while reading, and a full one once designing", () => {
    expect(buildPreviewState("read").composition).toBeUndefined();
    const design = buildPreviewState("design");
    expect(design.composition?.steps).toHaveLength(4);
  });

  it("build stage has an in-progress agent stage and a recorded decision", () => {
    const b = buildPreviewState("build");
    expect(b.stage).toBe("composing");
    expect(b.decisions).toHaveLength(1);
    expect(b.done).toBeUndefined();
  });

  it("ready stage reports the ready agent stage", () => {
    const r = buildPreviewState("ready");
    expect(r.stage).toBe("ready");
  });
});

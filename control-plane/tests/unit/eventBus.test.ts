import { describe, it, expect, vi } from "vitest";
import { EventBus } from "@server/services/eventBus";

describe("EventBus", () => {
  it("delivers events to subscribers", () => {
    const bus = new EventBus();
    const fn = vi.fn();
    bus.on("workflow.started", fn);
    bus.emit({ type: "workflow.started", workflowId: "A" });
    expect(fn).toHaveBeenCalledWith({ type: "workflow.started", workflowId: "A" });
  });
  it("supports onAny", () => {
    const bus = new EventBus();
    const fn = vi.fn();
    bus.onAny(fn);
    bus.emit({ type: "fleet.tick", timestamp: 1 });
    expect(fn).toHaveBeenCalled();
  });
  it("unsubscribe works", () => {
    const bus = new EventBus();
    const fn = vi.fn();
    const off = bus.on("workflow.started", fn);
    off();
    bus.emit({ type: "workflow.started", workflowId: "A" });
    expect(fn).not.toHaveBeenCalled();
  });
});

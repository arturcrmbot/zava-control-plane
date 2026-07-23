import { describe, it, expect } from "vitest";
import { labelForCapability, labelForEntity, isReadEvent, isWriteEvent } from "../labels";

describe("labelForCapability", () => {
  it("renders persona thinking with the persona name", () => {
    expect(labelForCapability({ type: "persona.thinking", persona: "ap_clerk" })).toBe(
      "AP Clerk is reviewing",
    );
  });
  it("renders persona decided", () => {
    expect(labelForCapability({ type: "persona.decided", persona: "controller" })).toBe(
      "Controller decided",
    );
  });
  it("renders running tool", () => {
    expect(labelForCapability({ type: "tool.invoked", tool_name: "stripe.charge" })).toBe(
      "Running Stripe Charge",
    );
  });
  it("renders completed tool", () => {
    expect(labelForCapability({ type: "tool.completed", tool_name: "stripe.charge" })).toBe(
      "Stripe Charge — done",
    );
  });
  it("falls back to type when fields are missing", () => {
    expect(labelForCapability({ type: "completely.unknown" })).toBe("Completely Unknown ran");
  });
});

describe("labelForEntity", () => {
  it("renders read with id", () => {
    expect(
      labelForEntity({ type: "entity.read", entity_kind: "Person", entity_id: "CAND-0042" }),
    ).toBe("Looked up person details CAND-0042");
  });
  it("renders update vs create", () => {
    expect(
      labelForEntity({ type: "entity.upserted", entity_kind: "Invoice", entity_id: "INV-0871", verb: "update" }),
    ).toBe("Updated invoice INV-0871");
    expect(
      labelForEntity({ type: "entity.upserted", entity_kind: "Vendor", verb: "create" }),
    ).toBe("Created vendor record");
  });
  it("renders link", () => {
    expect(labelForEntity({ type: "entity.linked", entity_kind: "Decision" })).toBe(
      "Connected decision",
    );
  });
});

describe("isReadEvent / isWriteEvent", () => {
  it("classifies read", () => {
    expect(isReadEvent("entity.read")).toBe(true);
    expect(isWriteEvent("entity.read")).toBe(false);
  });
  it("classifies write", () => {
    expect(isWriteEvent("entity.upserted")).toBe(true);
    expect(isWriteEvent("entity.linked")).toBe(true);
    expect(isReadEvent("entity.upserted")).toBe(false);
  });
});

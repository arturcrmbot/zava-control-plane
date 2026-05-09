import { describe, expect, it } from "vitest";
import { resolveFunction, translateEvent } from "./orgEvents";
import type { OrgFunction } from "./useOrgData";
import type { ObservatoryEvent } from "./types";
import { DEFAULT_LAYERS } from "./layerToggles";

const FN_FINANCE: OrgFunction = {
  name: "finance",
  display: "Finance",
  operatorSurface: "cfo",
  ownsDomains: ["vendor_kyc", "expense_claim"],
  ambientAgents: ["spend_watcher"],
  kpis: ["spend"],
  personaHierarchy: { role: "cfo", manages: [] },
};

const FN_HR: OrgFunction = {
  name: "hr",
  display: "HR",
  operatorSurface: "chro",
  ownsDomains: ["hiring"],
  ambientAgents: [],
  kpis: [],
  personaHierarchy: { role: "chro", manages: [] },
};

const ctx = {
  functionByWorkflowType: new Map<string, string>([
    ["vendor_kyc", "finance"],
    ["expense_claim", "finance"],
    ["hiring", "hr"],
  ]),
  functionByName: new Map<string, OrgFunction>([
    ["finance", FN_FINANCE],
    ["hr", FN_HR],
  ]),
  layers: DEFAULT_LAYERS,
};

function ev(over: Partial<ObservatoryEvent>): ObservatoryEvent {
  return {
    type: "entity.upserted",
    skill: null,
    tool: null,
    domain: null,
    workflow_id: "wf-1",
    ts: 0,
    ...over,
  } as ObservatoryEvent;
}

describe("resolveFunction", () => {
  it("uses explicit function field first", () => {
    expect(resolveFunction(ev({ function: "hr" }), ctx)).toBe("hr");
  });
  it("falls back to workflow_type lookup", () => {
    expect(
      resolveFunction(ev({ workflow_type: "vendor_kyc" }), ctx),
    ).toBe("finance");
  });
  it("returns null when no signal", () => {
    expect(resolveFunction(ev({}), ctx)).toBeNull();
  });
});

describe("translateEvent", () => {
  it("emits a mote for entity.upserted", () => {
    const e = translateEvent(
      ev({
        type: "entity.upserted",
        workflow_type: "vendor_kyc",
        entity_id: "VEN-1",
        entity_kind: "Organisation",
      }),
      ctx,
    );
    expect(e?.kind).toBe("mote");
    expect(e?.from).toBeDefined();
    expect(e?.to).toBeDefined();
  });

  it("emits a violet spark for decision.recorded", () => {
    const e = translateEvent(
      ev({
        type: "decision.recorded",
        workflow_type: "vendor_kyc",
        decision_id: "DEC-1",
      }),
      ctx,
    );
    expect(e?.kind).toBe("spark");
    expect(e?.color).toBe("#a78bfa");
  });

  it("emits a magenta filament for sub_spawned", () => {
    const e = translateEvent(
      ev({
        type: "workflow.sub_spawned",
        workflow_type: "vendor_kyc",
        parent_workflow_id: "wf-parent",
        child_workflow_id: "wf-child",
      } as Partial<ObservatoryEvent>),
      ctx,
    );
    expect(e?.kind).toBe("filament");
    expect(e?.color).toBe("#ec4899");
  });

  it("returns null when the layer is disabled", () => {
    const layers = { ...DEFAULT_LAYERS, decisionSparks: false };
    const e = translateEvent(
      ev({ type: "decision.recorded", workflow_type: "vendor_kyc" }),
      { ...ctx, layers },
    );
    expect(e).toBeNull();
  });

  it("returns null for unknown event types", () => {
    expect(translateEvent(ev({ type: "mystery.fired" }), ctx)).toBeNull();
  });
});

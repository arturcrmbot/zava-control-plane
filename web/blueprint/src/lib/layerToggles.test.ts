import { afterEach, beforeEach, describe, expect, it } from "vitest";
import {
  DEFAULT_LAYERS,
  loadLayers,
  saveLayers,
} from "./layerToggles";

describe("layerToggles persistence", () => {
  beforeEach(() => {
    window.localStorage.clear();
  });
  afterEach(() => {
    window.localStorage.clear();
  });

  it("returns defaults when no storage entry exists", () => {
    expect(loadLayers()).toEqual(DEFAULT_LAYERS);
  });

  it("round-trips a saved snapshot", () => {
    const next = { ...DEFAULT_LAYERS, decisionSparks: false };
    saveLayers(next);
    expect(loadLayers().decisionSparks).toBe(false);
    expect(loadLayers().activityHeat).toBe(true);
  });

  it("merges partial saves with defaults", () => {
    window.localStorage.setItem(
      "org-building.layers",
      JSON.stringify({ entityFlows: false }),
    );
    const loaded = loadLayers();
    expect(loaded.entityFlows).toBe(false);
    expect(loaded.activityHeat).toBe(true);
  });

  it("falls back to defaults on corrupt JSON", () => {
    window.localStorage.setItem("org-building.layers", "{not json");
    expect(loadLayers()).toEqual(DEFAULT_LAYERS);
  });
});
